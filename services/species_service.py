"""
Metadados zootécnicos centralizados para manejo multi-espécie da plataforma Animora
(Bovinos, Equinos e Ovinos), catálogo preventivo, alojamentos e rotinas dedicadas.
"""

from typing import Any


SPECIES_META: dict[str, dict[str, Any]] = {
    "bovino": {
        "slug": "bovino",
        "label": "Bovino",
        "plural": "Bovinos",
        "icon": "bi-shield-check",
        "emoji": "🐄",
        "badge_class": "badge-species-bovino",
        "tag_hint": "Brinco auricular, botton ou colar com QR Code Animora",
        "default_accommodation": "pasto_piquete",
        "accommodation_placeholder": "Ex.: Piquete 03, Curral Maternidade...",
        "common_breeds": [
            "Nelore",
            "Angus",
            "Brahman",
            "Girolando",
            "Gir Leiteiro",
            "Holandês",
            "Senepol",
            "Guzerá",
            "Tabapuã",
            "Sindi",
            "Jersey",
            "Cruzamento Industrial",
        ],
        "common_coats": [
            "Branca / Cinza (Nelore)",
            "Preta",
            "Vermelha",
            "Malhada (Preto e Branco)",
            "Chitada",
            "Baia",
        ],
        "feeding_warning": None,
    },
    "equino": {
        "slug": "equino",
        "label": "Equino",
        "plural": "Equinos",
        "icon": "bi-award-fill",
        "emoji": "🐎",
        "badge_class": "badge-species-equino",
        "tag_hint": "Placa de baia/cocho, placa de cabresto ou ficha cadastral plastificada com QR Code",
        "default_accommodation": "baia_cocheira",
        "accommodation_placeholder": "Ex.: Baia 04 - Pavilhão Principal, Piquete Tropa...",
        "common_breeds": [
            "Quarto de Milha",
            "Mangalarga Marchador",
            "Crioulo",
            "Campolina",
            "Puro Sangue Inglês (PSI)",
            "Árabe",
            "Appaloosa",
            "Paint Horse",
            "Lusitano",
            "Brasileiro de Hipismo",
            "Muar / Muares",
        ],
        "common_coats": [
            "Alazão",
            "Castanho",
            "Tordilho",
            "Zaino / Preto",
            "Baio",
            "Rosilho",
            "Pampa",
            "Palomino",
            "Lobuno",
        ],
        "feeding_warning": "Atenção ao fracionamento de concentrado por trato e oferta contínua de volumoso/água limpa para prevenção de cólica equina.",
    },
    "ovino": {
        "slug": "ovino",
        "label": "Ovino",
        "plural": "Ovinos",
        "icon": "bi-cloud-sun-fill",
        "emoji": "🐑",
        "badge_class": "badge-species-ovino",
        "tag_hint": "Brinco auricular leve, colar ou placa de aprisco/baia coletiva com QR Code",
        "default_accommodation": "galpao_aprisco",
        "accommodation_placeholder": "Ex.: Aprisco Baia 02, Piquete Ovelhas Matrizes...",
        "common_breeds": [
            "Santa Inês",
            "Dorper",
            "White Dorper",
            "Suffolk",
            "Texel",
            "Ile de France",
            "Morada Nova",
            "Hampshire Down",
            "Corriedale",
            "Bergamácia",
            "Lacaune",
        ],
        "common_coats": [
            "Branca Lanada",
            "Preta / Escura",
            "Vermelha / Castanha",
            "Cabeça Preta (Dorper/Suffolk)",
            "Chitada / Malhada",
            "Deslanado Pelado",
        ],
        "feeding_warning": "ATENÇÃO: Ovinos são altamente sensíveis à intoxicação por COBRE. Utilize exclusivamente sal mineral e rações formulados para ovinos.",
    },
}

SPECIES_CHOICES: dict[str, str] = {k: v["label"] for k, v in SPECIES_META.items()}

TARGET_SPECIES_LABELS: dict[str, str] = {
    "todas": "Todas as espécies",
    "bovino": "Bovinos",
    "equino": "Equinos",
    "ovino": "Ovinos",
}

ACCOMMODATION_TYPE_LABELS: dict[str, str] = {
    "baia_cocheira": "Baia / Cocheira Individual",
    "pasto_piquete": "Pasto / Piquete",
    "galpao_aprisco": "Galpão / Aprisco",
    "confinamento": "Confinamento / Curral de Cocho",
}

REPRODUCTIVE_STATUS_LABELS: dict[str, str] = {
    "nao_informado": "Não informado",
    "inteiro": "Inteiro(a)",
    "castrado": "Castrado",
    "matriz": "Matriz",
    "reprodutor": "Reprodutor / Garanhão / Carneiro",
}

PROPERTY_FOCUS_LABELS: dict[str, str] = {
    "misto": "Fazenda Mista (Multi-Espécie)",
    "corte": "Pecuária de Corte",
    "leite": "Pecuária de Leite",
    "haras": "Haras / Equinocultura",
    "cabanha": "Cabanha / Ovinocultura",
    "esporte_reproducao": "Esporte, Lazer & Reprodução",
}

