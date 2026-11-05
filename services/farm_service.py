"""
Serviço de Gestão de Fazendas (Propriedades), Perfis de Acesso Vinculados e
Exclusão de Dados (Unitária e Geral por Fazenda com Invalidação de QR Codes).
Exclusivo para o perfil Admin.
"""

import uuid
from typing import Any
from services.species_service import PROPERTY_FOCUS_LABELS
from services.supabase_service import (
    MigrationRequiredError,
    SupabaseServiceError,
    get_supabase_client,
    is_valid_uuid,
    translate_supabase_error,
)


def list_farms_with_stats(organization_id: str) -> list[dict[str, Any]]:
    """Lista todas as fazendas com contagem de animais, lotes e acessos vinculados."""
    if not organization_id or not is_valid_uuid(organization_id):
        return []
    try:
        client = get_supabase_client()
        props = (
            client.table("properties")
            .select("*")
            .eq("organization_id", organization_id)
            .order("created_at")
            .execute()
            .data
            or []
        )
        if not props:
            return []

        prop_ids = [p["id"] for p in props]

        # Contagem de animais por propriedade
        animals = (
            client.table("animals")
            .select("id, property_id")
            .in_("property_id", prop_ids)
            .eq("status", "ativo")
            .execute()
            .data
            or []
        )
        anim_counts: dict[str, int] = {}
        for a in animals:
            pid = a.get("property_id")
            if pid:
                anim_counts[pid] = anim_counts.get(pid, 0) + 1

        # Contagem de lotes por propriedade
        lots = (
            client.table("lots")
            .select("id, property_id")
            .in_("property_id", prop_ids)
            .execute()
            .data
            or []
        )
        lot_counts: dict[str, int] = {}
        for l in lots:
            pid = l.get("property_id")
            if pid:
                lot_counts[pid] = lot_counts.get(pid, 0) + 1

        # Perfis de acesso vinculados
        access_profiles = list_all_farm_access_profiles(organization_id)
        access_by_prop: dict[str, list[dict[str, Any]]] = {}
        for acc in access_profiles:
            pid = acc.get("property_id")
            if pid:
                access_by_prop.setdefault(pid, []).append(acc)

        for p in props:
            pid = p["id"]
            p["animals_count"] = anim_counts.get(pid, 0)
            p["lots_count"] = lot_counts.get(pid, 0)
            p["access_profiles"] = access_by_prop.get(pid, [])
            p["access_count"] = len(p["access_profiles"])
            p["focus_label"] = PROPERTY_FOCUS_LABELS.get(
                p.get("production_focus"), p.get("production_focus", "Misto")
            )

        return props
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def create_farm_access_profile(
    organization_id: str,
    property_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Cria um perfil de acesso vinculado a uma fazenda específica (Admin Only)."""
    if not is_valid_uuid(organization_id):
        raise SupabaseServiceError("Organização inválida.")
    if not is_valid_uuid(property_id):
        raise SupabaseServiceError("Selecione uma fazenda válida para vincular o acesso.")

    name = (payload.get("name") or "").strip()
    if not name:
        raise SupabaseServiceError("Informe o nome do operador / responsável pelo acesso.")

    access_pin = (payload.get("access_pin") or "").strip()
    if not access_pin or len(access_pin) < 3:
        raise SupabaseServiceError("Informe uma chave de acesso / PIN de no mínimo 3 caracteres.")

    role = (payload.get("role") or "produtor").strip().lower()
    if role not in ("produtor", "responsavel_tecnico", "operador"):
        role = "produtor"

    client = get_supabase_client()

    # Valida se o PIN já existe em outro perfil ativo
    try:
        existing = (
            client.table("property_access_profiles")
            .select("id, name")
            .eq("access_pin", access_pin)
            .limit(1)
            .execute()
            .data
        )
        if existing:
            raise SupabaseServiceError(
                f"Esta chave/PIN de acesso já está em uso pelo perfil '{existing[0]['name']}'. Escolha uma chave exclusiva."
            )
    except Exception as exc:
        err = translate_supabase_error(exc)
        if isinstance(err, MigrationRequiredError):
            raise SupabaseServiceError(
                "A tabela de acessos por fazenda ainda não foi criada no Supabase. Execute a migration 005_farm_access_and_cascade_cleanup.sql."
            ) from exc
        raise err from exc

    record = {
        "id": str(uuid.uuid4()),
        "organization_id": organization_id,
        "property_id": property_id,
        "name": name[:150],
        "role": role,
        "access_pin": access_pin[:100],
        "is_active": True,
    }

    try:
        res = client.table("property_access_profiles").insert(record).execute()
        if not res.data:
            raise SupabaseServiceError("Não foi possível criar o perfil de acesso.")
        return res.data[0]
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def list_all_farm_access_profiles(organization_id: str) -> list[dict[str, Any]]:
    """Lista todos os perfis de acesso cadastrados na organização."""
    if not organization_id or not is_valid_uuid(organization_id):
        return []
    try:
        client = get_supabase_client()
        return (
            client.table("property_access_profiles")
            .select("*, properties(id, name, code)")
            .eq("organization_id", organization_id)
            .order("created_at")
            .execute()
            .data
            or []
        )
    except Exception:
        # Se a tabela ainda não existir, degrada com lista vazia
        return []


def find_access_profile_by_pin(access_pin: str) -> dict[str, Any] | None:
    """Busca um perfil de acesso ativo pelo PIN informado."""
    clean_pin = (access_pin or "").strip()
    if not clean_pin:
        return None
    try:
        client = get_supabase_client()
        res = (
            client.table("property_access_profiles")
            .select("*, properties(id, name, code, organization_id)")
            .eq("access_pin", clean_pin)
            .eq("is_active", True)
            .limit(1)
            .execute()
            .data
        )
        if not res:
            return None
        profile = res[0]
        prop = profile.get("properties") or {}
        profile["property_name"] = prop.get("name") or "Fazenda Vinculada"
        return profile
    except Exception:
        return None


def delete_farm_access_profile(profile_id: str) -> bool:
    """Exclui um perfil de acesso pelo ID (Admin Only)."""
    if not is_valid_uuid(profile_id):
        raise SupabaseServiceError("Perfil de acesso inválido.")
    try:
        client = get_supabase_client()
        res = client.table("property_access_profiles").delete().eq("id", profile_id).execute()
        return bool(res.data)
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def toggle_farm_access_profile(profile_id: str) -> dict[str, Any]:
    """Ativa ou desativa um perfil de acesso."""
    if not is_valid_uuid(profile_id):
        raise SupabaseServiceError("Perfil de acesso inválido.")
    try:
        client = get_supabase_client()
        found = client.table("property_access_profiles").select("id, is_active").eq("id", profile_id).limit(1).execute().data
        if not found:
            raise SupabaseServiceError("Perfil não encontrado.")
        new_active = not bool(found[0].get("is_active"))
        res = client.table("property_access_profiles").update({"is_active": new_active}).eq("id", profile_id).execute()
        return res.data[0]
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


# ============================================================================
# Invalidação de QR Codes e Exclusão Segura
# ============================================================================

_LOCAL_INVALIDATED_TOKENS: dict[str, str] = {}


def record_invalidated_qr_tokens(tokens: list[str], reason: str = "Registro ou etiqueta excluída") -> None:
    """Grava tokens na tabela de QR codes invalidados e atualiza tag_units como 'retired'."""
    clean_tokens = [t.strip() for t in tokens if is_valid_uuid(t.strip())]
    if not clean_tokens:
        return

    # Registra no cache de segurança em memória
    for tok in clean_tokens:
        _LOCAL_INVALIDATED_TOKENS[tok] = reason

    client = get_supabase_client()

    # 1. Atualiza tag_units para retired
    try:
        client.table("tag_units").update({
            "status": "retired",
            "retired_at": "now()",
            "notes": reason,
        }).in_("qr_token", clean_tokens).execute()
    except Exception:
        pass

    # 2. Registra na tabela de tokens invalidados
    try:
        records = [{"token": tok, "reason": reason} for tok in clean_tokens]
        client.table("invalidated_qr_tokens").upsert(records).execute()
    except Exception:
        pass


def is_qr_token_invalidated(token: str) -> tuple[bool, str]:
    """Verifica se um token de QR code foi marcado como desativado ou inválido."""
    if not is_valid_uuid(token):
        return False, ""

    if token in _LOCAL_INVALIDATED_TOKENS:
        return True, _LOCAL_INVALIDATED_TOKENS[token]

    try:
        client = get_supabase_client()
        # Verifica tabela de invalidados
        res = client.table("invalidated_qr_tokens").select("reason").eq("token", token).limit(1).execute().data
        if res:
            _LOCAL_INVALIDATED_TOKENS[token] = res[0].get("reason") or "Registro ou etiqueta excluída"
            return True, _LOCAL_INVALIDATED_TOKENS[token]

        # Verifica tag_units com status retired
        tag_res = client.table("tag_units").select("status, notes").eq("qr_token", token).limit(1).execute().data
        if tag_res and tag_res[0].get("status") == "retired":
            _LOCAL_INVALIDATED_TOKENS[token] = tag_res[0].get("notes") or "Etiqueta inativada ou baixada"
            return True, _LOCAL_INVALIDATED_TOKENS[token]

        return False, ""
    except Exception:
        return False, ""


def delete_single_animal(animal_id: str, organization_id: str | None = None) -> dict[str, Any]:
    """
    Exclui um único animal e todas as suas dependências operacionais,
    invalidando permanentemente seu QR Code.
    """
    if not is_valid_uuid(animal_id):
        raise SupabaseServiceError("Identificador do animal inválido.")
    client = get_supabase_client()

    query = client.table("animals").select("id, ear_tag, qr_code_token, property_id").eq("id", animal_id)
    if organization_id and is_valid_uuid(organization_id):
        query = query.eq("organization_id", organization_id)
    animal_res = query.limit(1).execute().data
    if not animal_res:
        raise SupabaseServiceError("Animal não encontrado.")
    animal = animal_res[0]

    qr_token = animal.get("qr_code_token")
    ear_tag = animal.get("ear_tag", "desconhecido")

    # Invalida o QR Code
    if qr_token:
        record_invalidated_qr_tokens([qr_token], reason=f"Animal #{ear_tag} excluído da plataforma")

    # Exclui dependências em ordem reversa
    for tbl in ("feeding_plans", "management_records", "health_records", "vaccination_records", "vaccination_schedules"):
        try:
            client.table(tbl).delete().eq("animal_id", animal_id).execute()
        except Exception:
            pass

    # Exclui o animal
    try:
        client.table("animals").delete().eq("id", animal_id).execute()
    except Exception as exc:
        raise translate_supabase_error(exc) from exc

    return {"deleted": True, "ear_tag": ear_tag, "qr_token": qr_token}


def delete_farm_operational_data(property_id: str, organization_id: str | None = None) -> dict[str, Any]:
    """
    Exclui TODOS os dados operacionais de uma fazenda de uma vez só:
    animais, registros sanitários, manejos, dietas de cocho, agendamentos, campanhas e lotes,
    tornando TODOS os QR codes correspondentes inválidos.
    A fazenda permanece ativa para novos cadastros.
    """
    if not is_valid_uuid(property_id):
        raise SupabaseServiceError("Propriedade/Fazenda inválida.")
    client = get_supabase_client()

    # 1. Busca todos os animais da fazenda
    anim_query = client.table("animals").select("id, ear_tag, qr_code_token").eq("property_id", property_id)
    if organization_id and is_valid_uuid(organization_id):
        anim_query = anim_query.eq("organization_id", organization_id)
    animals = anim_query.execute().data or []

    animal_ids = [a["id"] for a in animals]
    qr_tokens = [a["qr_code_token"] for a in animals if a.get("qr_code_token")]

    # 2. Invalida todos os QR codes dos animais
    if qr_tokens:
        record_invalidated_qr_tokens(
            qr_tokens,
            reason=f"Dados da fazenda limpos na plataforma ({len(qr_tokens)} animais excluídos)"
        )

    # 3. Exclui dependências vinculadas aos animais
    if animal_ids:
        for tbl in ("feeding_plans", "management_records", "health_records", "vaccination_records", "vaccination_schedules"):
            try:
                client.table(tbl).delete().in_("animal_id", animal_ids).execute()
            except Exception:
                pass

    # 4. Exclui os animais da fazenda
    deleted_animals_count = 0
    try:
        res = client.table("animals").delete().eq("property_id", property_id).execute()
        deleted_animals_count = len(res.data or [])
    except Exception as exc:
        raise translate_supabase_error(exc) from exc

    # 5. Exclui campanhas da fazenda
    try:
        client.table("vaccination_campaigns").delete().eq("property_id", property_id).execute()
    except Exception:
        pass

    # 6. Exclui lotes da fazenda
    deleted_lots_count = 0
    try:
        res_lots = client.table("lots").delete().eq("property_id", property_id).execute()
        deleted_lots_count = len(res_lots.data or [])
    except Exception:
        pass

    return {
        "property_id": property_id,
        "deleted_animals": deleted_animals_count,
        "invalidated_qr_tokens": len(qr_tokens),
        "deleted_lots": deleted_lots_count,
    }


def delete_entire_farm(property_id: str, organization_id: str | None = None) -> dict[str, Any]:
    """
    Exclui uma fazenda inteira e absolutamente todos os seus dados:
    dados operacionais, animais, lotes, protocolos sanitários vinculados,
    perfis de acesso vinculados e o próprio registro da fazenda.
    """
    if not is_valid_uuid(property_id):
        raise SupabaseServiceError("Propriedade/Fazenda inválida.")
    client = get_supabase_client()

    # 1. Limpa os dados operacionais e invalida os QR codes
    op_stats = delete_farm_operational_data(property_id, organization_id)

    # 2. Exclui perfis de acesso vinculados à fazenda
    try:
        client.table("property_access_profiles").delete().eq("property_id", property_id).execute()
    except Exception:
        pass

    # 3. Exclui protocolos sanitários exclusivos desta fazenda
    try:
        proto_rows = client.table("sanitary_protocols").select("id").eq("property_id", property_id).execute().data or []
        proto_ids = [p["id"] for p in proto_rows]
        if proto_ids:
            client.table("sanitary_protocol_rules").delete().in_("protocol_id", proto_ids).execute()
            client.table("sanitary_protocols").delete().in_("id", proto_ids).execute()
    except Exception:
        pass

    # 4. Exclui o registro da propriedade
    try:
        res = client.table("properties").delete().eq("id", property_id).execute()
        if not res.data:
            raise SupabaseServiceError("Fazenda não encontrada para exclusão.")
    except Exception as exc:
        raise translate_supabase_error(exc) from exc

    return {
        "deleted_property": True,
        **op_stats,
    }


def delete_single_lot(lot_id: str) -> bool:
    """Exclui um lote específico desvinculando animais prévios."""
    if not is_valid_uuid(lot_id):
        raise SupabaseServiceError("Lote inválido.")
    client = get_supabase_client()
    try:
        # Desvincula animais que estavam neste lote
        client.table("animals").update({"lot_id": None}).eq("lot_id", lot_id).execute()
        res = client.table("lots").delete().eq("id", lot_id).execute()
        return bool(res.data)
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def delete_single_campaign(campaign_id: str) -> bool:
    """Exclui uma campanha e desassocia ou remove agendamentos pendentes da mesma."""
    if not is_valid_uuid(campaign_id):
        raise SupabaseServiceError("Campanha inválida.")
    client = get_supabase_client()
    try:
        client.table("vaccination_schedules").delete().eq("campaign_id", campaign_id).eq("status", "pendente").execute()
        client.table("vaccination_schedules").update({"campaign_id": None}).eq("campaign_id", campaign_id).execute()
        res = client.table("vaccination_campaigns").delete().eq("id", campaign_id).execute()
        return bool(res.data)
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def delete_single_vaccine(vaccine_id: str) -> bool:
    """Exclui um item preventivo do catálogo se não possuir dependências ativas."""
    if not is_valid_uuid(vaccine_id):
        raise SupabaseServiceError("Item preventivo inválido.")
    client = get_supabase_client()
    try:
        # Verifica se há regras ou agendamentos
        rules = client.table("sanitary_protocol_rules").select("id").eq("vaccine_id", vaccine_id).limit(1).execute().data
        if rules:
            raise SupabaseServiceError("Este item preventivo está em uso por regras de protocolos. Inative-o em vez de excluir.")
        res = client.table("vaccines").delete().eq("id", vaccine_id).execute()
        return bool(res.data)
    except Exception as exc:
        raise translate_supabase_error(exc) from exc
