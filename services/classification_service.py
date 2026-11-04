from datetime import date, datetime
from typing import Any

from config import Config
from services.species_service import enrich_animal_species_and_housing


AGE_CATEGORY_LABELS: dict[str, str] = {
    "todas": "Todas as categorias",
    "recem_nascido": "Recém-nascido (0 a 30 dias)",
    "lactente": "Lactente / Filhote (31 a 180 dias)",
    "jovem": "Jovem (181 a 365 dias)",
    "adulto": "Adulto (acima de 365 dias)",
}

AGE_BADGE_CLASSES: dict[str, str] = {
    "recem_nascido": "badge-age-newborn",
    "lactente": "badge-age-calf",
    "bezerro": "badge-age-calf",
    "jovem": "badge-age-young",
    "adulto": "badge-age-adult",
}


def normalize_age_slug(slug: str | None) -> str:
    """Normaliza slugs legados ('bezerro') para o termo neutro multi-espécie ('lactente')."""
    clean = str(slug or "").strip().lower()
    if clean == "bezerro":
        return "lactente"
    return clean or "adulto"


def parse_iso_date(value: str | date | None) -> date | None:
    """Converte string ISO (YYYY-MM-DD...) ou objeto date em date."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value).strip()[:10]
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def calculate_age_days(birth_date: str | date | None, ref_date: date | None = None) -> int:
    """Calcula dinamicamente a idade do animal em dias com base na data de nascimento."""
    parsed_birth = parse_iso_date(birth_date)
    if not parsed_birth:
        return 0
    reference = ref_date or date.today()
    delta = (reference - parsed_birth).days
    return max(0, delta)


def format_age_label(age_days: int) -> str:
    """Formata a idade em dias para leitura amigável no campo."""
    if age_days <= 0:
        return "0 dias (nascido hoje)"
    if age_days == 1:
        return "1 dia"
    if age_days <= 45:
        return f"{age_days} dias"
    if age_days <= 365:
        months = age_days // 30
        rem_days = age_days % 30
        m_label = "mês" if months == 1 else "meses"
        if rem_days == 0:
            return f"{months} {m_label} ({age_days}d)"
        return f"{months} {m_label} e {rem_days}d ({age_days}d)"

    years = age_days // 365
    rem_months = (age_days % 365) // 30
    y_label = "ano" if years == 1 else "anos"
    if rem_months == 0:
        return f"{years} {y_label} ({age_days}d)"
    m_label = "mês" if rem_months == 1 else "meses"
    return f"{years} {y_label} e {rem_months} {m_label}"


def classify_age_days(
    age_days: int,
    brackets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Identifica a faixa etária neutra do animal a partir das faixas configuradas:
    - Recém-nascido: 0 a 30 dias
    - Lactente / Filhote: 31 a 180 dias
    - Jovem: 181 a 365 dias
    - Adulto: acima de 365 dias
    """
    active_brackets = brackets or Config.DEFAULT_AGE_BRACKETS
    ordered = sorted(active_brackets, key=lambda b: (int(b.get("sort_order", 99)), int(b.get("min_days", 0))))

    for bracket in ordered:
        if not bracket.get("is_active", True):
            continue
        min_d = int(bracket.get("min_days", 0))
        max_d = bracket.get("max_days")
        if age_days >= min_d and (max_d is None or age_days <= int(max_d)):
            raw_slug = str(bracket.get("slug", "adulto"))
            slug = normalize_age_slug(raw_slug)
            raw_name = str(bracket.get("name", slug.title()))
            if raw_slug.lower() == "bezerro" or raw_name.strip().lower() == "bezerro":
                raw_name = "Lactente / Filhote"
            return {
                "slug": slug,
                "name": raw_name,
                "min_days": min_d,
                "max_days": int(max_d) if max_d is not None else None,
                "badge_class": AGE_BADGE_CLASSES.get(slug, "badge-age-adult"),
            }

    return {
        "slug": "adulto",
        "name": "Adulto",
        "min_days": 366,
        "max_days": None,
        "badge_class": "badge-age-adult",
    }


def enrich_animal_with_age(
    animal: dict[str, Any],
    brackets: list[dict[str, Any]] | None = None,
    ref_date: date | None = None,
) -> dict[str, Any]:
    """Enriquece um dicionário de animal com idade, faixa etária neutra, espécie e alojamento."""
    enriched = enrich_animal_species_and_housing(animal)
    age_days = calculate_age_days(enriched.get("birth_date"), ref_date=ref_date)
    classification = classify_age_days(age_days, brackets=brackets)

    enriched["age_days"] = age_days
    enriched["age_label"] = format_age_label(age_days)
    enriched["age_category"] = classification["slug"]
    enriched["age_category_name"] = classification["name"]
    enriched["age_badge_class"] = classification["badge_class"]
    return enriched


def enrich_animals_list(
    animals: list[dict[str, Any]],
    brackets: list[dict[str, Any]] | None = None,
    ref_date: date | None = None,
) -> list[dict[str, Any]]:
    """Enriquece uma lista de animais com idade, categoria etária neutra, espécie e alojamento."""
    return [enrich_animal_with_age(a, brackets=brackets, ref_date=ref_date) for a in animals]


def filter_animals_by_age_category(
    animals: list[dict[str, Any]],
    category_slug: str | None,
) -> list[dict[str, Any]]:
    """Filtra animais já enriquecidos pela categoria etária selecionada."""
    clean = (category_slug or "").strip().lower()
    if not clean or clean == "todas":
        return animals
    target = normalize_age_slug(clean)
    return [a for a in animals if normalize_age_slug(a.get("age_category")) == target]


def filter_animals_by_species(
    animals: list[dict[str, Any]],
    species_slug: str | None,
) -> list[dict[str, Any]]:
    """Filtra animais pela espécie ('bovino', 'equino', 'ovino' ou 'todas')."""
    clean = (species_slug or "").strip().lower()
    if not clean or clean in ("todas", "todos"):
        return animals
    return [a for a in animals if str(a.get("species") or "bovino").lower() == clean]


def summarize_age_categories(animals: list[dict[str, Any]]) -> dict[str, int]:
    """Calcula os totais por faixa etária e por espécie a partir de uma lista de animais."""
    counts = {
        "total": len(animals),
        "recem_nascido": 0,
        "lactente": 0,
        "bezerro": 0,  # alias de compatibilidade
        "jovem": 0,
        "adulto": 0,
        "bovino": 0,
        "equino": 0,
        "ovino": 0,
    }
    for animal in animals:
        cat = animal.get("age_category")
        if cat is None:
            age_d = calculate_age_days(animal.get("birth_date"))
            cat = classify_age_days(age_d)["slug"]
        norm_cat = normalize_age_slug(cat)
        if norm_cat in counts:
            counts[norm_cat] += 1
        sp = str(animal.get("species") or "bovino").strip().lower()
        if sp in ("bovino", "equino", "ovino"):
            counts[sp] += 1
        else:
            counts["bovino"] += 1
    counts["bezerro"] = counts["lactente"]
    return counts
