import calendar
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from config import Config
from services.classification_service import (
    enrich_animal_with_age,
    enrich_animals_list,
    normalize_age_slug,
    parse_iso_date,
    summarize_age_categories,
)
from services.management_service import (
    list_management_alerts_safe,
    list_management_records_for_animal_safe,
)
from services.schedule_engine import (
    SCHEDULE_STATUS_META,
    enrich_schedule_status,
    generate_schedules_for_animal,
    generate_schedules_for_protocol,
    sync_dynamic_schedule_statuses,
)
from services.species_service import (
    PREVENTIVE_ITEM_TYPE_META,
    PROPERTY_FOCUS_LABELS,
    PROTOCOL_PURPOSE_LABELS,
    TARGET_SPECIES_LABELS,
    normalize_species,
)
from services.supabase_service import (
    MigrationRequiredError,
    MultiSpeciesMigrationRequiredError,
    SupabaseServiceError,
    get_animal_by_token_or_id,
    get_supabase_client,
    is_valid_uuid,
    translate_supabase_error,
)


HEALTH_RECORD_TYPE_LABELS: dict[str, dict[str, str]] = {
    "tratamento": {"label": "Tratamento", "badge": "bg-primary-subtle text-primary-emphasis", "icon": "bi-capsule"},
    "ocorrencia": {"label": "Ocorrência Sanitária", "badge": "bg-warning-subtle text-warning-emphasis", "icon": "bi-clipboard2-pulse"},
    "observacao_veterinaria": {"label": "Observação Veterinária", "badge": "bg-info-subtle text-info-emphasis", "icon": "bi-journal-medical"},
    "avaliacao_inicial": {"label": "Avaliação Sanitária Inicial", "badge": "bg-success-subtle text-success-emphasis", "icon": "bi-shield-check"},
    "correcao_historico": {"label": "Retificação / Correção", "badge": "bg-secondary-subtle text-secondary-emphasis", "icon": "bi-pencil-square"},
}


# ============================================================================
# 1. Contexto Organizacional, Propriedades, Lotes e Faixas Etárias
# ============================================================================
def get_sanitary_context() -> dict[str, Any]:
    """
    Carrega a organização ativa, propriedades, lotes e faixas etárias configuradas.
    Se a organização padrão ainda não existir (após criar as tabelas), cria-a automaticamente.
    """
    client = get_supabase_client()
    try:
        orgs = client.table("organizations").select("*").eq("is_active", True).order("created_at").execute().data or []
        if not orgs:
            created_org = (
                client.table("organizations")
                .insert({"name": "Agropecuária Animora", "slug": "agropecuaria-animora"})
                .execute()
                .data
            )
            orgs = created_org or []

        organization = orgs[0]
        org_id = organization["id"]

        properties = (
            client.table("properties")
            .select("*")
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .order("name")
            .execute()
            .data
            or []
        )
        if not properties:
            created_prop = (
                client.table("properties")
                .insert(
                    {
                        "organization_id": org_id,
                        "name": "Fazenda Sede Animora",
                        "code": "FAZ-01",
                        "production_focus": "corte",
                    }
                )
                .execute()
                .data
            )
            properties = created_prop or []

        lots = (
            client.table("lots")
            .select("*, properties(id, name)")
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .order("name")
            .execute()
            .data
            or []
        )

        brackets = (
            client.table("age_classifications")
            .select("*")
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .order("sort_order")
            .execute()
            .data
            or Config.DEFAULT_AGE_BRACKETS
        )

        return {
            "organization": organization,
            "organization_id": org_id,
            "properties": properties,
            "lots": lots,
            "age_brackets": brackets,
            "migration_ready": True,
        }
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def get_sanitary_context_safe() -> dict[str, Any]:
    """Versão resiliente usada em rotas compartilhadas antes/depois da migration."""
    try:
        return get_sanitary_context()
    except MigrationRequiredError as exc:
        return {
            "organization": None,
            "organization_id": None,
            "properties": [],
            "lots": [],
            "age_brackets": Config.DEFAULT_AGE_BRACKETS,
            "migration_ready": False,
            "migration_message": str(exc),
        }


