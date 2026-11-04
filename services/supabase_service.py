import os
import uuid
from typing import Any
from dotenv import load_dotenv
from supabase import Client, create_client

from config import BASE_DIR


class SupabaseServiceError(Exception):
    """Exceção amigável para falhas de configuração ou comunicação com o Supabase."""


class MigrationRequiredError(SupabaseServiceError):
    """Exceção disparada quando as tabelas do Módulo Sanitário ainda não foram criadas no Supabase."""


class TagMigrationRequiredError(MigrationRequiredError):
    """Exceção disparada quando as tabelas tag_units / tag_batches ainda não foram criadas no Supabase."""


class MultiSpeciesMigrationRequiredError(MigrationRequiredError):
    """Exceção disparada quando a migration 004_multi_species_management.sql ainda não foi executada."""


class DuplicateEarTagError(SupabaseServiceError):
    """Exceção disparada quando já existe um animal com o mesmo número de identificação/etiqueta."""


_client: Client | None = None
_cached_credentials: tuple[str, str] | None = None

SANITARY_TABLES = (
    "organizations",
    "properties",
    "lots",
    "age_classifications",
    "vaccines",
    "sanitary_protocols",
    "sanitary_protocol_rules",
    "animal_protocols",
    "vaccination_campaigns",
    "vaccination_schedules",
    "vaccination_records",
    "health_records",
)


def get_supabase_client() -> Client:
    """Inicializa e retorna o cliente Supabase, validando as credenciais de ambiente."""
    global _client, _cached_credentials

    load_dotenv(BASE_DIR / ".env", override=True)
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()

    if not url or not key or "seu-projeto.supabase.co" in url:
        raise SupabaseServiceError(
            "Credenciais do Supabase não configuradas. Defina SUPABASE_URL e SUPABASE_KEY no arquivo .env."
        )

    if _client is None or _cached_credentials != (url, key):
        try:
            _client = create_client(url, key)
            _cached_credentials = (url, key)
        except Exception as exc:
            raise SupabaseServiceError(
                f"Não foi possível inicializar a conexão com o Supabase: {exc}"
            ) from exc

    return _client


def is_valid_uuid(value: str | None) -> bool:
    """Verifica se uma string possui formato válido de UUID."""
    if not value:
        return False
    try:
        uuid.UUID(str(value).strip())
        return True
    except (ValueError, TypeError, AttributeError):
        return False


_is_valid_uuid = is_valid_uuid


