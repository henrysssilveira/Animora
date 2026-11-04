import uuid
from datetime import date, timedelta
from typing import Any

from services.classification_service import (
    calculate_age_days,
    classify_age_days,
    normalize_age_slug,
    parse_iso_date,
)
from services.species_service import normalize_species
from services.supabase_service import (
    MigrationRequiredError,
    SupabaseServiceError,
    get_supabase_client,
    is_valid_uuid,
    translate_supabase_error,
)


SCHEDULE_STATUS_META: dict[str, dict[str, str]] = {
    "pendente": {
        "label": "Pendente",
        "badge_class": "badge-status-pending",
        "icon": "bi-hourglass-split",
    },
    "proxima_aplicacao": {
        "label": "Próxima aplicação",
        "badge_class": "badge-status-upcoming",
        "icon": "bi-calendar-event",
    },
    "atrasada": {
        "label": "Atrasada",
        "badge_class": "badge-status-overdue",
        "icon": "bi-exclamation-triangle-fill",
    },
    "aplicada": {
        "label": "Aplicada",
        "badge_class": "badge-status-applied",
        "icon": "bi-check-circle-fill",
    },
    "nao_realizada": {
        "label": "Não realizada",
        "badge_class": "badge-status-not-done",
        "icon": "bi-slash-circle",
    },
    "historico_desconhecido": {
        "label": "Histórico desconhecido",
        "badge_class": "badge-status-unknown",
        "icon": "bi-question-circle",
    },
    "cancelada": {
        "label": "Cancelada",
        "badge_class": "badge-status-cancelled",
        "icon": "bi-x-circle",
    },
}

ONBOARDING_MODE_LABELS: dict[str, str] = {
    "acompanhamento_nascimento": "Acompanhamento desde o nascimento",
    "historico_conhecido": "Histórico de vacinação conhecido",
    "historico_desconhecido": "Histórico sanitário desconhecido",
    "avaliacao_inicial": "Em avaliação sanitária inicial",
    "inicio_inclusao": "Protocolo iniciado na data de inclusão",
}

TERMINAL_OR_FIXED_STATUSES = {
    "aplicada",
    "nao_realizada",
    "historico_desconhecido",
    "cancelada",
}


def compute_effective_schedule_status(
    schedule: dict[str, Any],
    ref_date: date | None = None,
) -> str:
    """
    Calcula o estado efetivo de um agendamento sem alterar estados fixos/históricos
    (aplicada, nao_realizada, historico_desconhecido, cancelada).
    """
    current_status = str(schedule.get("status") or "pendente").strip().lower()
    if current_status in TERMINAL_OR_FIXED_STATUSES:
        return current_status

    today = ref_date or date.today()
    start_dt = parse_iso_date(schedule.get("scheduled_date"))
    end_dt = parse_iso_date(schedule.get("window_end_date")) or start_dt

    if not start_dt:
        return current_status

    if end_dt and today > end_dt:
        return "atrasada"
    if today < start_dt:
        return "proxima_aplicacao"
    return "pendente"


def enrich_schedule_status(
    schedule: dict[str, Any],
    ref_date: date | None = None,
) -> dict[str, Any]:
    """Anexa metadados visuais e status dinâmico atualizado ao dicionário de agendamento."""
    enriched = dict(schedule)
    effective = compute_effective_schedule_status(enriched, ref_date=ref_date)
    meta = SCHEDULE_STATUS_META.get(effective, SCHEDULE_STATUS_META["pendente"])
    enriched["status"] = effective
    enriched["status_label"] = meta["label"]
    enriched["status_badge_class"] = meta["badge_class"]
    enriched["status_icon"] = meta["icon"]
    return enriched


def sync_dynamic_schedule_statuses(
    schedules: list[dict[str, Any]],
    persist_changes: bool = True,
) -> list[dict[str, Any]]:
    """
    Atualiza dinamicamente os agendamentos entre proxima_aplicacao, pendente e atrasada,
    sincronizando eventuais transições de data com o Supabase.
    """
    today = date.today()
    result: list[dict[str, Any]] = []
    updates_by_status: dict[str, list[str]] = {
        "pendente": [],
        "proxima_aplicacao": [],
        "atrasada": [],
    }

    for item in schedules:
        db_status = str(item.get("status") or "pendente")
        enriched = enrich_schedule_status(item, ref_date=today)
        new_status = enriched["status"]
        if (
            persist_changes
            and db_status not in TERMINAL_OR_FIXED_STATUSES
            and new_status != db_status
            and item.get("id")
        ):
            updates_by_status.setdefault(new_status, []).append(item["id"])
        result.append(enriched)

    if persist_changes and any(updates_by_status.values()):
        try:
            client = get_supabase_client()
            for target_status, ids in updates_by_status.items():
                if ids:
                    client.table("vaccination_schedules").update(
                        {"status": target_status}
                    ).in_("id", ids).execute()
        except Exception:
            # Em caso de falha transitória de rede na sincronização secundária, mantém cálculo em memória
            pass

    return result