def create_property(organization_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Cadastra uma nova propriedade rural multi-espécie vinculada à organização."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise SupabaseServiceError("Informe o nome da propriedade.")
    focus = (payload.get("production_focus") or "misto").strip().lower()
    if focus not in PROPERTY_FOCUS_LABELS:
        focus = "misto"

    record = {
        "id": str(uuid.uuid4()),
        "organization_id": organization_id,
        "name": name,
        "code": (payload.get("code") or "").strip() or None,
        "municipality": (payload.get("municipality") or "").strip() or None,
        "state": ((payload.get("state") or "").strip().upper()[:2]) or None,
        "production_focus": focus,
        "is_active": True,
    }
    try:
        res = get_supabase_client().table("properties").insert(record).execute()
        return res.data[0]
    except Exception as exc:
        err = translate_supabase_error(exc)
        if isinstance(err, MultiSpeciesMigrationRequiredError) and focus not in ("corte", "leite", "misto"):
            fallback_record = {**record, "production_focus": "misto"}
            res_fb = get_supabase_client().table("properties").insert(fallback_record).execute()
            return res_fb.data[0]
        raise err from exc


def create_lot(organization_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Cadastra um novo lote de manejo vinculado a uma propriedade (com filtro opcional por espécie)."""
    property_id = (payload.get("property_id") or "").strip()
    name = (payload.get("name") or "").strip()
    target_species = (payload.get("target_species") or "todas").strip().lower()
    if target_species not in TARGET_SPECIES_LABELS:
        target_species = "todas"

    if not is_valid_uuid(property_id):
        raise SupabaseServiceError("Selecione uma propriedade válida para o lote.")
    if not name:
        raise SupabaseServiceError("Informe o nome do lote.")

    try:
        client = get_supabase_client()
        prop_check = (
            client.table("properties")
            .select("id")
            .eq("id", property_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        if not prop_check.data:
            raise SupabaseServiceError("Propriedade não encontrada nesta organização.")

        base_record = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "property_id": property_id,
            "name": name,
            "description": (payload.get("description") or "").strip() or None,
            "is_active": True,
        }
        full_record = {**base_record, "target_species": target_species}
        try:
            res = client.table("lots").insert(full_record).execute()
            return res.data[0]
        except Exception as inner_exc:
            inner_err = translate_supabase_error(inner_exc)
            if isinstance(inner_err, MultiSpeciesMigrationRequiredError):
                res = client.table("lots").insert(base_record).execute()
                return res.data[0]
            raise inner_err from inner_exc
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def _enrich_vaccine_item(row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    itype = str(enriched.get("item_type") or "vacina").strip().lower()
    meta = PREVENTIVE_ITEM_TYPE_META.get(itype, PREVENTIVE_ITEM_TYPE_META["vacina"])
    tspecies = str(enriched.get("target_species") or "todas").strip().lower()
    enriched["item_type"] = itype
    enriched["item_type_label"] = meta["label"]
    enriched["item_type_badge_class"] = meta["badge_class"]
    enriched["item_type_icon"] = meta["icon"]
    enriched["target_species"] = tspecies if tspecies in TARGET_SPECIES_LABELS else "todas"
    enriched["target_species_label"] = TARGET_SPECIES_LABELS.get(enriched["target_species"], "Todas as espécies")
    return enriched


# ============================================================================
# 2. Catálogo Preventivo: Vacinas, Vermífugos e Exames (`vaccines`)
# ============================================================================
def list_vaccines(
    organization_id: str,
    only_active: bool = False,
    species: str | None = None,
    item_type: str | None = None,
) -> list[dict[str, Any]]:
    clean_sp = (species or "").strip().lower()
    clean_type = (item_type or "").strip().lower()
    try:
        query = (
            get_supabase_client()
            .table("vaccines")
            .select("*")
            .eq("organization_id", organization_id)
            .order("commercial_name")
        )
        if only_active:
            query = query.eq("is_active", True)
        rows = [_enrich_vaccine_item(r) for r in (query.execute().data or [])]
        if clean_sp and clean_sp not in ("todas", "todos"):
            rows = [r for r in rows if r["target_species"] in ("todas", clean_sp)]
        if clean_type and clean_type not in ("todos", "todas"):
            rows = [r for r in rows if r["item_type"] == clean_type]
        return rows
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def get_vaccine(vaccine_id: str, organization_id: str) -> dict[str, Any] | None:
    if not is_valid_uuid(vaccine_id):
        return None
    try:
        res = (
            get_supabase_client()
            .table("vaccines")
            .select("*")
            .eq("id", vaccine_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        return _enrich_vaccine_item(res.data[0]) if res.data else None
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def save_vaccine(organization_id: str, payload: dict[str, Any], vaccine_id: str | None = None) -> dict[str, Any]:
    commercial_name = (payload.get("commercial_name") or "").strip()
    manufacturer = (payload.get("manufacturer") or "").strip()
    administration_route = (payload.get("administration_route") or "").strip()
    dosage_unit = (payload.get("dosage_unit") or "").strip()
    item_type = (payload.get("item_type") or "vacina").strip().lower()
    if item_type not in PREVENTIVE_ITEM_TYPE_META:
        item_type = "vacina"
    target_species = (payload.get("target_species") or "todas").strip().lower()
    if target_species not in TARGET_SPECIES_LABELS:
        target_species = "todas"

    if item_type == "exame_preventivo":
        manufacturer = manufacturer or "Laboratório / Serviço Veterinário"
        administration_route = administration_route or "Coleta Laboratorial / Avaliação"
        dosage_unit = dosage_unit or "exame"

    errors: list[str] = []
    if not commercial_name:
        errors.append("O nome do item preventivo (vacina, vermífugo ou exame) é obrigatório.")
    if not manufacturer:
        errors.append("O fabricante ou laboratório responsável é obrigatório.")
    if not administration_route:
        errors.append("A via de administração / coleta é obrigatória.")
    if not dosage_unit:
        errors.append("A unidade de referência (ex.: mL, g, dose, exame) é obrigatória.")
    if errors:
        raise SupabaseServiceError(" ".join(errors))

    is_active = str(payload.get("is_active", "true")).lower() in ("1", "true", "on", "yes", "ativo")

    base_record: dict[str, Any] = {
        "organization_id": organization_id,
        "commercial_name": commercial_name,
        "manufacturer": manufacturer,
        "description": (payload.get("description") or "").strip() or None,
        "administration_route": administration_route,
        "dosage_unit": dosage_unit,
        "notes": (payload.get("notes") or "").strip() or None,
        "is_active": is_active,
        "updated_at": datetime.now().astimezone().isoformat(),
    }
    full_record = {
        **base_record,
        "item_type": item_type,
        "target_species": target_species,
    }

    try:
        client = get_supabase_client()
        if vaccine_id and is_valid_uuid(vaccine_id):
            res = (
                client.table("vaccines")
                .update(full_record)
                .eq("id", vaccine_id)
                .eq("organization_id", organization_id)
                .execute()
            )
        else:
            full_record["id"] = str(uuid.uuid4())
            res = client.table("vaccines").insert(full_record).execute()
        if not res.data:
            raise SupabaseServiceError("Não foi possível salvar o item no catálogo preventivo.")
        return _enrich_vaccine_item(res.data[0])
    except Exception as exc:
        err = translate_supabase_error(exc)
        if isinstance(err, MultiSpeciesMigrationRequiredError) and item_type == "vacina" and target_species == "todas":
            client = get_supabase_client()
            if vaccine_id and is_valid_uuid(vaccine_id):
                res = client.table("vaccines").update(base_record).eq("id", vaccine_id).eq("organization_id", organization_id).execute()
            else:
                base_record["id"] = str(uuid.uuid4())
                res = client.table("vaccines").insert(base_record).execute()
            if res.data:
                return _enrich_vaccine_item(res.data[0])
        raise err from exc


def toggle_vaccine_status(vaccine_id: str, organization_id: str) -> dict[str, Any]:
    vac = get_vaccine(vaccine_id, organization_id)
    if not vac:
        raise SupabaseServiceError("Vacina não encontrada.")
    try:
        res = (
            get_supabase_client()
            .table("vaccines")
            .update(
                {
                    "is_active": not bool(vac.get("is_active")),
                    "updated_at": datetime.now().astimezone().isoformat(),
                }
            )
            .eq("id", vaccine_id)
            .eq("organization_id", organization_id)
            .execute()
        )
        return res.data[0]
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def _enrich_protocol_item(row: dict[str, Any]) -> dict[str, Any]:
    p = dict(row)
    rules = p.get("sanitary_protocol_rules") or []
    p["rules_count"] = len(rules)
    p["active_rules_count"] = sum(1 for r in rules if r.get("is_active"))
    tspecies = str(p.get("target_species") or "bovino").strip().lower()
    p["target_species"] = tspecies if tspecies in TARGET_SPECIES_LABELS else "bovino"
    p["target_species_label"] = TARGET_SPECIES_LABELS.get(p["target_species"], "Bovinos")
    purpose = str(p.get("purpose") or "geral").strip().lower()
    p["purpose_label"] = PROTOCOL_PURPOSE_LABELS.get(purpose, purpose.title())
    raw_cat = str(p.get("animal_category") or "todas").strip().lower()
    p["animal_category"] = "todas" if raw_cat == "todas" else normalize_age_slug(raw_cat)
    return p


# ============================================================================
# 3. Protocolos Sanitários e Regras (`sanitary_protocols`, `sanitary_protocol_rules`)
# ============================================================================
def list_protocols(
    organization_id: str,
    property_id: str | None = None,
    species: str | None = None,
) -> list[dict[str, Any]]:
    clean_sp = (species or "").strip().lower()
    try:
        client = get_supabase_client()
        query = (
            client.table("sanitary_protocols")
            .select("*, properties(id, name), sanitary_protocol_rules(id, is_active)")
            .eq("organization_id", organization_id)
            .order("created_at", desc=True)
        )
        if property_id and is_valid_uuid(property_id):
            query = query.eq("property_id", property_id)

        rows = [_enrich_protocol_item(p) for p in (query.execute().data or [])]
        if clean_sp and clean_sp not in ("todas", "todos"):
            rows = [p for p in rows if p["target_species"] in ("todas", clean_sp)]
        return rows
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def get_protocol_detail(protocol_id: str, organization_id: str) -> dict[str, Any] | None:
    if not is_valid_uuid(protocol_id):
        return None
    try:
        client = get_supabase_client()
        proto_res = (
            client.table("sanitary_protocols")
            .select("*, properties(id, name, production_focus)")
            .eq("id", protocol_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        if not proto_res.data:
            return None
        protocol = _enrich_protocol_item(proto_res.data[0])
        rules = (
            client.table("sanitary_protocol_rules")
            .select("*, vaccines(*)")
            .eq("protocol_id", protocol_id)
            .order("min_age_days")
            .order("dose_number")
            .execute()
            .data
            or []
        )
        for r in rules:
            if r.get("vaccines"):
                r["vaccines"] = _enrich_vaccine_item(r["vaccines"])
        protocol["rules"] = rules
        return protocol
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def save_protocol(
    organization_id: str,
    payload: dict[str, Any],
    protocol_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    name = (payload.get("name") or "").strip()
    property_id = (payload.get("property_id") or "").strip()
    raw_cat = (payload.get("animal_category") or "todas").strip().lower()
    animal_category = "todas" if raw_cat == "todas" else normalize_age_slug(raw_cat)
    purpose = (payload.get("purpose") or "geral").strip().lower()
    target_species = (payload.get("target_species") or "bovino").strip().lower()
    if target_species not in TARGET_SPECIES_LABELS:
        target_species = "bovino"
    validated_by = (payload.get("validated_by") or "").strip()
    is_validated = str(payload.get("is_validated", "")).lower() in ("1", "true", "on", "yes")
    is_active = str(payload.get("is_active", "true")).lower() in ("1", "true", "on", "yes")

    errors: list[str] = []
    if not name:
        errors.append("Informe o nome do protocolo sanitário.")
    if not is_valid_uuid(property_id):
        errors.append("Selecione a propriedade à qual o protocolo pertence.")
    if animal_category not in ("todas", "recem_nascido", "lactente", "jovem", "adulto"):
        errors.append("Selecione uma faixa etária válida.")
    if purpose not in PROTOCOL_PURPOSE_LABELS:
        errors.append("Selecione uma finalidade válida para o protocolo.")
    if is_validated and not validated_by:
        errors.append("Para validar o protocolo, informe o nome/registro do Responsável Técnico ou Produtor responsável.")
    if errors:
        raise SupabaseServiceError(" ".join(errors))

    try:
        client = get_supabase_client()
        prop_check = (
            client.table("properties")
            .select("id")
            .eq("id", property_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        if not prop_check.data:
            raise SupabaseServiceError("A propriedade informada não pertence à organização ativa.")

        now_iso = datetime.now().astimezone().isoformat()
        base_record: dict[str, Any] = {
            "organization_id": organization_id,
            "property_id": property_id,
            "name": name,
            "description": (payload.get("description") or "").strip() or None,
            "animal_category": animal_category,
            "purpose": purpose,
            "validated_by": validated_by or None,
            "is_validated": is_validated,
            "validated_at": now_iso if is_validated else None,
            "is_active": is_active,
            "updated_at": now_iso,
        }
        full_record = {**base_record, "target_species": target_species}

        try:
            if protocol_id and is_valid_uuid(protocol_id):
                res = (
                    client.table("sanitary_protocols")
                    .update(full_record)
                    .eq("id", protocol_id)
                    .eq("organization_id", organization_id)
                    .execute()
                )
            else:
                full_record["id"] = str(uuid.uuid4())
                res = client.table("sanitary_protocols").insert(full_record).execute()
        except Exception as inner_exc:
            inner_err = translate_supabase_error(inner_exc)
            if isinstance(inner_err, MultiSpeciesMigrationRequiredError) and target_species == "bovino":
                legacy_rec = {
                    **base_record,
                    "animal_category": "bezerro" if animal_category == "lactente" else animal_category,
                    "purpose": purpose if purpose in ("corte", "leite") else "corte",
                }
                if protocol_id and is_valid_uuid(protocol_id):
                    res = client.table("sanitary_protocols").update(legacy_rec).eq("id", protocol_id).eq("organization_id", organization_id).execute()
                else:
                    legacy_rec["id"] = str(uuid.uuid4())
                    res = client.table("sanitary_protocols").insert(legacy_rec).execute()
            else:
                raise inner_err from inner_exc

        if not res.data:
            raise SupabaseServiceError("Não foi possível salvar o protocolo sanitário.")

        saved = _enrich_protocol_item(res.data[0])
        sync_stats = {"animals_evaluated": 0, "created_schedules": 0, "skipped_duplicates": 0}
        if saved.get("is_active") and saved.get("is_validated"):
            sync_stats = generate_schedules_for_protocol(saved["id"])

        return saved, sync_stats
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def add_protocol_rule(
    organization_id: str,
    protocol_id: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, int]]:
    protocol = get_protocol_detail(protocol_id, organization_id)
    if not protocol:
        raise SupabaseServiceError("Protocolo sanitário não encontrado.")

    vaccine_id = (payload.get("vaccine_id") or "").strip()
    if not is_valid_uuid(vaccine_id):
        raise SupabaseServiceError("Selecione uma vacina do catálogo para a regra.")

    vac = get_vaccine(vaccine_id, organization_id)
    if not vac:
        raise SupabaseServiceError("A vacina selecionada não pertence ao catálogo desta organização.")

    try:
        min_age_days = int(payload.get("min_age_days", ""))
        max_age_days = int(payload.get("max_age_days", ""))
        dose_number = int(payload.get("dose_number", "1"))
    except ValueError as exc:
        raise SupabaseServiceError("Informe números inteiros válidos para idades mínima/máxima (em dias) e dose.") from exc

    if min_age_days < 0:
        raise SupabaseServiceError("A idade mínima não pode ser negativa.")
    if max_age_days < min_age_days:
        raise SupabaseServiceError("A idade máxima (em dias) deve ser maior ou igual à idade mínima.")
    if dose_number < 1:
        raise SupabaseServiceError("O número da dose deve ser no mínimo 1.")

    booster_raw = (payload.get("booster_interval_days") or "").strip()
    booster_interval_days: int | None = None
    if booster_raw:
        try:
            booster_interval_days = int(booster_raw)
            if booster_interval_days <= 0:
                raise SupabaseServiceError("O intervalo para próxima dose deve ser maior que zero.")
        except ValueError as exc:
            raise SupabaseServiceError("Informe um número inteiro de dias válido para o intervalo da próxima dose.") from exc

    is_active = str(payload.get("is_active", "true")).lower() in ("1", "true", "on", "yes")

    record = {
        "id": str(uuid.uuid4()),
        "organization_id": organization_id,
        "protocol_id": protocol_id,
        "vaccine_id": vaccine_id,
        "min_age_days": min_age_days,
        "max_age_days": max_age_days,
        "dose_number": dose_number,
        "booster_interval_days": booster_interval_days,
        "notes": (payload.get("notes") or "").strip() or None,
        "is_active": is_active,
    }

    try:
        res = get_supabase_client().table("sanitary_protocol_rules").insert(record).execute()
        saved_rule = res.data[0]
        sync_stats = {"animals_evaluated": 0, "created_schedules": 0, "skipped_duplicates": 0}
        if protocol.get("is_active") and protocol.get("is_validated") and is_active:
            sync_stats = generate_schedules_for_protocol(protocol_id)
        return saved_rule, sync_stats
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def toggle_protocol_rule_status(rule_id: str, organization_id: str) -> dict[str, Any]:
    """Ativa ou inativa uma regra sem apagar agendamentos históricos ou aplicações já realizadas."""
    if not is_valid_uuid(rule_id):
        raise SupabaseServiceError("Regra inválida.")
    try:
        client = get_supabase_client()
        found = (
            client.table("sanitary_protocol_rules")
            .select("*")
            .eq("id", rule_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        if not found.data:
            raise SupabaseServiceError("Regra não encontrada.")
        rule = found.data[0]
        new_active = not bool(rule.get("is_active"))
        res = (
            client.table("sanitary_protocol_rules")
            .update({"is_active": new_active, "updated_at": datetime.now().astimezone().isoformat()})
            .eq("id", rule_id)
            .execute()
        )
        if new_active:
            generate_schedules_for_protocol(rule["protocol_id"])
        return res.data[0]
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


# ============================================================================
# 4. Campanhas de Vacinação e Cartelas (`vaccination_campaigns`)
# ============================================================================
def create_campaign_with_schedules(
    organization_id: str,
    payload: dict[str, Any],
    selected_animal_ids: list[str],
) -> tuple[dict[str, Any], int]:
    """
    Cria uma campanha de vacinação (seleção por lote ou manual), valida rigorosamente
    a propriedade de todos os animais e gera um agendamento independente por animal.
    """
    name = (payload.get("name") or "").strip()
    vaccine_id = (payload.get("vaccine_id") or "").strip()
    property_id = (payload.get("property_id") or "").strip()
    lot_id = (payload.get("lot_id") or "").strip() or None
    selection_mode = (payload.get("selection_mode") or "lote").strip().lower()
    scheduled_date_str = (payload.get("scheduled_date") or "").strip()

    errors: list[str] = []
    if not name:
        errors.append("Informe o nome da campanha.")
    if not is_valid_uuid(property_id):
        errors.append("Selecione uma propriedade válida.")
    if not is_valid_uuid(vaccine_id):
        errors.append("Selecione a vacina da campanha.")
    scheduled_dt = parse_iso_date(scheduled_date_str)
    if not scheduled_dt:
        errors.append("Informe uma data prevista válida para a campanha.")
    if selection_mode not in ("lote", "manual"):
        errors.append("Modalidade de seleção inválida.")
    if selection_mode == "lote" and not is_valid_uuid(lot_id):
        errors.append("Selecione o lote para buscar os animais da campanha.")
    if errors:
        raise SupabaseServiceError(" ".join(errors))

    try:
        client = get_supabase_client()

        # Valida propriedade e vacina dentro da organização
        prop = (
            client.table("properties")
            .select("id, name")
            .eq("id", property_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
            .data
        )
        if not prop:
            raise SupabaseServiceError("Propriedade inválida para esta organização.")

        vac = get_vaccine(vaccine_id, organization_id)
        if not vac or not vac.get("is_active"):
            raise SupabaseServiceError("Selecione um item preventivo ativo do catálogo.")

        vac_species = str(vac.get("target_species") or "todas").strip().lower()
        target_animals: list[dict[str, Any]] = []

        if selection_mode == "lote":
            lot_check = (
                client.table("lots")
                .select("*")
                .eq("id", lot_id)
                .eq("property_id", property_id)
                .limit(1)
                .execute()
                .data
            )
            if not lot_check:
                raise SupabaseServiceError("O lote selecionado não pertence à propriedade informada.")

            lot_animals = (
                client.table("animals")
                .select("*")
                .eq("property_id", property_id)
                .eq("lot_id", lot_id)
                .eq("status", "ativo")
                .execute()
                .data
                or []
            )
            if vac_species not in ("", "todas"):
                lot_animals = [a for a in lot_animals if normalize_species(a.get("species")) == vac_species]

            if selected_animal_ids:
                clean_selected = {aid.strip() for aid in selected_animal_ids if is_valid_uuid(aid)}
                target_animals = [a for a in lot_animals if a["id"] in clean_selected]
            else:
                target_animals = lot_animals
        else:
            lot_id = None
            clean_ids = list({aid.strip() for aid in selected_animal_ids if is_valid_uuid(aid)})
            if not clean_ids:
                raise SupabaseServiceError("Selecione ao menos um animal para criar a campanha manual.")

            fetched = (
                client.table("animals")
                .select("*")
                .in_("id", clean_ids)
                .execute()
                .data
                or []
            )
            if len(fetched) != len(clean_ids):
                raise SupabaseServiceError("Um ou mais animais selecionados não existem no cadastro.")

            # Regra 14: Validar a propriedade e a espécie dos animais antes de adicioná-los a uma campanha
            wrong_prop = [a["ear_tag"] for a in fetched if a.get("property_id") != property_id]
            if wrong_prop:
                raise SupabaseServiceError(
                    f"Os seguintes animais não pertencem à propriedade selecionada: {', '.join(wrong_prop)}."
                )
            if vac_species not in ("", "todas"):
                wrong_sp = [a["ear_tag"] for a in fetched if normalize_species(a.get("species")) != vac_species]
                if wrong_sp:
                    raise SupabaseServiceError(
                        f"O item '{vac['commercial_name']}' é exclusivo para {vac['target_species_label']}. "
                        f"Incompatíveis: {', '.join(wrong_sp)}."
                    )
            inactive = [a["ear_tag"] for a in fetched if a.get("status", "ativo") != "ativo"]
            if inactive:
                raise SupabaseServiceError(
                    f"Apenas animais ativos podem participar da campanha. Inativos: {', '.join(inactive)}."
                )
            target_animals = fetched

        if not target_animals:
            raise SupabaseServiceError("Nenhum animal ativo encontrado para gerar os agendamentos da campanha.")

        campaign_id = str(uuid.uuid4())
        campaign_record = {
            "id": campaign_id,
            "organization_id": organization_id,
            "property_id": property_id,
            "lot_id": lot_id,
            "vaccine_id": vaccine_id,
            "selection_mode": selection_mode,
            "name": name,
            "scheduled_date": scheduled_dt.isoformat(),
            "description": (payload.get("description") or "").strip() or None,
            "notes": (payload.get("notes") or "").strip() or None,
            "status": "programada",
        }
        created_camp = client.table("vaccination_campaigns").insert(campaign_record).execute().data[0]

        today = date.today()
        initial_status = (
            "proxima_aplicacao"
            if scheduled_dt > today
            else ("atrasada" if scheduled_dt < today else "pendente")
        )

        schedule_rows = [
            {
                "id": str(uuid.uuid4()),
                "organization_id": organization_id,
                "property_id": property_id,
                "animal_id": animal["id"],
                "vaccine_id": vaccine_id,
                "protocol_id": None,
                "protocol_rule_id": None,
                "campaign_id": campaign_id,
                "origin_type": "campanha",
                "dose_number": 1,
                "scheduled_date": scheduled_dt.isoformat(),
                "window_end_date": scheduled_dt.isoformat(),
                "status": initial_status,
                "notes": f"Campanha: {name}",
            }
            for animal in target_animals
        ]

        client.table("vaccination_schedules").insert(schedule_rows).execute()
        return created_camp, len(schedule_rows)
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def _compute_cartela_metrics(schedules: list[dict[str, Any]]) -> dict[str, Any]:
    active_items = [s for s in schedules if s.get("status") != "cancelada"]
    total = len(active_items)
    applied = sum(1 for s in active_items if s.get("status") == "aplicada")
    overdue = sum(1 for s in active_items if s.get("status") == "atrasada")
    pending = sum(1 for s in active_items if s.get("status") in ("pendente", "proxima_aplicacao"))
    not_done = sum(1 for s in active_items if s.get("status") == "nao_realizada")
    pct = round((applied / total) * 100, 1) if total > 0 else 0.0
    return {
        "total_animals": total,
        "applied_count": applied,
        "pending_count": pending,
        "overdue_count": overdue,
        "not_done_count": not_done,
        "completion_pct": pct,
    }


def list_campaign_cartelas(
    organization_id: str,
    property_id: str | None = None,
) -> list[dict[str, Any]]:
    """Lista todas as cartelas (campanhas) com indicadores reais de andamento."""
    try:
        client = get_supabase_client()
        query = (
            client.table("vaccination_campaigns")
            .select("*, properties(id, name), lots(id, name), vaccines(id, commercial_name, manufacturer, dosage_unit, administration_route)")
            .eq("organization_id", organization_id)
            .order("scheduled_date", desc=True)
        )
        if property_id and is_valid_uuid(property_id):
            query = query.eq("property_id", property_id)

        campaigns = query.execute().data or []
        if not campaigns:
            return []

        camp_ids = [c["id"] for c in campaigns]
        raw_schedules = (
            client.table("vaccination_schedules")
            .select("id, campaign_id, scheduled_date, window_end_date, status")
            .in_("campaign_id", camp_ids)
            .execute()
            .data
            or []
        )
        synced_schedules = sync_dynamic_schedule_statuses(raw_schedules, persist_changes=True)

        by_campaign: dict[str, list[dict[str, Any]]] = {}
        for s in synced_schedules:
            by_campaign.setdefault(s["campaign_id"], []).append(s)

        for camp in campaigns:
            metrics = _compute_cartela_metrics(by_campaign.get(camp["id"], []))
            camp.update(metrics)

        return campaigns
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def get_campaign_cartela_detail(
    campaign_id: str,
    organization_id: str,
    age_brackets: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Retorna os dados completos de uma cartela de vacinação e seus agendamentos individuais."""
    if not is_valid_uuid(campaign_id):
        return None
    try:
        client = get_supabase_client()
        camp_res = (
            client.table("vaccination_campaigns")
            .select("*, properties(id, name), lots(id, name), vaccines(id, commercial_name, manufacturer, dosage_unit, administration_route)")
            .eq("id", campaign_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        if not camp_res.data:
            return None

        campaign = camp_res.data[0]
        raw_schedules = (
            client.table("vaccination_schedules")
            .select("*, animals(id, ear_tag, name, sex, breed, birth_date, qr_code_token, lot_id, lots(id, name))")
            .eq("campaign_id", campaign_id)
            .order("created_at")
            .execute()
            .data
            or []
        )
        schedules = sync_dynamic_schedule_statuses(raw_schedules, persist_changes=True)

        records = (
            client.table("vaccination_records")
            .select("*")
            .eq("campaign_id", campaign_id)
            .order("applied_at", desc=True)
            .execute()
            .data
            or []
        )
        record_by_schedule: dict[str, dict[str, Any]] = {}
        for rec in records:
            if rec.get("schedule_id") and rec["schedule_id"] not in record_by_schedule:
                record_by_schedule[rec["schedule_id"]] = rec

        for sched in schedules:
            if sched.get("animals"):
                sched["animal"] = enrich_animal_with_age(sched["animals"], brackets=age_brackets)
            else:
                sched["animal"] = {}
            sched["application_record"] = record_by_schedule.get(sched["id"])

        schedules.sort(key=lambda item: (item.get("animal", {}).get("ear_tag") or ""))
        campaign.update(_compute_cartela_metrics(schedules))
        campaign["schedules"] = schedules
        return campaign
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def refresh_campaign_status(campaign_id: str) -> None:
    """Atualiza consistentemente o status geral da campanha conforme o progresso individual."""
    if not campaign_id or not is_valid_uuid(campaign_id):
        return
    try:
        client = get_supabase_client()
        schedules = (
            client.table("vaccination_schedules")
            .select("status")
            .eq("campaign_id", campaign_id)
            .execute()
            .data
            or []
        )
        metrics = _compute_cartela_metrics(schedules)
        total = metrics["total_animals"]
        applied = metrics["applied_count"]

        if total > 0 and applied == total:
            new_status = "concluida"
        elif applied > 0:
            new_status = "em_andamento"
        else:
            new_status = "programada"

        client.table("vaccination_campaigns").update(
            {"status": new_status, "updated_at": datetime.now().astimezone().isoformat()}
        ).eq("id", campaign_id).execute()
    except Exception:
        pass


# ============================================================================
# 5. Confirmação e Registro Individual de Vacinação (`vaccination_records`)
# ============================================================================
def confirm_vaccination_application(
    organization_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Registra uma aplicação efetiva de vacina de forma permanente no histórico do animal,
    atualizando o agendamento correspondente (se houver) e gerando reforço futuro quando aplicável.
    Nunca sobrescreve aplicações anteriores.
    """
    animal_id = (payload.get("animal_id") or "").strip()
    vaccine_id = (payload.get("vaccine_id") or "").strip()
    schedule_id = (payload.get("schedule_id") or "").strip() or None
    applied_at_raw = (payload.get("applied_at") or "").strip()
    dosage_raw = (payload.get("dosage") or "").strip().replace(",", ".")
    dosage_unit = (payload.get("dosage_unit") or "").strip()
    administration_route = (payload.get("administration_route") or "").strip()
    manufacturer = (payload.get("manufacturer") or "").strip()
    product_batch = (payload.get("product_batch") or "").strip()
    product_expiry_raw = (payload.get("product_expiry") or "").strip()
    exam_result = (payload.get("exam_result") or "").strip()[:100] or None
    applied_by = (payload.get("applied_by") or "").strip()
    next_dose_raw = (payload.get("next_dose_date") or "").strip()
    is_historical = str(payload.get("is_historical_record", "false")).lower() in ("1", "true", "on", "yes")
    notes = (payload.get("notes") or "").strip() or None

    vac_preview = get_vaccine(vaccine_id, organization_id) if is_valid_uuid(vaccine_id) else None
    is_exam_item = bool(vac_preview and vac_preview.get("item_type") == "exame_preventivo")
    if is_exam_item and not dosage_raw:
        dosage_raw = "1"

    errors: list[str] = []
    if not is_valid_uuid(animal_id):
        errors.append("Animal inválido para registro sanitário.")
    if not is_valid_uuid(vaccine_id):
        errors.append("Selecione um item válido do catálogo preventivo.")

    dosage: float = 0.0
    try:
        dosage = round(float(dosage_raw), 2)
        if is_exam_item:
            if dosage < 0 or dosage > 1000:
                errors.append("Informe uma quantidade válida.")
        elif dosage <= 0 or dosage > 1000:
            errors.append("Informe uma dosagem numérica maior que zero.")
    except ValueError:
        errors.append("Informe um valor numérico válido para a dosagem / quantidade.")

    if not dosage_unit:
        errors.append("Informe a unidade (ex.: mL, g, dose, exame).")
    if not administration_route:
        errors.append("Informe a via de administração / coleta.")
    if not manufacturer:
        errors.append("Informe o fabricante ou laboratório.")
    if not is_historical and not is_exam_item and not product_batch:
        errors.append("Informe o número do lote do produto aplicado.")
    if not applied_by:
        errors.append("Informe o responsável pela aplicação / realização.")

    applied_dt: datetime | None = None
    if not applied_at_raw:
        errors.append("Informe a data e o horário da aplicação.")
    else:
        try:
            if len(applied_at_raw) == 10:
                parsed_d = datetime.strptime(applied_at_raw, "%Y-%m-%d")
                applied_dt = parsed_d.astimezone()
            else:
                applied_dt = datetime.fromisoformat(applied_at_raw).astimezone()
            if applied_dt > datetime.now().astimezone() + timedelta(minutes=10):
                errors.append("A data/horário da aplicação não pode estar no futuro.")
        except ValueError:
            errors.append("Formato inválido para data e horário da aplicação.")

    product_expiry_dt = parse_iso_date(product_expiry_raw) if product_expiry_raw else None
    if product_expiry_raw and not product_expiry_dt:
        errors.append("Informe uma data de validade do produto válida.")
    if product_expiry_dt and applied_dt and not is_historical and product_expiry_dt < applied_dt.date():
        errors.append("Atenção: a validade informada do produto está vencida na data da aplicação.")

    next_dose_dt = parse_iso_date(next_dose_raw) if next_dose_raw else None
    if next_dose_raw and not next_dose_dt:
        errors.append("Informe uma data válida para a próxima dose.")
    if next_dose_dt and applied_dt and next_dose_dt <= applied_dt.date():
        errors.append("A data da próxima dose deve ser posterior à data da aplicação atual.")

    if errors:
        raise SupabaseServiceError(" ".join(errors))

    try:
        client = get_supabase_client()

        # Regra 14: Impedir aplicações vinculadas a animais inexistentes
        animal_res = (
            client.table("animals")
            .select("*")
            .eq("id", animal_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
            .data
        )
        if not animal_res:
            raise SupabaseServiceError("Animal inexistente ou pertencente a outra organização.")
        animal = animal_res[0]
        property_id = animal.get("property_id")
        if not property_id:
            raise SupabaseServiceError("O animal precisa estar vinculado a uma propriedade.")

        vac = get_vaccine(vaccine_id, organization_id)
        if not vac:
            raise SupabaseServiceError("Vacina não encontrada no catálogo.")

        schedule_row: dict[str, Any] | None = None
        dose_number = int(payload.get("dose_number") or 1)
        campaign_id: str | None = None

        if schedule_id:
            if not is_valid_uuid(schedule_id):
                raise SupabaseServiceError("Agendamento informado inválido.")
            sched_res = (
                client.table("vaccination_schedules")
                .select("*, sanitary_protocol_rules(id, booster_interval_days)")
                .eq("id", schedule_id)
                .eq("organization_id", organization_id)
                .limit(1)
                .execute()
                .data
            )
            if not sched_res:
                raise SupabaseServiceError("Agendamento de vacinação não encontrado.")
            schedule_row = sched_res[0]

            # Garante consistência estrita entre agendamento e aplicação
            if schedule_row["animal_id"] != animal_id:
                raise SupabaseServiceError("Inconsistência: o agendamento pertence a outro animal.")
            if schedule_row["status"] == "aplicada":
                raise SupabaseServiceError(
                    "Este agendamento já possui aplicação confirmada. Não é permitido sobrescrever aplicações."
                )

            vaccine_id = schedule_row["vaccine_id"]
            dose_number = int(schedule_row.get("dose_number") or 1)
            campaign_id = schedule_row.get("campaign_id")

            # Calcula próxima dose automaticamente pelo intervalo da regra se não preenchida manualmente
            rule_info = schedule_row.get("sanitary_protocol_rules") or {}
            booster_days = rule_info.get("booster_interval_days")
            if not next_dose_dt and booster_days and applied_dt:
                next_dose_dt = applied_dt.date() + timedelta(days=int(booster_days))

        # Se informou histórico conhecido para um adulto com histórico desconhecido, atualiza modo se desejado
        record_id = str(uuid.uuid4())
        applied_iso = applied_dt.isoformat() if applied_dt else datetime.now().astimezone().isoformat()

        base_record_payload = {
            "id": record_id,
            "organization_id": organization_id,
            "property_id": property_id,
            "animal_id": animal_id,
            "vaccine_id": vaccine_id,
            "schedule_id": schedule_id,
            "campaign_id": campaign_id,
            "dose_number": max(1, dose_number),
            "applied_at": applied_iso,
            "dosage": dosage,
            "dosage_unit": dosage_unit,
            "administration_route": administration_route,
            "manufacturer": manufacturer,
            "product_batch": product_batch or None,
            "product_expiry": product_expiry_dt.isoformat() if product_expiry_dt else None,
            "applied_by": applied_by,
            "next_dose_date": next_dose_dt.isoformat() if next_dose_dt else None,
            "is_historical_record": is_historical,
            "notes": notes,
        }
        full_record_payload = {
            **base_record_payload,
            **({"exam_result": exam_result} if exam_result else {}),
        }

        try:
            inserted = client.table("vaccination_records").insert(full_record_payload).execute()
        except Exception as rec_exc:
            rec_err = translate_supabase_error(rec_exc)
            if isinstance(rec_err, MultiSpeciesMigrationRequiredError):
                fallback_notes = f"Resultado: {exam_result}" + (f" | {notes}" if notes else "") if exam_result else notes
                fallback_payload = {
                    **base_record_payload,
                    "dosage": max(0.01, dosage),
                    "notes": fallback_notes,
                }
                inserted = client.table("vaccination_records").insert(fallback_payload).execute()
            else:
                raise rec_err from rec_exc

        if not inserted.data:
            raise SupabaseServiceError("Falha ao gravar o registro permanente na Carteira Sanitária.")
        saved_record = inserted.data[0]

        # Atualiza agendamento vinculado de forma consistente
        if schedule_row:
            client.table("vaccination_schedules").update(
                {
                    "status": "aplicada",
                    "completed_at": applied_iso,
                    "updated_at": datetime.now().astimezone().isoformat(),
                }
            ).eq("id", schedule_row["id"]).execute()

            if campaign_id:
                refresh_campaign_status(campaign_id)

        # Gera agendamento individual de reforço/próxima dose quando aplicável (evitando duplicidade)
        if next_dose_dt and not is_historical:
            next_dose_num = max(1, dose_number) + 1
            existing_booster = (
                client.table("vaccination_schedules")
                .select("id")
                .eq("animal_id", animal_id)
                .eq("vaccine_id", vaccine_id)
                .eq("dose_number", next_dose_num)
                .neq("status", "cancelada")
                .limit(1)
                .execute()
                .data
            )
            if not existing_booster:
                today = date.today()
                b_status = "proxima_aplicacao" if next_dose_dt > today else "pendente"
                client.table("vaccination_schedules").insert(
                    {
                        "id": str(uuid.uuid4()),
                        "organization_id": organization_id,
                        "property_id": property_id,
                        "animal_id": animal_id,
                        "vaccine_id": vaccine_id,
                        "protocol_id": schedule_row.get("protocol_id") if schedule_row else None,
                        "protocol_rule_id": None,
                        "campaign_id": None,
                        "origin_type": "reforco",
                        "dose_number": next_dose_num,
                        "scheduled_date": next_dose_dt.isoformat(),
                        "window_end_date": (next_dose_dt + timedelta(days=7)).isoformat(),
                        "status": b_status,
                        "notes": f"Próxima dose ({next_dose_num}ª dose) agendada após aplicação em {applied_dt.strftime('%d/%m/%Y') if applied_dt else ''}.",
                    }
                ).execute()

        return saved_record
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def update_schedule_status_with_audit(
    organization_id: str,
    schedule_id: str,
    new_status: str,
    reason: str,
    operator_name: str,
) -> dict[str, Any]:
    """
    Atualiza um agendamento para Não realizada, Histórico desconhecido ou Cancelada,
    registrando obrigatoriamente a justificativa no histórico sanitário do animal.
    Nunca permite marcar 'aplicada' sem o formulário completo de aplicação!
    """
    allowed = {"nao_realizada", "historico_desconhecido", "cancelada", "pendente"}
    clean_status = (new_status or "").strip().lower()
    clean_reason = (reason or "").strip()

    if clean_status not in allowed:
        raise SupabaseServiceError(
            "Status inválido. Para confirmar uma aplicação, utilize o registro completo de vacinação."
        )
    if not clean_reason:
        raise SupabaseServiceError("Informe o motivo/justificativa para registrar esta alteração no histórico.")
    if not is_valid_uuid(schedule_id):
        raise SupabaseServiceError("Agendamento inválido.")

    try:
        client = get_supabase_client()
        sched_res = (
            client.table("vaccination_schedules")
            .select("*, vaccines(commercial_name)")
            .eq("id", schedule_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
            .data
        )
        if not sched_res:
            raise SupabaseServiceError("Agendamento não encontrado.")
        sched = sched_res[0]
        if sched.get("status") == "aplicada":
            raise SupabaseServiceError(
                "Agendamentos com vacina já aplicada fazem parte do histórico permanente e não podem ser desfeitos. "
                "Utilize uma nota de retificação se necessário."
            )

        updated = (
            client.table("vaccination_schedules")
            .update(
                {
                    "status": clean_status,
                    "status_reason": clean_reason,
                    "updated_at": datetime.now().astimezone().isoformat(),
                }
            )
            .eq("id", schedule_id)
            .execute()
            .data[0]
        )

        if sched.get("campaign_id"):
            refresh_campaign_status(sched["campaign_id"])

        vac_name = (sched.get("vaccines") or {}).get("commercial_name", "Vacina")
        status_label = SCHEDULE_STATUS_META.get(clean_status, {}).get("label", clean_status)

        # Registra a alteração no histórico auditável do animal
        client.table("health_records").insert(
            {
                "id": str(uuid.uuid4()),
                "organization_id": organization_id,
                "property_id": sched["property_id"],
                "animal_id": sched["animal_id"],
                "related_schedule_id": schedule_id,
                "record_type": "correcao_historico",
                "title": f"Agendamento atualizado para '{status_label}' — {vac_name}",
                "description": clean_reason,
                "occurred_at": datetime.now().astimezone().isoformat(),
                "veterinarian_or_responsible": operator_name or "Operador Animora",
                "is_private": True,
            }
        ).execute()

        return updated
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


# ============================================================================
# 6. Registros Clínicos / Ocorrências / Observações / Retificações (`health_records`)
# ============================================================================
def create_health_record(organization_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    animal_id = (payload.get("animal_id") or "").strip()
    record_type = (payload.get("record_type") or "").strip().lower()
    title = (payload.get("title") or "").strip()
    description = (payload.get("description") or "").strip()
    occurred_raw = (payload.get("occurred_at") or "").strip()

    if not is_valid_uuid(animal_id):
        raise SupabaseServiceError("Animal inválido para registro sanitário.")
    if record_type not in HEALTH_RECORD_TYPE_LABELS:
        raise SupabaseServiceError("Selecione um tipo de registro sanitário válido.")
    if not title:
        raise SupabaseServiceError("Informe um título resumido para o registro.")
    if not description:
        raise SupabaseServiceError("Descreva os detalhes da ocorrência, tratamento ou observação.")

    occurred_iso = datetime.now().astimezone().isoformat()
    if occurred_raw:
        try:
            if len(occurred_raw) == 10:
                occurred_iso = datetime.strptime(occurred_raw, "%Y-%m-%d").astimezone().isoformat()
            else:
                occurred_iso = datetime.fromisoformat(occurred_raw).astimezone().isoformat()
        except ValueError as exc:
            raise SupabaseServiceError("Informe uma data/hora válida para o registro sanitário.") from exc

    try:
        client = get_supabase_client()
        animal_res = (
            client.table("animals")
            .select("id, property_id")
            .eq("id", animal_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
            .data
        )
        if not animal_res:
            raise SupabaseServiceError("Animal não encontrado nesta organização.")

        rel_vac_id = (payload.get("related_vaccination_record_id") or "").strip() or None
        if rel_vac_id and not is_valid_uuid(rel_vac_id):
            rel_vac_id = None

        record = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "property_id": animal_res[0]["property_id"],
            "animal_id": animal_id,
            "related_vaccination_record_id": rel_vac_id,
            "record_type": record_type,
            "title": title,
            "description": description,
            "occurred_at": occurred_iso,
            "veterinarian_or_responsible": (payload.get("veterinarian_or_responsible") or "").strip() or None,
            "medication_applied": (payload.get("medication_applied") or "").strip() or None,
            "dosage_info": (payload.get("dosage_info") or "").strip() or None,
            "is_private": True,
            "notes": (payload.get("notes") or "").strip() or None,
        }

        res = client.table("health_records").insert(record).execute()
        return res.data[0]
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


# ============================================================================
# 7. Carteira Sanitária Individual e Linha do Tempo (`animal_detail`)
# ============================================================================
def get_animal_sanitary_card(
    animal: dict[str, Any],
    organization_id: str | None = None,
) -> dict[str, Any]:
    """
    Monta todos os blocos da Carteira Sanitária Individual do animal,
    incluindo linha do tempo cronológica completa.
    """
    empty_card = {
        "applied_records": [],
        "pending_schedules": [],
        "upcoming_schedules": [],
        "overdue_schedules": [],
        "unknown_or_other_schedules": [],
        "treatments": [],
        "occurrences": [],
        "vet_notes": [],
        "linked_protocols": [],
        "timeline": [],
    }
    animal_id = animal.get("id")
    if not animal_id or not is_valid_uuid(animal_id):
        return empty_card

    try:
        client = get_supabase_client()

        raw_schedules = (
            client.table("vaccination_schedules")
            .select(
                "*, vaccines(*), "
                "sanitary_protocols(id, name), vaccination_campaigns(id, name)"
            )
            .eq("animal_id", animal_id)
            .order("scheduled_date")
            .execute()
            .data
            or []
        )
        for s in raw_schedules:
            if s.get("vaccines"):
                s["vaccines"] = _enrich_vaccine_item(s["vaccines"])
        schedules = sync_dynamic_schedule_statuses(raw_schedules, persist_changes=True)

        applied_records = (
            client.table("vaccination_records")
            .select("*, vaccines(*), vaccination_campaigns(id, name)")
            .eq("animal_id", animal_id)
            .order("applied_at", desc=True)
            .execute()
            .data
            or []
        )
        for r in applied_records:
            if r.get("vaccines"):
                r["vaccines"] = _enrich_vaccine_item(r["vaccines"])

        health_records = (
            client.table("health_records")
            .select("*")
            .eq("animal_id", animal_id)
            .order("occurred_at", desc=True)
            .execute()
            .data
            or []
        )

        linked_protocols = (
            client.table("animal_protocols")
            .select("*, sanitary_protocols(id, name, purpose, animal_category, validated_by, is_active)")
            .eq("animal_id", animal_id)
            .execute()
            .data
            or []
        )

        pending_schedules = [s for s in schedules if s["status"] == "pendente"]
        upcoming_schedules = [s for s in schedules if s["status"] == "proxima_aplicacao"]
        overdue_schedules = [s for s in schedules if s["status"] == "atrasada"]
        unknown_or_other = [
            s for s in schedules if s["status"] in ("historico_desconhecido", "nao_realizada", "cancelada")
        ]

        treatments = [h for h in health_records if h.get("record_type") == "tratamento"]
        occurrences = [h for h in health_records if h.get("record_type") in ("ocorrencia", "avaliacao_inicial")]
        vet_notes = [h for h in health_records if h.get("record_type") in ("observacao_veterinaria", "correcao_historico")]

        # Constrói linha do tempo cronológica unificada (mais recente -> mais antigo / futuros no topo)
        timeline: list[dict[str, Any]] = []

        for rec in applied_records:
            vac_obj = rec.get("vaccines") or {}
            vac_name = vac_obj.get("commercial_name", "Preventivo")
            itype_lbl = vac_obj.get("item_type_label", "Vacina")
            itype_icon = vac_obj.get("item_type_icon", "bi-eyedropper")
            sort_key = str(rec.get("applied_at") or "")[:19]
            sub_parts = [
                f"{rec.get('dosage')} {rec.get('dosage_unit')}",
                str(rec.get("administration_route") or ""),
            ]
            if rec.get("exam_result"):
                sub_parts.append(f"Resultado: {rec['exam_result']}")
            elif rec.get("product_batch"):
                sub_parts.append(f"Lote: {rec['product_batch']}")
            sub_parts.append(f"Resp.: {rec.get('applied_by')}")
            timeline.append(
                {
                    "kind": "vaccination_applied",
                    "sort_key": sort_key,
                    "date_display": rec.get("applied_at"),
                    "is_datetime": True,
                    "title": f"{itype_lbl} Realizada: {vac_name} ({rec.get('dose_number', 1)}ª dose/etapa)",
                    "subtitle": " • ".join(p for p in sub_parts if p),
                    "notes": rec.get("notes"),
                    "badge_label": "Histórico Anterior" if rec.get("is_historical_record") else f"{itype_lbl} Ok",
                    "badge_class": "badge-status-applied",
                    "icon": itype_icon,
                    "record_id": rec["id"],
                }
            )

        for sched in schedules:
            if sched["status"] == "aplicada":
                continue
            vac_name = (sched.get("vaccines") or {}).get("commercial_name", "Vacina")
            sort_key = f"{str(sched.get('scheduled_date') or '')[:10]}T12:00:00"
            origin_desc = "Protocolo"
            if sched.get("vaccination_campaigns"):
                origin_desc = f"Campanha: {sched['vaccination_campaigns']['name']}"
            elif sched.get("sanitary_protocols"):
                origin_desc = f"Protocolo: {sched['sanitary_protocols']['name']}"
            elif sched.get("origin_type") == "reforco":
                origin_desc = "Reforço programado"

            timeline.append(
                {
                    "kind": "schedule",
                    "sort_key": sort_key,
                    "date_display": sched.get("scheduled_date"),
                    "is_datetime": False,
                    "title": f"Agendamento: {vac_name} ({sched.get('dose_number', 1)}ª dose)",
                    "subtitle": origin_desc,
                    "notes": sched.get("status_reason") or sched.get("notes"),
                    "badge_label": sched["status_label"],
                    "badge_class": sched["status_badge_class"],
                    "icon": sched["status_icon"],
                    "schedule": sched,
                }
            )

        for hr in health_records:
            meta = HEALTH_RECORD_TYPE_LABELS.get(
                hr.get("record_type", ""),
                HEALTH_RECORD_TYPE_LABELS["observacao_veterinaria"],
            )
            sort_key = str(hr.get("occurred_at") or "")[:19]
            extra = []
            if hr.get("medication_applied"):
                extra.append(f"Medicação: {hr['medication_applied']}")
            if hr.get("dosage_info"):
                extra.append(f"Posologia: {hr['dosage_info']}")
            if hr.get("veterinarian_or_responsible"):
                extra.append(f"Resp.: {hr['veterinarian_or_responsible']}")

            timeline.append(
                {
                    "kind": "health_record",
                    "sort_key": sort_key,
                    "date_display": hr.get("occurred_at"),
                    "is_datetime": True,
                    "title": hr.get("title"),
                    "subtitle": " • ".join(extra) if extra else meta["label"],
                    "notes": hr.get("description"),
                    "badge_label": meta["label"],
                    "badge_class": meta["badge"],
                    "icon": meta["icon"],
                }
            )

        mgmt_records, _ = list_management_records_for_animal_safe(animal_id)
        for mr in mgmt_records:
            sort_key = f"{str(mr.get('performed_at') or '')[:10]}T15:00:00"
            m_parts = []
            if mr.get("weight_kg") is not None:
                m_parts.append(f"Peso: {mr['weight_kg']} kg")
            if mr.get("fleece_weight_kg") is not None:
                m_parts.append(f"Lã/Velo: {mr['fleece_weight_kg']} kg")
            if mr.get("famacha_score") is not None:
                m_parts.append(f"Famacha: Grau {mr['famacha_score']}")
            if mr.get("hoof_condition"):
                m_parts.append(f"Cascos/Ferragem: {mr['hoof_condition']}")
            if mr.get("next_due_date"):
                m_parts.append(f"Próx. retorno: {mr['next_due_date']}")
            if mr.get("specialist_or_responsible"):
                m_parts.append(f"Resp.: {mr['specialist_or_responsible']}")
            timeline.append(
                {
                    "kind": "management_record",
                    "sort_key": sort_key,
                    "date_display": mr.get("performed_at"),
                    "is_datetime": False,
                    "title": f"Manejo Realizado: {mr['routine_label']}",
                    "subtitle": " • ".join(m_parts) if m_parts else "Rotina de manejo zootécnico",
                    "notes": mr.get("notes"),
                    "badge_label": mr["routine_short_label"],
                    "badge_class": mr["due_badge_class"],
                    "icon": mr["routine_icon"],
                }
            )

        timeline.sort(key=lambda item: item["sort_key"], reverse=True)

        return {
            "applied_records": applied_records,
            "pending_schedules": pending_schedules,
            "upcoming_schedules": upcoming_schedules,
            "overdue_schedules": overdue_schedules,
            "unknown_or_other_schedules": unknown_or_other,
            "treatments": treatments,
            "occurrences": occurrences,
            "vet_notes": vet_notes,
            "linked_protocols": linked_protocols,
            "timeline": timeline,
        }
    except MigrationRequiredError:
        return empty_card
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


# ============================================================================
# 8. Calendário Sanitário Mensal (`get_monthly_calendar_data`)
# ============================================================================
MONTH_NAMES_PT = [
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]


def get_monthly_calendar_data(
    organization_id: str,
    year: int,
    month: int,
    filters: dict[str, str],
    age_brackets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Constrói o calendário sanitário mensal com filtros por Propriedade, Lote,
    Vacina, Categoria Etária e Situação, atualizado diretamente do Supabase.
    """
    first_day = date(year, month, 1)
    _, last_day_num = calendar.monthrange(year, month)
    last_day = date(year, month, last_day_num)

    prop_filter = (filters.get("property_id") or "").strip()
    lot_filter = (filters.get("lot_id") or "").strip()
    vac_filter = (filters.get("vaccine_id") or "").strip()
    species_filter = (filters.get("species") or "").strip().lower()
    age_filter = (filters.get("age_category") or "").strip().lower()
    status_filter = (filters.get("status") or "").strip().lower()

    try:
        client = get_supabase_client()

        # Busca agendamentos do mês
        sched_query = (
            client.table("vaccination_schedules")
            .select(
                "*, vaccines(*), "
                "animals(*, lots(id, name)), "
                "properties(id, name), vaccination_campaigns(id, name)"
            )
            .eq("organization_id", organization_id)
            .gte("scheduled_date", first_day.isoformat())
            .lte("scheduled_date", last_day.isoformat())
        )
        if prop_filter and is_valid_uuid(prop_filter):
            sched_query = sched_query.eq("property_id", prop_filter)
        if vac_filter and is_valid_uuid(vac_filter):
            sched_query = sched_query.eq("vaccine_id", vac_filter)

        raw_schedules = sched_query.order("scheduled_date").execute().data or []
        schedules = sync_dynamic_schedule_statuses(raw_schedules, persist_changes=True)

        # Busca aplicações avulsas realizadas no mês
        rec_query = (
            client.table("vaccination_records")
            .select(
                "*, vaccines(*), "
                "animals(*, lots(id, name)), "
                "properties(id, name)"
            )
            .eq("organization_id", organization_id)
            .gte("applied_at", f"{first_day.isoformat()}T00:00:00")
            .lte("applied_at", f"{last_day.isoformat()}T23:59:59")
        )
        if prop_filter and is_valid_uuid(prop_filter):
            rec_query = rec_query.eq("property_id", prop_filter)
        if vac_filter and is_valid_uuid(vac_filter):
            rec_query = rec_query.eq("vaccine_id", vac_filter)
        month_records = rec_query.execute().data or []

        # Busca campanhas programadas no mês
        camp_query = (
            client.table("vaccination_campaigns")
            .select("*, vaccines(id, commercial_name), properties(id, name), lots(id, name)")
            .eq("organization_id", organization_id)
            .gte("scheduled_date", first_day.isoformat())
            .lte("scheduled_date", last_day.isoformat())
        )
        if prop_filter and is_valid_uuid(prop_filter):
            camp_query = camp_query.eq("property_id", prop_filter)
        if lot_filter and is_valid_uuid(lot_filter):
            camp_query = camp_query.eq("lot_id", lot_filter)
        if vac_filter and is_valid_uuid(vac_filter):
            camp_query = camp_query.eq("vaccine_id", vac_filter)
        campaigns = camp_query.execute().data or []

        events_by_day: dict[str, list[dict[str, Any]]] = {}
        scheduled_record_ids: set[str] = set()

        for sched in schedules:
            animal_raw = sched.get("animals") or {}
            if not animal_raw:
                continue
            animal = enrich_animal_with_age(animal_raw, brackets=age_brackets)

            if species_filter and species_filter not in ("todas", "todos") and animal.get("species") != species_filter:
                continue
            if lot_filter and is_valid_uuid(lot_filter) and animal.get("lot_id") != lot_filter:
                continue
            if age_filter and age_filter != "todas" and animal.get("age_category") != normalize_age_slug(age_filter):
                continue
            if status_filter and status_filter != "todos" and sched["status"] != status_filter:
                continue

            if sched["status"] == "aplicada":
                scheduled_record_ids.add(sched["id"])

            day_key = str(sched["scheduled_date"])[:10]
            vac = _enrich_vaccine_item(sched.get("vaccines") or {})
            events_by_day.setdefault(day_key, []).append(
                {
                    "type": "schedule",
                    "id": sched["id"],
                    "date": day_key,
                    "status": sched["status"],
                    "status_label": sched["status_label"],
                    "status_badge_class": sched["status_badge_class"],
                    "vaccine_id": sched["vaccine_id"],
                    "vaccine_name": vac.get("commercial_name", "Preventivo"),
                    "item_type_label": vac.get("item_type_label", "Vacina"),
                    "manufacturer": vac.get("manufacturer", ""),
                    "dosage_unit": vac.get("dosage_unit", "mL"),
                    "administration_route": vac.get("administration_route", ""),
                    "dose_number": sched.get("dose_number", 1),
                    "animal_id": animal["id"],
                    "ear_tag": animal.get("ear_tag", ""),
                    "animal_name": animal.get("name") or "",
                    "species_label": animal.get("species_label", "Bovino"),
                    "species_badge_class": animal.get("species_badge_class", "badge-species-bovino"),
                    "qr_code_token": animal.get("qr_code_token", ""),
                    "age_category_name": animal.get("age_category_name", ""),
                    "property_name": (sched.get("properties") or {}).get("name", ""),
                    "lot_name": ((animal.get("lots") or {}).get("name")) or "Sem lote",
                    "campaign_name": (sched.get("vaccination_campaigns") or {}).get("name"),
                    "campaign_id": sched.get("campaign_id"),
                    "can_apply": sched["status"] in ("pendente", "proxima_aplicacao", "atrasada"),
                }
            )

        # Inclui aplicações avulsas na data real de aplicação (se não duplicar agendamento do mesmo dia)
        for rec in month_records:
            if rec.get("schedule_id") in scheduled_record_ids:
                continue
            if status_filter and status_filter not in ("todos", "aplicada"):
                continue
            animal_raw = rec.get("animals") or {}
            if not animal_raw:
                continue
            animal = enrich_animal_with_age(animal_raw, brackets=age_brackets)
            if species_filter and species_filter not in ("todas", "todos") and animal.get("species") != species_filter:
                continue
            if lot_filter and is_valid_uuid(lot_filter) and animal.get("lot_id") != lot_filter:
                continue
            if age_filter and age_filter != "todas" and animal.get("age_category") != normalize_age_slug(age_filter):
                continue

            day_key = str(rec["applied_at"])[:10]
            vac = _enrich_vaccine_item(rec.get("vaccines") or {})
            events_by_day.setdefault(day_key, []).append(
                {
                    "type": "record",
                    "id": rec["id"],
                    "date": day_key,
                    "status": "aplicada",
                    "status_label": "Realizada",
                    "status_badge_class": "badge-status-applied",
                    "vaccine_id": rec["vaccine_id"],
                    "vaccine_name": vac.get("commercial_name", "Preventivo"),
                    "item_type_label": vac.get("item_type_label", "Vacina"),
                    "dose_number": rec.get("dose_number", 1),
                    "animal_id": animal["id"],
                    "ear_tag": animal.get("ear_tag", ""),
                    "animal_name": animal.get("name") or "",
                    "species_label": animal.get("species_label", "Bovino"),
                    "species_badge_class": animal.get("species_badge_class", "badge-species-bovino"),
                    "qr_code_token": animal.get("qr_code_token", ""),
                    "age_category_name": animal.get("age_category_name", ""),
                    "property_name": (rec.get("properties") or {}).get("name", ""),
                    "lot_name": ((animal.get("lots") or {}).get("name")) or "Sem lote",
                    "campaign_name": None,
                    "campaign_id": rec.get("campaign_id"),
                    "can_apply": False,
                }
            )

        # Inclui retornos programados de Rotinas de Manejo (casqueamento, ferrageamento, tosquia, pesagem) no mês
        if not vac_filter:
            mgmt_data = list_management_alerts_safe(
                organization_id=organization_id,
                property_id=prop_filter or None,
                species=species_filter or None,
                age_brackets=age_brackets,
            )
            for mr in mgmt_data["overdue_alerts"] + mgmt_data["upcoming_alerts"]:
                due_iso = str(mr.get("next_due_date") or "")[:10]
                if not due_iso or due_iso < first_day.isoformat() or due_iso > last_day.isoformat():
                    continue
                anim = mr["animal"]
                if lot_filter and is_valid_uuid(lot_filter) and anim.get("lot_id") != lot_filter:
                    continue
                if age_filter and age_filter != "todas" and anim.get("age_category") != normalize_age_slug(age_filter):
                    continue
                mapped_status = "atrasada" if mr.get("due_status") == "atrasado" else "proxima_aplicacao"
                if status_filter and status_filter not in ("todos", mapped_status, "pendente"):
                    continue
                events_by_day.setdefault(due_iso, []).append(
                    {
                        "type": "management_due",
                        "id": mr["id"],
                        "date": due_iso,
                        "status": mapped_status,
                        "status_label": mr["due_status_label"],
                        "status_badge_class": mr["due_badge_class"],
                        "vaccine_id": None,
                        "vaccine_name": f"Manejo: {mr['routine_short_label']}",
                        "item_type_label": "Manejo",
                        "dose_number": 1,
                        "animal_id": anim["id"],
                        "ear_tag": anim.get("ear_tag", ""),
                        "animal_name": anim.get("name") or "",
                        "species_label": anim.get("species_label", "Bovino"),
                        "species_badge_class": anim.get("species_badge_class", "badge-species-bovino"),
                        "qr_code_token": anim.get("qr_code_token", ""),
                        "age_category_name": anim.get("age_category_name", ""),
                        "property_name": mr.get("property_name", ""),
                        "lot_name": anim.get("housing_display") or "Manejo programado",
                        "campaign_name": None,
                        "campaign_id": None,
                        "can_apply": False,
                    }
                )

        campaigns_by_day: dict[str, list[dict[str, Any]]] = {}
        if not status_filter or status_filter in ("todos", "pendente", "proxima_aplicacao", "aplicada"):
            for camp in campaigns:
                day_key = str(camp["scheduled_date"])[:10]
                campaigns_by_day.setdefault(day_key, []).append(
                    {
                        "id": camp["id"],
                        "name": camp["name"],
                        "vaccine_name": (camp.get("vaccines") or {}).get("commercial_name", "Vacina"),
                        "property_name": (camp.get("properties") or {}).get("name", ""),
                        "lot_name": (camp.get("lots") or {}).get("name") or "Seleção manual",
                        "status": camp.get("status", "programada"),
                    }
                )

        cal = calendar.Calendar(firstweekday=6)  # Domingo a Sábado
        weeks: list[list[dict[str, Any]]] = []
        today_iso = date.today().isoformat()

        summary_counts = {"previstas": 0, "realizadas": 0, "atrasadas": 0, "campanhas": len(campaigns)}

        for week in cal.monthdatescalendar(year, month):
            week_cells: list[dict[str, Any]] = []
            for d in week:
                d_iso = d.isoformat()
                in_month = d.month == month
                day_events = events_by_day.get(d_iso, []) if in_month else []
                day_camps = campaigns_by_day.get(d_iso, []) if in_month else []

                c_overdue = sum(1 for e in day_events if e["status"] == "atrasada")
                c_planned = sum(1 for e in day_events if e["status"] in ("pendente", "proxima_aplicacao"))
                c_applied = sum(1 for e in day_events if e["status"] == "aplicada")

                if in_month:
                    summary_counts["previstas"] += c_planned
                    summary_counts["realizadas"] += c_applied
                    summary_counts["atrasadas"] += c_overdue

                week_cells.append(
                    {
                        "date_iso": d_iso,
                        "date_br": d.strftime("%d/%m/%Y"),
                        "day": d.day,
                        "in_month": in_month,
                        "is_today": d_iso == today_iso,
                        "overdue_count": c_overdue,
                        "planned_count": c_planned,
                        "applied_count": c_applied,
                        "campaigns_count": len(day_camps),
                        "total_items": len(day_events) + len(day_camps),
                        "events": day_events,
                        "campaigns": day_camps,
                    }
                )
            weeks.append(week_cells)

        prev_dt = first_day - timedelta(days=1)
        next_dt = last_day + timedelta(days=1)

        return {
            "year": year,
            "month": month,
            "month_name": MONTH_NAMES_PT[month],
            "prev_year": prev_dt.year,
            "prev_month": prev_dt.month,
            "next_year": next_dt.year,
            "next_month": next_dt.month,
            "weeks": weeks,
            "summary": summary_counts,
        }
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


# ============================================================================
# 9. Dashboard Sanitário (`get_sanitary_dashboard_data`)
# ============================================================================
def get_sanitary_dashboard_data(
    organization_id: str,
    property_id: str | None = None,
    species: str | None = None,
    age_brackets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Calcula em tempo real todos os indicadores do Dashboard Sanitário & Manejo
    (Bovinos, Equinos e Ovinos) a partir dos dados reais armazenados no Supabase.
    """
    clean_sp = (species or "").strip().lower()
    if clean_sp in ("", "todas", "todos"):
        clean_sp = ""

    try:
        client = get_supabase_client()

        anim_query = (
            client.table("animals")
            .select("*, properties(id, name), lots(id, name)")
            .eq("organization_id", organization_id)
            .eq("status", "ativo")
            .order("created_at", desc=True)
        )
        if property_id and is_valid_uuid(property_id):
            anim_query = anim_query.eq("property_id", property_id)

        raw_animals = anim_query.execute().data or []
        animals = enrich_animals_list(raw_animals, brackets=age_brackets)
        if clean_sp:
            animals = [a for a in animals if a["species"] == clean_sp]
        age_summary = summarize_age_categories(animals)

        sched_query = (
            client.table("vaccination_schedules")
            .select(
                "*, vaccines(*), "
                "animals(*), "
                "properties(id, name), vaccination_campaigns(id, name)"
            )
            .eq("organization_id", organization_id)
            .order("scheduled_date")
        )
        if property_id and is_valid_uuid(property_id):
            sched_query = sched_query.eq("property_id", property_id)

        raw_schedules = sched_query.execute().data or []
        for rs in raw_schedules:
            if rs.get("vaccines"):
                rs["vaccines"] = _enrich_vaccine_item(rs["vaccines"])
        schedules = sync_dynamic_schedule_statuses(raw_schedules, persist_changes=True)
        if clean_sp:
            schedules = [
                s
                for s in schedules
                if s.get("animals") and normalize_species(s["animals"].get("species")) == clean_sp
            ]

        pending_count = sum(1 for s in schedules if s["status"] == "pendente")
        overdue_count = sum(1 for s in schedules if s["status"] == "atrasada")
        upcoming_count = sum(1 for s in schedules if s["status"] == "proxima_aplicacao")

        unknown_animal_ids = {
            a["id"] for a in animals if a.get("sanitary_onboarding_mode") == "historico_desconhecido"
        } | {
            s["animal_id"] for s in schedules if s["status"] == "historico_desconhecido"
        }
        unknown_history_count = len(unknown_animal_ids)

        priority_map = {"atrasada": 0, "pendente": 1, "proxima_aplicacao": 2}
        actionable = [
            s for s in schedules if s["status"] in ("atrasada", "pendente", "proxima_aplicacao") and s.get("animals")
        ]
        for s in actionable:
            s["animal"] = enrich_animal_with_age(s["animals"], brackets=age_brackets)
        actionable.sort(key=lambda s: (priority_map.get(s["status"], 9), str(s.get("scheduled_date") or "")))

        recent_campaigns = list_campaign_cartelas(organization_id, property_id=property_id)[:4]
        mgmt_summary = list_management_alerts_safe(
            organization_id=organization_id,
            property_id=property_id,
            species=clean_sp or None,
            age_brackets=age_brackets,
        )

        return {
            "total_animals": age_summary["total"],
            "newborns_count": age_summary["recem_nascido"],
            "lactentes_count": age_summary["lactente"],
            "calves_count": age_summary["lactente"],
            "young_count": age_summary["jovem"],
            "adults_count": age_summary["adulto"],
            "bovinos_count": age_summary["bovino"],
            "equinos_count": age_summary["equino"],
            "ovinos_count": age_summary["ovino"],
            "pending_vaccinations": pending_count,
            "overdue_vaccinations": overdue_count,
            "upcoming_vaccinations": upcoming_count,
            "unknown_history_count": unknown_history_count,
            "upcoming_activities": actionable[:12],
            "recent_campaigns": recent_campaigns,
            "overdue_management_count": len(mgmt_summary["overdue_alerts"]),
            "upcoming_management_count": len(mgmt_summary["upcoming_alerts"]),
            "management_alerts": (mgmt_summary["overdue_alerts"] + mgmt_summary["upcoming_alerts"])[:10],
            "migration_004_ready": mgmt_summary["migration_004_ready"],
        }
    except Exception as exc:
        raise translate_supabase_error(exc) from exc