def translate_supabase_error(exc: Exception) -> SupabaseServiceError:
    """Converte exceções técnicas do cliente/rede em mensagens claras para o usuário."""
    if isinstance(exc, SupabaseServiceError):
        return exc

    raw = str(exc)
    raw_lower = raw.lower()

    if "23505" in raw or "duplicate key" in raw_lower:
        if "tag_units_organization_id_tag_number_key" in raw_lower or "tag_number" in raw_lower:
            return SupabaseServiceError(
                "Uma ou mais numerações de etiqueta informadas já existem nesta organização. Escolha uma faixa livre."
            )
        if "tag_units_qr_token_key" in raw_lower or "qr_token" in raw_lower:
            return SupabaseServiceError("Conflito de token exclusivo de QR Code detectado. Tente gerar novamente.")
        if "animals_ear_tag_key" in raw_lower or "ear_tag" in raw_lower:
            return DuplicateEarTagError(
                "Já existe um animal cadastrado com este número de brinco. Informe uma identificação única."
            )
        if "idx_uq_schedule_campaign_animal" in raw_lower:
            return SupabaseServiceError("Este animal já possui um agendamento ativo nesta campanha.")
        if "idx_uq_schedule_animal_rule_dose" in raw_lower:
            return SupabaseServiceError("Já existe um agendamento para esta regra e dose neste animal.")
        if "lots_property_id_name_key" in raw_lower:
            return SupabaseServiceError("Já existe um lote com este nome na propriedade selecionada.")
        return SupabaseServiceError("Registro duplicado detectado pelo banco de dados.")

    if "23514" in raw or "check constraint" in raw_lower:
        if any(
            k in raw_lower
            for k in ("production_focus", "animal_category", "purpose", "dosage", "species")
        ):
            return MultiSpeciesMigrationRequiredError(
                "Para utilizar espécies, finalidades ou categorias expandidas da Animora, "
                "abra o SQL Editor do Supabase e execute database/migrations/004_multi_species_management.sql."
            )

    if "pgrst205" in raw_lower or "pgrst204" in raw_lower or "42p01" in raw_lower or "42703" in raw_lower or "does not exist" in raw_lower:
        if any(
            col in raw_lower
            for col in (
                "management_records",
                "feeding_plans",
                "coat_color",
                "secondary_id",
                "reproductive_status",
                "accommodation_type",
                "accommodation_name",
                "target_species",
                "item_type",
                "exam_result",
                "'species'",
                "\"species\"",
                "animals.species",
            )
        ):
            return MultiSpeciesMigrationRequiredError(
                "As tabelas/colunas de Manejo Multi-Espécie ainda não foram criadas no Supabase. "
                "Abra o SQL Editor do Supabase e execute database/migrations/004_multi_species_management.sql."
            )
        if "tag_units" in raw_lower or "tag_batches" in raw_lower:
            return TagMigrationRequiredError(
                "As tabelas de controle de etiquetas ('tag_units' e 'tag_batches') ainda não foram criadas no Supabase. "
                "Abra o SQL Editor do Supabase e execute database/migrations/003_tag_batches_and_units.sql."
            )
        if any(tbl in raw_lower for tbl in SANITARY_TABLES) or any(
            col in raw_lower
            for col in ("organization_id", "property_id", "lot_id", "sanitary_onboarding_mode", "inclusion_date", "animals.status")
        ):
            return MigrationRequiredError(
                "As tabelas/colunas do Módulo Sanitário ainda não foram criadas no Supabase. "
                "Abra o SQL Editor do Supabase e execute database/migrations/001_sanitary_module.sql "
                "(e opcionalmente database/seeds/002_demo_data.sql para dados demonstrativos)."
            )
        if "animals" in raw_lower:
            return SupabaseServiceError(
                "A tabela 'animals' ainda não foi encontrada no Supabase. Execute database/schema.sql no SQL Editor do Supabase."
            )

    if "42501" in raw or "row-level security" in raw_lower:
        return SupabaseServiceError(
            "Permissão negada pelo Row Level Security (RLS) no Supabase. "
            "No backend Flask utilize a chave service_role no arquivo .env ou configure a filiação em organization_members."
        )

    if any(term in raw_lower for term in ("connecterror", "timed out", "timeout", "name or service not known", "getaddrinfo")):
        return SupabaseServiceError(
            "Falha de conexão com o Supabase. Verifique sua internet e se a SUPABASE_URL está correta."
        )

    if "invalid api key" in raw_lower or "jwt" in raw_lower or "401" in raw:
        return SupabaseServiceError(
            "Chave de acesso recusada pelo Supabase. Verifique a variável SUPABASE_KEY no arquivo .env."
        )

    return SupabaseServiceError(f"Erro ao comunicar com o banco de dados Supabase: {raw}")


_translate_supabase_error = translate_supabase_error


def count_animals(organization_id: str | None = None, property_id: str | None = None) -> int:
    """Retorna o total de bovinos cadastrados no Supabase."""
    try:
        client = get_supabase_client()
        query = client.table("animals").select("id", count="exact")
        if organization_id and is_valid_uuid(organization_id):
            query = query.eq("organization_id", organization_id)
        if property_id and is_valid_uuid(property_id):
            query = query.eq("property_id", property_id)
        response = query.limit(1).execute()
        if response.count is not None:
            return int(response.count)
        return len(response.data or [])
    except Exception as exc:
        err = translate_supabase_error(exc)
        if isinstance(err, MigrationRequiredError) and (organization_id or property_id):
            return count_animals()
        raise err from exc


