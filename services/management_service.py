"""
Serviço de Rotinas Zootécnicas / Manejo por Espécie (`management_records`) e
Planos Individuais de Cocho / Arraçoamento (`feeding_plans`).
"""

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from services.classification_service import enrich_animal_with_age, parse_iso_date
from services.species_service import (
    MANAGEMENT_ROUTINE_META,
    get_routines_for_species,
    normalize_species,
)
from services.supabase_service import (
    MigrationRequiredError,
    MultiSpeciesMigrationRequiredError,
    SupabaseServiceError,
    get_supabase_client,
    is_valid_uuid,
    translate_supabase_error,
)


def enrich_management_record(record: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """Adiciona rótulos de rotina e cálculo dinâmico de vencimento do próximo retorno."""
    ref_today = today or date.today()
    enriched = dict(record)
    rtype = str(enriched.get("routine_type") or "pesagem").strip().lower()
    meta = MANAGEMENT_ROUTINE_META.get(rtype, MANAGEMENT_ROUTINE_META["pesagem"])

    enriched["routine_label"] = meta["label"]
    enriched["routine_short_label"] = meta["short_label"]
    enriched["routine_icon"] = meta["icon"]
    enriched["routine_badge_class"] = meta["badge_class"]

    due_dt = parse_iso_date(enriched.get("next_due_date"))
    if due_dt:
        days_until = (due_dt - ref_today).days
        enriched["days_until_due"] = days_until
        if days_until < 0:
            enriched["due_status"] = "atrasado"
            enriched["due_status_label"] = f"Retorno atrasado ({abs(days_until)}d)"
            enriched["due_badge_class"] = "badge-status-overdue"
        elif days_until <= 10:
            enriched["due_status"] = "proximo"
            enriched["due_status_label"] = "Hoje" if days_until == 0 else f"Em {days_until}d"
            enriched["due_badge_class"] = "badge-status-pending"
        else:
            enriched["due_status"] = "programado"
            enriched["due_status_label"] = f"Programado ({due_dt.strftime('%d/%m/%Y')})"
            enriched["due_badge_class"] = "badge-status-upcoming"
    else:
        enriched["days_until_due"] = None
        enriched["due_status"] = "concluido"
        enriched["due_status_label"] = "Realizado"
        enriched["due_badge_class"] = "badge-status-applied"

    return enriched


def list_management_records_for_animal_safe(animal_id: str) -> tuple[list[dict[str, Any]], bool]:
    """
    Lista o histórico de rotinas de manejo de um animal em ordem decrescente.
    Retorna `(registros, migration_004_ready)` sem lançar erro caso a tabela ainda não exista.
    """
    if not animal_id or not is_valid_uuid(animal_id):
        return [], True
    try:
        rows = (
            get_supabase_client()
            .table("management_records")
            .select("*")
            .eq("animal_id", animal_id)
            .order("performed_at", desc=True)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        today = date.today()
        return [enrich_management_record(r, today=today) for r in rows], True
    except Exception as exc:
        err = translate_supabase_error(exc)
        if isinstance(err, MigrationRequiredError):
            return [], False
        raise err from exc


def list_management_alerts_safe(
    organization_id: str | None,
    property_id: str | None = None,
    species: str | None = None,
    age_brackets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Busca os manejos mais recentes por animal + tipo de rotina para destacar retornos
    atrasados ou próximos nos próximos 15 dias (casqueamento, ferrageamento, tosquia, pesagem).
    """
    empty = {
        "migration_004_ready": True,
        "overdue_alerts": [],
        "upcoming_alerts": [],
        "recent_records": [],
    }
    if not organization_id or not is_valid_uuid(organization_id):
        return empty

    clean_species = (species or "").strip().lower()
    if clean_species in ("", "todas", "todos"):
        clean_species = ""

    try:
        client = get_supabase_client()
        query = (
            client.table("management_records")
            .select(
                "*, animals(id, ear_tag, name, species, breed, birth_date, qr_code_token, "
                "accommodation_name, accommodation_type, status), properties(id, name)"
            )
            .eq("organization_id", organization_id)
            .order("performed_at", desc=True)
            .limit(200)
        )
        if property_id and is_valid_uuid(property_id):
            query = query.eq("property_id", property_id)

        rows = query.execute().data or []
        today = date.today()

        latest_per_animal_routine: dict[tuple[str, str], dict[str, Any]] = {}
        enriched_all: list[dict[str, Any]] = []

        for r in rows:
            anim_raw = r.get("animals") or {}
            if not anim_raw or str(anim_raw.get("status") or "ativo").lower() != "ativo":
                continue
            anim = enrich_animal_with_age(anim_raw, brackets=age_brackets)
            if clean_species and anim["species"] != clean_species:
                continue

            item = enrich_management_record(r, today=today)
            item["animal"] = anim
            item["property_name"] = (r.get("properties") or {}).get("name", "—")
            enriched_all.append(item)

            key = (anim["id"], str(item.get("routine_type") or ""))
            if key not in latest_per_animal_routine:
                latest_per_animal_routine[key] = item

        overdue_alerts = [
            v for v in latest_per_animal_routine.values() if v.get("due_status") == "atrasado"
        ]
        upcoming_alerts = [
            v
            for v in latest_per_animal_routine.values()
            if v.get("due_status") in ("proximo", "programado")
            and v.get("days_until_due") is not None
            and v["days_until_due"] <= 30
        ]

        overdue_alerts.sort(key=lambda x: str(x.get("next_due_date") or ""))
        upcoming_alerts.sort(key=lambda x: str(x.get("next_due_date") or ""))

        return {
            "migration_004_ready": True,
            "overdue_alerts": overdue_alerts,
            "upcoming_alerts": upcoming_alerts,
            "recent_records": enriched_all[:20],
        }
    except Exception as exc:
        err = translate_supabase_error(exc)
        if isinstance(err, MigrationRequiredError):
            return {**empty, "migration_004_ready": False}
        raise err from exc


def create_management_record(organization_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Registra uma rotina de manejo (casqueamento, ferrageamento, tosquia, pesagem, etc.) para o animal."""
    animal_id = (payload.get("animal_id") or "").strip()
    routine_type = (payload.get("routine_type") or "").strip().lower()
    performed_raw = (payload.get("performed_at") or "").strip() or date.today().isoformat()
    next_due_raw = (payload.get("next_due_date") or "").strip()
    auto_suggest_due = str(payload.get("auto_suggest_due", "")).lower() in ("1", "true", "on", "yes")

    if not is_valid_uuid(animal_id):
        raise SupabaseServiceError("Animal inválido para registro de manejo.")
    if routine_type not in MANAGEMENT_ROUTINE_META:
        raise SupabaseServiceError("Selecione um tipo de manejo válido.")

    performed_dt = parse_iso_date(performed_raw)
    if not performed_dt:
        raise SupabaseServiceError("Informe uma data válida para a realização do manejo.")
    if performed_dt > date.today():
        raise SupabaseServiceError("A data de realização do manejo não pode ser futura.")

    next_due_dt = parse_iso_date(next_due_raw) if next_due_raw else None
    if next_due_raw and not next_due_dt:
        raise SupabaseServiceError("Informe uma data válida para o próximo retorno.")
    if not next_due_dt and auto_suggest_due:
        interval = int(MANAGEMENT_ROUTINE_META[routine_type].get("default_interval_days") or 30)
        next_due_dt = performed_dt + timedelta(days=interval)
    if next_due_dt and next_due_dt < performed_dt:
        raise SupabaseServiceError("A data do próximo retorno deve ser igual ou posterior à data realizada.")

    weight_kg: float | None = None
    w_raw = str(payload.get("weight_kg") or "").strip().replace(",", ".")
    if w_raw:
        try:
            weight_kg = round(float(w_raw), 2)
            if weight_kg < 0 or weight_kg > 3000:
                raise SupabaseServiceError("Informe um peso válido em quilogramas (0 a 3000 kg).")
        except ValueError as exc:
            raise SupabaseServiceError("Informe um número válido para o peso em kg.") from exc

    fleece_weight_kg: float | None = None
    fl_raw = str(payload.get("fleece_weight_kg") or "").strip().replace(",", ".")
    if fl_raw:
        try:
            fleece_weight_kg = round(float(fl_raw), 2)
            if fleece_weight_kg < 0 or fleece_weight_kg > 50:
                raise SupabaseServiceError("Informe um peso de velo/lã válido em kg.")
        except ValueError as exc:
            raise SupabaseServiceError("Informe um número válido para o peso de lã.") from exc

    famacha_score: int | None = None
    fam_raw = str(payload.get("famacha_score") or "").strip()
    if fam_raw:
        try:
            famacha_score = int(fam_raw)
            if famacha_score < 1 or famacha_score > 5:
                raise SupabaseServiceError("O grau Famacha deve estar entre 1 e 5.")
        except ValueError as exc:
            raise SupabaseServiceError("Informe um grau Famacha válido (1 a 5).") from exc

    try:
        client = get_supabase_client()
        anim_res = (
            client.table("animals")
            .select("*")
            .eq("id", animal_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
            .data
        )
        if not anim_res:
            raise SupabaseServiceError("Animal não encontrado nesta organização.")
        animal = anim_res[0]
        property_id = animal.get("property_id")
        if not property_id:
            raise SupabaseServiceError("Vincule o animal a uma propriedade antes de registrar manejos.")

        # Valida compatibilidade da rotina com a espécie do animal
        animal_species = normalize_species(animal.get("species"))
        allowed_for_species = get_routines_for_species(animal_species)
        if routine_type not in allowed_for_species:
            meta_lbl = MANAGEMENT_ROUTINE_META[routine_type]["short_label"]
            raise SupabaseServiceError(
                f"A rotina '{meta_lbl}' não é aplicável à espécie deste animal ({animal_species.title()})."
            )

        record = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "property_id": property_id,
            "animal_id": animal_id,
            "routine_type": routine_type,
            "performed_at": performed_dt.isoformat(),
            "next_due_date": next_due_dt.isoformat() if next_due_dt else None,
            "weight_kg": weight_kg,
            "fleece_weight_kg": fleece_weight_kg,
            "famacha_score": famacha_score,
            "hoof_condition": (payload.get("hoof_condition") or "").strip()[:120] or None,
            "specialist_or_responsible": (payload.get("specialist_or_responsible") or "").strip()[:150] or None,
            "notes": (payload.get("notes") or "").strip() or None,
        }

        res = client.table("management_records").insert(record).execute()
        if not res.data:
            raise SupabaseServiceError("Não foi possível salvar o registro de manejo.")

        # Se houve pesagem registrada, atualiza o peso atual de referência do animal
        if weight_kg is not None:
            try:
                client.table("animals").update({"initial_weight": weight_kg}).eq("id", animal_id).execute()
            except Exception:
                pass

        return enrich_management_record(res.data[0])
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


# ============================================================================
# Plano Individual de Cocho / Arraçoamento (`feeding_plans`)
# ============================================================================
def get_feeding_plan_for_animal_safe(animal_id: str) -> tuple[dict[str, Any] | None, bool]:
    """
    Busca o plano de cocho/arraçoamento ativo do animal.
    Retorna `(plano_ou_None, migration_004_ready)` com degradação elegante.
    """
    if not animal_id or not is_valid_uuid(animal_id):
        return None, True
    try:
        rows = (
            get_supabase_client()
            .table("feeding_plans")
            .select("*")
            .eq("animal_id", animal_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return (rows[0] if rows else None), True
    except Exception as exc:
        err = translate_supabase_error(exc)
        if isinstance(err, MigrationRequiredError):
            return None, False
        raise err from exc


def save_feeding_plan(
    organization_id: str,
    payload: dict[str, Any],
    operator_name: str,
) -> dict[str, Any]:
    """Cria ou atualiza o plano de cocho/arraçoamento de um animal (restrito a Property/Admin)."""
    animal_id = (payload.get("animal_id") or "").strip()
    if not is_valid_uuid(animal_id):
        raise SupabaseServiceError("Animal inválido para configurar plano de cocho.")

    plan_name = (payload.get("plan_name") or "").strip() or "Dieta Padrão de Cocho"
    roughage = (payload.get("roughage") or "").strip() or None
    concentrate = (payload.get("concentrate") or "").strip() or None
    supplement_mineral = (payload.get("supplement_mineral") or "").strip() or None
    feeding_schedule = (payload.get("feeding_schedule") or "").strip() or None
    water_and_trough_notes = (payload.get("water_and_trough_notes") or "").strip() or None
    is_active = str(payload.get("is_active", "true")).lower() in ("1", "true", "on", "yes")

    if not any((roughage, concentrate, supplement_mineral, water_and_trough_notes)):
        raise SupabaseServiceError(
            "Preencha ao menos o volumoso, concentrado/ração, suplemento ou orientações de cocho."
        )

    try:
        client = get_supabase_client()
        anim_res = (
            client.table("animals")
            .select("id, property_id")
            .eq("id", animal_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
            .data
        )
        if not anim_res:
            raise SupabaseServiceError("Animal não encontrado nesta organização.")
        property_id = anim_res[0].get("property_id")
        if not property_id:
            raise SupabaseServiceError("Vincule o animal a uma propriedade antes de configurar o plano de cocho.")

        now_iso = datetime.now().astimezone().isoformat()
        existing = (
            client.table("feeding_plans")
            .select("id")
            .eq("animal_id", animal_id)
            .limit(1)
            .execute()
            .data
        )

        record = {
            "organization_id": organization_id,
            "property_id": property_id,
            "animal_id": animal_id,
            "plan_name": plan_name[:150],
            "roughage": roughage[:200] if roughage else None,
            "concentrate": concentrate[:200] if concentrate else None,
            "supplement_mineral": supplement_mineral[:200] if supplement_mineral else None,
            "feeding_schedule": feeding_schedule[:160] if feeding_schedule else None,
            "water_and_trough_notes": water_and_trough_notes,
            "is_active": is_active,
            "updated_by": operator_name or "Operador Animora",
            "updated_at": now_iso,
        }

        if existing:
            res = (
                client.table("feeding_plans")
                .update(record)
                .eq("id", existing[0]["id"])
                .execute()
            )
        else:
            record["id"] = str(uuid.uuid4())
            res = client.table("feeding_plans").insert(record).execute()

        if not res.data:
            raise SupabaseServiceError("Não foi possível salvar o plano de cocho.")
        return res.data[0]
    except Exception as exc:
        raise translate_supabase_error(exc) from exc
