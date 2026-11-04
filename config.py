import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Configurações centrais da plataforma Animora."""

    APP_NAME: str = "Animora"
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "animora-mvp-dev-secret-key")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip()
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "").strip().rstrip("/")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "True").lower() in ("1", "true", "yes")
    PORT: int = int(os.getenv("PORT", "5000"))

    # Chaves de acesso por nível (Common = público sem PIN | Property = manejo/vacinas | Admin = criação de QR Codes)
    _legacy_pin: str = os.getenv("BOVITRACK_ACCESS_PIN", "").strip()
    PROPERTY_ACCESS_PIN: str = (
        os.getenv("ANIMORA_PROPERTY_PIN", "").strip() or _legacy_pin or "animora2026"
    )
    ADMIN_ACCESS_PIN: str = (
        os.getenv("ANIMORA_ADMIN_PIN", "").strip() or "animora-admin2026"
    )

    IS_CUSTOM_PROPERTY_PIN_CONFIGURED: bool = bool(
        os.getenv("ANIMORA_PROPERTY_PIN", "").strip() or _legacy_pin
    )
    IS_CUSTOM_ADMIN_PIN_CONFIGURED: bool = bool(
        os.getenv("ANIMORA_ADMIN_PIN", "").strip()
    )

    # Alias de compatibilidade
    OPERATOR_ACCESS_PIN: str = PROPERTY_ACCESS_PIN
    IS_CUSTOM_PIN_CONFIGURED: bool = IS_CUSTOM_PROPERTY_PIN_CONFIGURED

    STATIC_DIR: Path = BASE_DIR / "static"
    QRCODES_DIR: Path = STATIC_DIR / "qrcodes"

    # Faixas etárias neutras padrão (utilizadas para Bovinos, Equinos e Ovinos)
    DEFAULT_AGE_BRACKETS: list[dict] = [
        {"slug": "recem_nascido", "name": "Recém-nascido", "min_days": 0, "max_days": 30, "sort_order": 1},
        {"slug": "lactente", "name": "Lactente / Filhote", "min_days": 31, "max_days": 180, "sort_order": 2},
        {"slug": "jovem", "name": "Jovem", "min_days": 181, "max_days": 365, "sort_order": 3},
        {"slug": "adulto", "name": "Adulto", "min_days": 366, "max_days": None, "sort_order": 4},
    ]

    @classmethod
    def is_supabase_configured(cls) -> bool:
        """Verifica se as variáveis obrigatórias do Supabase foram preenchidas."""
        return bool(cls.SUPABASE_URL and cls.SUPABASE_KEY)