def build_rule_schedule_payload(
    animal: dict[str, Any],
    protocol: dict[str, Any],
    rule: dict[str, Any],
    age_days: int,
    age_category: str,
    today: date | None = None,
) -> dict[str, Any] | None:
    """
    Determina como uma regra de protocolo se aplica a um animal específico,
    respeitando rigorosamente a diferença entre recém-nascidos e animais adultos/pré-existentes.
    Retorna o payload de agendamento ou None caso a regra não deva gerar pendência.
    """
    ref_today = today or date.today()
    birth_dt = parse_iso_date(animal.get("birth_date"))
    if not birth_dt:
        return None

    inclusion_dt = parse_iso_date(animal.get("inclusion_date")) or ref_today
    onboarding = str(animal.get("sanitary_onboarding_mode") or "acompanhamento_nascimento").strip()

    min_age = int(rule.get("min_age_days", 0))
    max_age = int(rule.get("max_age_days", min_age))
    dose_number = int(rule.get("dose_number", 1))
    raw_proto_category = str(protocol.get("animal_category") or "todas").strip().lower()
    proto_category = "todas" if raw_proto_category == "todas" else normalize_age_slug(raw_proto_category)
    norm_age_category = normalize_age_slug(age_category)

    animal_species = normalize_species(animal.get("species"))
    proto_species = str(protocol.get("target_species") or "todas").strip().lower()
    if proto_species not in ("todas", animal_species):
        return None

    # Verifica compatibilidade de categoria do protocolo
    if proto_category != "todas" and proto_category != norm_age_category:
        return None

    scheduled_dt = birth_dt + timedelta(days=min_age)
    window_end_dt = birth_dt + timedelta(days=max_age)
    status = "pendente"
    notes = rule.get("notes") or f"Gerado pelo protocolo '{protocol.get('name', '')}'."

    if onboarding == "acompanhamento_nascimento":
        # Acompanhamento desde o nascimento: avalia janela real a partir do nascimento
        if ref_today < scheduled_dt:
            status = "proxima_aplicacao"
        elif ref_today > window_end_dt:
            status = "atrasada"
        else:
            status = "pendente"

    elif onboarding == "historico_desconhecido":
        # Animais adultos ou pré-existentes sem histórico conhecido:
        # NUNCA classificar janelas anteriores à idade atual como atrasadas!
        if max_age < age_days:
            scheduled_dt = inclusion_dt
            window_end_dt = inclusion_dt
            status = "historico_desconhecido"
            notes = (
                "Animal cadastrado com histórico sanitário anterior desconhecido. "
                "A ausência de registro não implica que nunca foi vacinado."
            )
        else:
            if ref_today < scheduled_dt:
                status = "proxima_aplicacao"
            else:
                status = "pendente"
                if window_end_dt < ref_today:
                    window_end_dt = ref_today + timedelta(days=15)

    elif onboarding == "historico_conhecido":
        # Se a regra era de uma fase anterior e não consta aplicação registrada,
        # não marca automaticamente como atrasada sem validação clínica
        if max_age < age_days:
            return None
        status = "proxima_aplicacao" if ref_today < scheduled_dt else "pendente"

    elif onboarding == "avaliacao_inicial":
        # Em avaliação sanitária inicial: agenda apenas janelas vigentes ou futuras, sem falso atraso
        if max_age < age_days:
            return None
        status = "proxima_aplicacao" if ref_today < scheduled_dt else "pendente"

    elif onboarding == "inicio_inclusao":
        # Iniciar protocolo a partir da data de inclusão do animal na Animora
        window_span = max(15, max_age - min_age)
        if max_age < age_days:
            # Só inicia na inclusão se a regra pertencer à própria categoria atual do animal
            if proto_category != norm_age_category and min_age < 365 and norm_age_category == "adulto":
                return None
            scheduled_dt = inclusion_dt
            window_end_dt = inclusion_dt + timedelta(days=window_span)
        else:
            scheduled_dt = max(inclusion_dt, scheduled_dt)
            window_end_dt = max(scheduled_dt + timedelta(days=window_span), window_end_dt)

        status = "proxima_aplicacao" if ref_today < scheduled_dt else "pendente"
        notes = f"Protocolo iniciado a partir da inclusão ({inclusion_dt.strftime('%d/%m/%Y')})."

    return {
        "id": str(uuid.uuid4()),
        "organization_id": animal["organization_id"],
        "property_id": animal["property_id"],
        "animal_id": animal["id"],
        "vaccine_id": rule["vaccine_id"],
        "protocol_id": protocol["id"],
        "protocol_rule_id": rule["id"],
        "campaign_id": None,
        "origin_type": "protocolo",
        "dose_number": dose_number,
        "scheduled_date": scheduled_dt.isoformat(),
        "window_end_date": window_end_dt.isoformat(),
        "status": status,
        "notes": notes,
    }