def list_animals(
    limit: int | None = None,
    organization_id: str | None = None,
    property_id: str | None = None,
    lot_id: str | None = None,
    species: str | None = None,
    only_active: bool = False,
) -> list[dict[str, Any]]:
    """Lista os animais cadastrados em ordem decrescente de cadastro, com filtros opcionais."""
    clean_species = (species or "").strip().lower()
    if clean_species in ("", "todas", "todos"):
        clean_species = ""

    try:
        client = get_supabase_client()
        query = client.table("animals").select("*").order("created_at", desc=True)
        if organization_id and is_valid_uuid(organization_id):
            query = query.eq("organization_id", organization_id)
        if property_id and is_valid_uuid(property_id):
            query = query.eq("property_id", property_id)
        if lot_id and is_valid_uuid(lot_id):
            query = query.eq("lot_id", lot_id)
        if clean_species:
            query = query.eq("species", clean_species)
        if only_active:
            query = query.eq("status", "ativo")
        if limit is not None:
            query = query.limit(limit)
        response = query.execute()
        return response.data or []
    except Exception as exc:
        err = translate_supabase_error(exc)
        if isinstance(err, MultiSpeciesMigrationRequiredError) and clean_species:
            rows = list_animals(
                limit=None,
                organization_id=organization_id,
                property_id=property_id,
                lot_id=lot_id,
                species=None,
                only_active=only_active,
            )
            filtered = [r for r in rows if str(r.get("species") or "bovino").lower() == clean_species]
            return filtered[:limit] if limit is not None else filtered
        if isinstance(err, MigrationRequiredError) and any((organization_id, property_id, lot_id, only_active)):
            client = get_supabase_client()
            q_fallback = client.table("animals").select("*").order("created_at", desc=True)
            if limit is not None:
                q_fallback = q_fallback.limit(limit)
            return q_fallback.execute().data or []
        raise err from exc


