import hmac
from functools import wraps
from typing import Any
from flask import flash, redirect, request, session, url_for

from config import Config
from services.supabase_service import get_supabase_client


ACCESS_LEVEL_LABELS: dict[str, str] = {
    "common": "Common (Consulta Pública)",
    "property": "Property (Manejo & Vacinação)",
    "admin": "Admin (Administração & QR Codes)",
}

ROLE_LABELS: dict[str, str] = {
    "produtor": "Produtor / Gestor da Propriedade",
    "responsavel_tecnico": "Responsável Técnico (Méd. Veterinário)",
    "operador": "Equipe de Campo",
    "admin": "Administrador da Plataforma",
}


def get_access_level() -> str:
    """Retorna o nível de acesso atual da sessão: 'common', 'property' ou 'admin'."""
    if session.get("operator_authenticated") is not True:
        return "common"
    level = str(session.get("access_level") or "property").strip().lower()
    if level in ("property", "admin"):
        return level
    return "property"


def is_property_authenticated() -> bool:
    """Indica se o usuário possui acesso de nível Property ou Admin."""
    return get_access_level() in ("property", "admin")


def is_admin_authenticated() -> bool:
    """Indica se o usuário possui acesso de nível Admin (criação de QR Codes e controle total)."""
    return get_access_level() == "admin"


# Alias de compatibilidade com módulos existentes
is_operator_authenticated = is_property_authenticated


def get_current_operator() -> dict[str, str | None]:
    """Retorna os dados do usuário autenticado (ou visitante Common) na sessão."""
    level = get_access_level()
    default_role = "admin" if level == "admin" else "produtor"
    role = str(session.get("operator_role") or default_role)
    default_name = (
        "Admin Animora"
        if level == "admin"
        else ("Equipe Property" if level == "property" else "Visitante")
    )
    return {
        "name": str(session.get("operator_name") or default_name),
        "access_level": level,
        "access_level_label": ACCESS_LEVEL_LABELS.get(level, "Common"),
        "role": role,
        "role_label": ROLE_LABELS.get(role, "Gestão"),
        "property_id": session.get("property_id"),
        "property_name": session.get("property_name"),
    }


def get_assigned_property_id() -> str | None:
    """Retorna o ID da fazenda vinculada ao perfil de acesso atual (se houver)."""
    return session.get("property_id")


def get_active_filter_property_id(requested_property_id: str | None = None) -> str | None:
    """
    Retorna o ID da propriedade a ser filtrado nas consultas:
    - Se o usuário for Property com fazenda vinculada: SEMPRE retorna a fazenda dele (isolamento total).
    - Se o usuário for Admin: pode filtrar por qualquer fazenda ou None (todas).
    """
    assigned = session.get("property_id")
    if not is_admin_authenticated() and assigned:
        return str(assigned)
    clean_req = (requested_property_id or "").strip()
    return clean_req if clean_req else None


def _resolve_supabase_user_access_level(client: Any, user: Any) -> str:
    """Determina o nível máximo ('property' ou 'admin') de um usuário autenticado via Supabase Auth."""
    user_meta = getattr(user, "user_metadata", None) or {}
    app_meta = getattr(user, "app_metadata", None) or {}
    for meta in (app_meta, user_meta):
        declared = str(meta.get("access_level") or meta.get("role") or "").strip().lower()
        if declared == "admin":
            return "admin"

    try:
        rows = (
            client.table("organization_members")
            .select("role")
            .eq("user_id", str(user.id))
            .eq("is_active", True)
            .execute()
            .data
            or []
        )
        if any(str(r.get("role") or "").lower() == "admin" for r in rows):
            return "admin"
    except Exception:
        pass

    return "property"