PROTOCOL_PURPOSE_LABELS: dict[str, str] = {
    "geral": "Sanidade Geral / Preventivo",
    "corte": "Produção de Corte",
    "leite": "Produção de Leite",
    "reproducao": "Reprodução / Matrizes",
    "esporte_trabalho": "Esporte, Trabalho & Lida",
    "la": "Produção de Lã",
}

PREVENTIVE_ITEM_TYPE_META: dict[str, dict[str, str]] = {
    "vacina": {
        "label": "Vacina",
        "plural": "Vacinas",
        "badge_class": "badge-item-vacina",
        "icon": "bi-eyedropper",
        "default_unit": "mL",
        "default_route": "Subcutânea",
    },
    "vermifugo": {
        "label": "Vermífugo / Antiparasitário",
        "plural": "Vermífugos",
        "badge_class": "badge-item-vermifugo",
        "icon": "bi-capsule",
        "default_unit": "mL",
        "default_route": "Oral",
    },
    "exame_preventivo": {
        "label": "Exame Sanitário / Preventivo",
        "plural": "Exames Sanitários",
        "badge_class": "badge-item-exame",
        "icon": "bi-clipboard2-pulse",
        "default_unit": "exame",
        "default_route": "Coleta Laboratorial / Avaliação",
    },
}

MANAGEMENT_ROUTINE_META: dict[str, dict[str, Any]] = {
    "casqueamento": {
        "label": "Casqueamento / Aparação de Cascos",
        "short_label": "Casqueamento",
        "icon": "bi-tools",
        "badge_class": "badge-routine-hoof",
        "species": ("equino", "ovino", "bovino"),
        "default_interval_days": 45,
    },
    "ferrageamento": {
        "label": "Ferrageamento (Ferraduras)",
        "short_label": "Ferrageamento",
        "icon": "bi-magnet",
        "badge_class": "badge-routine-shoeing",
        "species": ("equino",),
        "default_interval_days": 40,
    },
    "tosquia": {
        "label": "Tosquia ( Manejo de Lã / Velo )",
        "short_label": "Tosquia",
        "icon": "bi-scissors",
        "badge_class": "badge-routine-shearing",
        "species": ("ovino",),
        "default_interval_days": 180,
    },
    "pesagem": {
        "label": "Pesagem & Acompanhamento Corporal",
        "short_label": "Pesagem",
        "icon": "bi-speedometer2",
        "badge_class": "badge-routine-weight",
        "species": ("bovino", "equino", "ovino"),
        "default_interval_days": 30,
    },
    "odontologia": {
        "label": "Odontologia / Nivelamento Dentário",
        "short_label": "Odontologia",
        "icon": "bi-heart-pulse",
        "badge_class": "badge-routine-dental",
        "species": ("equino",),
        "default_interval_days": 180,
    },
    "escore_famacha": {
        "label": "Avaliação Famacha (Grau 1 a 5)",
        "short_label": "Famacha",
        "icon": "bi-eye-fill",
        "badge_class": "badge-routine-famacha",
        "species": ("ovino",),
        "default_interval_days": 21,
    },
}


def normalize_species(value: str | None) -> str:
    """Retorna uma espécie válida ('bovino', 'equino' ou 'ovino'), usando 'bovino' como padrão."""
    clean = str(value or "").strip().lower()
    if clean in SPECIES_META:
        return clean
    return "bovino"


def get_species_meta(species: str | None) -> dict[str, Any]:
    return SPECIES_META[normalize_species(species)]


def get_routines_for_species(species: str | None) -> dict[str, dict[str, Any]]:
    sp = normalize_species(species)
    return {
        k: meta
        for k, meta in MANAGEMENT_ROUTINE_META.items()
        if sp in meta["species"]
    }


def enrich_animal_species_and_housing(animal: dict[str, Any]) -> dict[str, Any]:
    """Adiciona rótulos de espécie, alojamento e status reprodutivo ao dicionário do animal."""
    enriched = dict(animal)
    sp = normalize_species(enriched.get("species"))
    meta = SPECIES_META[sp]
    enriched["species"] = sp
    enriched["species_label"] = meta["label"]
    enriched["species_plural"] = meta["plural"]
    enriched["species_icon"] = meta["icon"]
    enriched["species_emoji"] = meta["emoji"]
    enriched["species_badge_class"] = meta["badge_class"]

    acc_type = str(enriched.get("accommodation_type") or "").strip().lower()
    acc_name = str(enriched.get("accommodation_name") or "").strip()
    acc_type_label = ACCOMMODATION_TYPE_LABELS.get(acc_type, "")
    if acc_name and acc_type_label:
        housing_display = f"{acc_name} ({acc_type_label})"
    elif acc_name:
        housing_display = acc_name
    elif acc_type_label:
        housing_display = acc_type_label
    else:
        housing_display = ""

    enriched["accommodation_type_label"] = acc_type_label
    enriched["housing_display"] = housing_display

    repro = str(enriched.get("reproductive_status") or "nao_informado").strip().lower()
    enriched["reproductive_status_label"] = REPRODUCTIVE_STATUS_LABELS.get(repro, "Não informado")
    return enriched