def _load_age_brackets_safe(client, organization_id: str | None) -> list[dict[str, Any]] | None:
    try:
        query = client.table("age_classifications").select("*").eq("is_active", True)
        if organization_id and is_valid_uuid(organization_id):
            query = query.eq("organization_id", organization_id)
        rows = query.order("sort_order").execute().data
        return rows or None
    except Exception:
        return None


def generate_schedules_for_animal(
    animal: dict[str, Any],
    specific_protocol_id: str | None = None,
) -> dict[str, int]:
    """
    Executa o fluxo automático de geração de pendências para um animal:
    1. Identifica sua propriedade
    2. Calcula sua idade
    3. Identifica sua categoria etária
    4. Verifica os protocolos ativos e validados aplicáveis à propriedade
    5. Verifica as regras compatíveis com a categoria e a idade
    6. Gera agendamentos individuais pendentes sem duplicar nem sobrescrever histórico
    """
    stats = {"created_schedules": 0, "linked_protocols": 0, "skipped_duplicates": 0}

    property_id = animal.get("property_id")
    organization_id = animal.get("organization_id")
    animal_id = animal.get("id")

    if not animal_id or not property_id or not organization_id:
        return stats
    if str(animal.get("status", "ativo")).lower() != "ativo":
        return stats

    try:
        client = get_supabase_client()
        brackets = _load_age_brackets_safe(client, organization_id)

        age_days = calculate_age_days(animal.get("birth_date"))
        age_info = classify_age_days(age_days, brackets=brackets)
        age_category = age_info["slug"]

        # Busca protocolos ativos E validados pelo responsável técnico para a propriedade
        proto_query = (
            client.table("sanitary_protocols")
            .select("*")
            .eq("property_id", property_id)
            .eq("is_active", True)
            .eq("is_validated", True)
        )
        if specific_protocol_id and is_valid_uuid(specific_protocol_id):
            proto_query = proto_query.eq("id", specific_protocol_id)

        protocols = proto_query.execute().data or []
        if not protocols:
            return stats

        protocol_ids = [p["id"] for p in protocols]

        # Carrega regras ativas vinculadas aos protocolos e vacinas ativas
        rules = (
            client.table("sanitary_protocol_rules")
            .select("*, vaccines(id, is_active)")
            .in_("protocol_id", protocol_ids)
            .eq("is_active", True)
            .order("min_age_days")
            .execute()
            .data
            or []
        )

        # Carrega agendamentos e aplicações já existentes do animal para evitar duplicação
        existing_schedules = (
            client.table("vaccination_schedules")
            .select("id, protocol_rule_id, vaccine_id, dose_number, status")
            .eq("animal_id", animal_id)
            .execute()
            .data
            or []
        )
        existing_records = (
            client.table("vaccination_records")
            .select("id, vaccine_id, dose_number")
            .eq("animal_id", animal_id)
            .execute()
            .data
            or []
        )
        existing_links = (
            client.table("animal_protocols")
            .select("protocol_id")
            .eq("animal_id", animal_id)
            .execute()
            .data
            or []
        )

        existing_rule_doses = {
            (s["protocol_rule_id"], int(s.get("dose_number", 1)))
            for s in existing_schedules
            if s.get("protocol_rule_id") and s.get("status") != "cancelada"
        }
        applied_vaccine_doses = {
            (r["vaccine_id"], int(r.get("dose_number", 1)))
            for r in existing_records
            if r.get("vaccine_id")
        }
        linked_proto_ids = {lnk["protocol_id"] for lnk in existing_links}

        rules_by_protocol: dict[str, list[dict[str, Any]]] = {}
        for r in rules:
            vac_info = r.get("vaccines") or {}
            if vac_info and vac_info.get("is_active") is False:
                continue
            rules_by_protocol.setdefault(r["protocol_id"], []).append(r)

        today = date.today()
        schedules_to_insert: list[dict[str, Any]] = []
        links_to_insert: list[dict[str, Any]] = []

        animal_species = normalize_species(animal.get("species"))
        norm_age_cat = normalize_age_slug(age_category)

        for proto in protocols:
            proto_species = str(proto.get("target_species") or "todas").strip().lower()
            if proto_species not in ("todas", animal_species):
                continue

            raw_proto_cat = str(proto.get("animal_category") or "todas").lower()
            proto_cat = "todas" if raw_proto_cat == "todas" else normalize_age_slug(raw_proto_cat)
            if proto_cat != "todas" and proto_cat != norm_age_cat:
                continue

            if proto["id"] not in linked_proto_ids:
                links_to_insert.append(
                    {
                        "id": str(uuid.uuid4()),
                        "organization_id": organization_id,
                        "property_id": property_id,
                        "animal_id": animal_id,
                        "protocol_id": proto["id"],
                        "onboarding_mode": animal.get("sanitary_onboarding_mode") or "acompanhamento_nascimento",
                        "reference_date": (animal.get("inclusion_date") or today.isoformat()),
                        "is_active": True,
                    }
                )
                linked_proto_ids.add(proto["id"])

            for rule in rules_by_protocol.get(proto["id"], []):
                dose_num = int(rule.get("dose_number", 1))
                rule_key = (rule["id"], dose_num)
                vac_key = (rule["vaccine_id"], dose_num)

                if rule_key in existing_rule_doses or vac_key in applied_vaccine_doses:
                    stats["skipped_duplicates"] += 1
                    continue

                payload = build_rule_schedule_payload(
                    animal=animal,
                    protocol=proto,
                    rule=rule,
                    age_days=age_days,
                    age_category=age_category,
                    today=today,
                )
                if payload:
                    schedules_to_insert.append(payload)
                    existing_rule_doses.add(rule_key)

        if links_to_insert:
            client.table("animal_protocols").upsert(
                links_to_insert, on_conflict="animal_id,protocol_id"
            ).execute()
            stats["linked_protocols"] = len(links_to_insert)

        if schedules_to_insert:
            client.table("vaccination_schedules").insert(schedules_to_insert).execute()
            stats["created_schedules"] = len(schedules_to_insert)

        return stats
    except Exception as exc:
        err = translate_supabase_error(exc)
        if isinstance(err, MigrationRequiredError):
            return stats
        raise err from exc