def authenticate_operator(
    access_pin: str,
    operator_name: str,
    access_level: str = "property",
    operator_role: str = "produtor",
    email: str | None = None,
) -> tuple[bool, str | None]:
    """
    Valida o acesso de nível Property ou Admin via chaves separadas (.env)
    ou via credenciais de usuário do Supabase Auth (e-mail + senha).
    """
    target_level = (access_level or "property").strip().lower()
    if target_level not in ("property", "admin"):
        target_level = "property"

    default_name = "Admin Animora" if target_level == "admin" else "Gestor Animora"
    clean_name = (operator_name or "").strip() or default_name

    clean_role = (operator_role or ("admin" if target_level == "admin" else "produtor")).strip()
    if clean_role not in ROLE_LABELS:
        clean_role = "admin" if target_level == "admin" else "produtor"
    if target_level == "admin":
        clean_role = "admin"

    clean_pin = (access_pin or "").strip()
    clean_email = (email or "").strip()

    if not clean_pin:
        return False, "Informe a chave de acesso do nível selecionado ou sua senha."

    # Modalidade 1: Login via Supabase Auth (quando e-mail é preenchido)
    if clean_email:
        try:
            client = get_supabase_client()
            auth_res = client.auth.sign_in_with_password({"email": clean_email, "password": clean_pin})
            if auth_res and auth_res.user:
                granted_level = _resolve_supabase_user_access_level(client, auth_res.user)
                if target_level == "admin" and granted_level != "admin":
                    return (
                        False,
                        "Esta conta não possui privilégio Admin em organization_members.",
                    )
                final_level = "admin" if (target_level == "admin" or granted_level == "admin") else "property"
                session["operator_authenticated"] = True
                session["access_level"] = final_level
                session["operator_name"] = clean_name if operator_name.strip() else clean_email
                session["operator_role"] = "admin" if final_level == "admin" else clean_role
                session["supabase_user_id"] = str(auth_res.user.id)
                return True, None
            return False, "Credenciais recusadas pelo Supabase Auth."
        except Exception:
            return False, "E-mail ou senha inválidos no Supabase Auth."

    # Modalidade 2: Perfis de Acesso Vinculados a Fazendas (Criados pelo Admin)
    if target_level == "property":
        try:
            from services.farm_service import find_access_profile_by_pin
            farm_profile = find_access_profile_by_pin(clean_pin)
            if farm_profile:
                session["operator_authenticated"] = True
                session["access_level"] = "property"
                session["operator_name"] = clean_name if operator_name.strip() else farm_profile["name"]
                session["operator_role"] = farm_profile.get("role") or "produtor"
                session["property_id"] = str(farm_profile["property_id"])
                session["property_name"] = farm_profile.get("property_name") or "Fazenda Vinculada"
                return True, None
        except Exception:
            pass

    # Modalidade 3: Chaves separadas por nível no servidor (.env)
    pin_bytes = clean_pin.encode("utf-8")
    admin_pin_bytes = Config.ADMIN_ACCESS_PIN.encode("utf-8")
    prop_pin_bytes = Config.PROPERTY_ACCESS_PIN.encode("utf-8")

    is_admin_match = bool(Config.ADMIN_ACCESS_PIN) and hmac.compare_digest(pin_bytes, admin_pin_bytes)
    is_prop_match = bool(Config.PROPERTY_ACCESS_PIN) and hmac.compare_digest(pin_bytes, prop_pin_bytes)

    if target_level == "admin":
        if is_admin_match:
            session["operator_authenticated"] = True
            session["access_level"] = "admin"
            session["operator_name"] = clean_name
            session["operator_role"] = "admin"
            session.pop("property_id", None)
            session.pop("property_name", None)
            return True, None
        return False, "Chave de acesso Admin incorreta."

    # Nível Property aceita a chave Property mestra (ou a chave Admin)
    if is_prop_match or is_admin_match:
        session["operator_authenticated"] = True
        session["access_level"] = "property" if is_prop_match and not is_admin_match else target_level
        session["operator_name"] = clean_name
        session["operator_role"] = clean_role
        session.pop("property_id", None)
        session.pop("property_name", None)
        return True, None

    return False, "Chave de acesso Property incorreta. Verifique o código informado."


def logout_operator() -> None:
    """Encerra a sessão autenticada, retornando ao nível Common (consulta pública)."""
    for key in (
        "operator_authenticated",
        "access_level",
        "operator_name",
        "operator_role",
        "supabase_user_id",
        "property_id",
        "property_name",
    ):
        session.pop(key, None)


def property_required(view_func: Any) -> Any:
    """Exige nível Property ou Admin (adição/atribuição de animais e gestão sanitária/vacinação)."""
    @wraps(view_func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not is_property_authenticated():
            flash(
                "Esta área requer acesso de nível Property (ou Admin). Identifique-se para continuar.",
                "warning",
            )
            return redirect(
                url_for("operator_login", level="property", next=request.full_path.rstrip("?"))
            )
        return view_func(*args, **kwargs)

    return wrapped


def admin_required(view_func: Any) -> Any:
    """Exige nível Admin (criação de QR Codes e geração de lotes de etiquetas)."""
    @wraps(view_func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not is_admin_authenticated():
            flash(
                "A criação de QR Codes e lotes de etiquetas é exclusiva para o nível Admin.",
                "warning",
            )
            return redirect(
                url_for("operator_login", level="admin", next=request.full_path.rstrip("?"))
            )
        return view_func(*args, **kwargs)

    return wrapped


# Alias de compatibilidade
operator_required = property_required