def ear_tag_exists(ear_tag: str) -> bool:
    """Verifica se já existe um animal registrado com o mesmo código de etiqueta/identificação."""
    try:
        client = get_supabase_client()
        response = (
            client.table("animals")
            .select("id")
            .eq("ear_tag", ear_tag.strip())
            .limit(1)
            .execute()
        )
        return bool(response.data)
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def create_animal(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Persiste um novo animal (Bovino, Equino ou Ovino) na tabela 'animals' do Supabase.
    Garante unicidade da etiqueta, vínculo com propriedade/lote, alojamento e modo sanitário.
    """
    ear_tag = str(payload.get("ear_tag", "")).strip()
    if ear_tag_exists(ear_tag):
        raise DuplicateEarTagError(
            f"Já existe um animal cadastrado com a etiqueta/identificador '{ear_tag}'. Informe outro código."
        )

    animal_id = payload.get("id") or str(uuid.uuid4())
    qr_code_token = payload.get("qr_code_token") or str(uuid.uuid4())
    species = str(payload.get("species") or "bovino").strip().lower()
    if species not in ("bovino", "equino", "ovino"):
        species = "bovino"

    base_record: dict[str, Any] = {
        "id": animal_id,
        "ear_tag": ear_tag,
        "name": payload.get("name") or None,
        "sex": payload["sex"],
        "breed": payload["breed"],
        "birth_date": payload["birth_date"],
        "initial_weight": payload.get("initial_weight"),
        "notes": payload.get("notes") or None,
        "qr_code_token": qr_code_token,
    }

    extended_fields = {
        "organization_id": payload.get("organization_id") or None,
        "property_id": payload.get("property_id") or None,
        "lot_id": payload.get("lot_id") or None,
        "status": payload.get("status") or "ativo",
        "origin_type": payload.get("origin_type") or "nascido_propriedade",
        "sanitary_onboarding_mode": payload.get("sanitary_onboarding_mode") or "acompanhamento_nascimento",
        "inclusion_date": payload.get("inclusion_date") or None,
        "initial_sanitary_notes": payload.get("initial_sanitary_notes") or None,
    }

    multispecies_fields = {
        "species": species,
        "coat_color": payload.get("coat_color") or None,
        "secondary_id": payload.get("secondary_id") or None,
        "reproductive_status": payload.get("reproductive_status") or None,
        "accommodation_type": payload.get("accommodation_type") or None,
        "accommodation_name": payload.get("accommodation_name") or None,
    }

    sanitary_record = {**base_record, **{k: v for k, v in extended_fields.items() if v is not None}}
    full_record = {**sanitary_record, **{k: v for k, v in multispecies_fields.items() if v is not None}}

    try:
        client = get_supabase_client()
        response = client.table("animals").insert(full_record).execute()
        if not response.data:
            raise SupabaseServiceError("O Supabase não retornou os dados do animal após a inserção.")
        return response.data[0]
    except Exception as exc:
        err = translate_supabase_error(exc)
        if isinstance(err, MultiSpeciesMigrationRequiredError):
            if species != "bovino":
                raise err from exc
            try:
                client = get_supabase_client()
                response = client.table("animals").insert(sanitary_record).execute()
                if response.data:
                    return response.data[0]
            except Exception as inner_001_exc:
                err = translate_supabase_error(inner_001_exc)
        if isinstance(err, MigrationRequiredError) and not isinstance(err, MultiSpeciesMigrationRequiredError):
            # Fallback compatível caso a migration 001 ainda não tenha sido aplicada
            try:
                client = get_supabase_client()
                response = client.table("animals").insert(base_record).execute()
                if response.data:
                    return response.data[0]
            except Exception as inner_exc:
                raise translate_supabase_error(inner_exc) from inner_exc
        raise err from exc


def update_animal_sanitary_profile(animal_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Atualiza propriedade, lote, alojamento/baia ou modo de acompanhamento sanitário de um animal existente."""
    if not is_valid_uuid(animal_id):
        raise SupabaseServiceError("Identificador do animal inválido.")

    allowed_keys = {
        "property_id",
        "lot_id",
        "status",
        "origin_type",
        "sanitary_onboarding_mode",
        "inclusion_date",
        "initial_sanitary_notes",
        "species",
        "coat_color",
        "secondary_id",
        "reproductive_status",
        "accommodation_type",
        "accommodation_name",
        "initial_weight",
        "notes",
        "name",
        "breed",
    }
    clean_updates = {k: v for k, v in updates.items() if k in allowed_keys}
    if not clean_updates:
        animal = get_animal_by_token_or_id(animal_id)
        if not animal:
            raise SupabaseServiceError("Animal não encontrado.")
        return animal

    try:
        client = get_supabase_client()
        response = (
            client.table("animals")
            .update(clean_updates)
            .eq("id", animal_id)
            .execute()
        )
        if not response.data:
            raise SupabaseServiceError("Animal não encontrado para atualização.")
        return response.data[0]
    except Exception as exc:
        err = translate_supabase_error(exc)
        if isinstance(err, MultiSpeciesMigrationRequiredError):
            legacy_keys = {
                "property_id",
                "lot_id",
                "status",
                "origin_type",
                "sanitary_onboarding_mode",
                "inclusion_date",
                "initial_sanitary_notes",
                "initial_weight",
                "notes",
                "name",
                "breed",
            }
            fallback_updates = {k: v for k, v in clean_updates.items() if k in legacy_keys}
            if fallback_updates and clean_updates.get("species", "bovino") == "bovino":
                res = get_supabase_client().table("animals").update(fallback_updates).eq("id", animal_id).execute()
                if res.data:
                    return res.data[0]
        raise err from exc


def get_animal_by_ear_tag(ear_tag: str) -> dict[str, Any] | None:
    """Busca um animal pelo número de brinco/etiqueta (case-insensitive) para consulta pública."""
    clean_tag = (ear_tag or "").strip()
    if not clean_tag:
        return None
    # Escapa curingas de LIKE para comparação exata case-insensitive
    escaped_tag = clean_tag.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    try:
        client = get_supabase_client()
        res = (
            client.table("animals")
            .select("*")
            .ilike("ear_tag", escaped_tag)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def get_animal_by_token_or_id(identifier: str) -> dict[str, Any] | None:
    """
    Busca um animal pelo qr_code_token (utilizado na URL do QR Code)
    ou pelo id (UUID primário). Retorna None caso não exista ou o formato não seja UUID.
    """
    clean_id = (identifier or "").strip()
    if not clean_id or not is_valid_uuid(clean_id):
        return None

    try:
        client = get_supabase_client()

        by_token = (
            client.table("animals")
            .select("*")
            .eq("qr_code_token", clean_id)
            .limit(1)
            .execute()
        )
        if by_token.data:
            return by_token.data[0]

        by_id = (
            client.table("animals")
            .select("*")
            .eq("id", clean_id)
            .limit(1)
            .execute()
        )
        if by_id.data:
            return by_id.data[0]

        return None
    except Exception as exc:
        raise translate_supabase_error(exc) from exc