def generate_schedules_for_protocol(protocol_id: str) -> dict[str, int]:
    """
    Executa a geração automática de pendências para todos os animais ativos da propriedade
    quando um protocolo sanitário é criado, validado ou atualizado.
    Nunca apaga registros históricos nem aplicações já realizadas.
    """
    totals = {"animals_evaluated": 0, "created_schedules": 0, "skipped_duplicates": 0}
    if not is_valid_uuid(protocol_id):
        return totals

    try:
        client = get_supabase_client()
        proto_res = (
            client.table("sanitary_protocols")
            .select("*")
            .eq("id", protocol_id)
            .limit(1)
            .execute()
        )
        if not proto_res.data:
            return totals

        protocol = proto_res.data[0]
        if not protocol.get("is_active") or not protocol.get("is_validated"):
            return totals

        animals = (
            client.table("animals")
            .select("*")
            .eq("property_id", protocol["property_id"])
            .eq("status", "ativo")
            .execute()
            .data
            or []
        )

        proto_species = str(protocol.get("target_species") or "todas").strip().lower()
        for animal in animals:
            if proto_species != "todas" and normalize_species(animal.get("species")) != proto_species:
                continue
            totals["animals_evaluated"] += 1
            res = generate_schedules_for_animal(animal, specific_protocol_id=protocol_id)
            totals["created_schedules"] += res["created_schedules"]
            totals["skipped_duplicates"] += res["skipped_duplicates"]

        return totals
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def sync_property_schedules(property_id: str | None = None, organization_id: str | None = None) -> dict[str, int]:
    """Sincroniza pendências de todos os animais ativos de uma propriedade ou organização."""
    totals = {"animals_evaluated": 0, "created_schedules": 0, "skipped_duplicates": 0}
    try:
        client = get_supabase_client()
        query = client.table("animals").select("*").eq("status", "ativo")
        if property_id and is_valid_uuid(property_id):
            query = query.eq("property_id", property_id)
        if organization_id and is_valid_uuid(organization_id):
            query = query.eq("organization_id", organization_id)

        animals = query.execute().data or []
        for animal in animals:
            totals["animals_evaluated"] += 1
            res = generate_schedules_for_animal(animal)
            totals["created_schedules"] += res["created_schedules"]
            totals["skipped_duplicates"] += res["skipped_duplicates"]
        return totals
    except Exception as exc:
        raise translate_supabase_error(exc) from exc
