import re
import uuid
from datetime import datetime
from typing import Any

from services.qrcode_service import build_animal_public_url, ensure_qrcode_exists, generate_animal_qrcode
from services.supabase_service import (
    SupabaseServiceError,
    TagMigrationRequiredError,
    get_supabase_client,
    is_valid_uuid,
    translate_supabase_error,
)


TAG_STATUS_META: dict[str, dict[str, str]] = {
    "available": {
        "label": "Disponível",
        "badge_class": "badge-status-applied",
        "icon": "bi-check2-circle",
    },
    "assigned": {
        "label": "Reservada / Atribuída",
        "badge_class": "badge-status-upcoming",
        "icon": "bi-bookmark-check",
    },
    "activated": {
        "label": "Ativada (Em Animal)",
        "badge_class": "badge-age-newborn",
        "icon": "bi-link-45deg",
    },
    "retired": {
        "label": "Inativada / Baixada",
        "badge_class": "badge-status-cancelled",
        "icon": "bi-slash-circle",
    },
}

PAGE_FORMATS: dict[str, dict[str, Any]] = {
    "a4_portrait": {"name": "A4 Retrato (210 × 297 mm)", "width_mm": 210.0, "height_mm": 297.0},
    "a4_landscape": {"name": "A4 Paisagem (297 × 210 mm)", "width_mm": 297.0, "height_mm": 210.0},
    "letter_portrait": {"name": "Carta / Letter (215,9 × 279,4 mm)", "width_mm": 215.9, "height_mm": 279.4},
    "a5_portrait": {"name": "A5 Retrato (148 × 210 mm)", "width_mm": 148.0, "height_mm": 210.0},
    "thermal_100x150": {"name": "Etiqueta Logística / Rolo (100 × 150 mm)", "width_mm": 100.0, "height_mm": 150.0},
    "custom": {"name": "Tamanho de Folha Personalizado (mm)", "width_mm": 210.0, "height_mm": 297.0},
}

LABEL_PRESETS: dict[str, dict[str, Any]] = {
    "a4_24_standard": {
        "name": "A4 Padrão — 24 Etiquetas (3×8 • 63,5 × 33,9 mm)",
        "page_format": "a4_portrait",
        "page_width_mm": 210.0,
        "page_height_mm": 297.0,
        "label_width_mm": 63.5,
        "label_height_mm": 33.9,
        "gap_x_mm": 2.5,
        "gap_y_mm": 0.0,
        "margin_top_mm": 12.9,
        "margin_right_mm": 7.2,
        "margin_bottom_mm": 12.9,
        "margin_left_mm": 7.2,
        "columns": 3,
        "rows": 8,
        "qr_size_mm": 23.0,
        "font_size_pt": 11.5,
        "show_border": True,
    },
    "a4_14_medium": {
        "name": "A4 Média — 14 Etiquetas (2×7 • 99,0 × 38,1 mm)",
        "page_format": "a4_portrait",
        "page_width_mm": 210.0,
        "page_height_mm": 297.0,
        "label_width_mm": 99.0,
        "label_height_mm": 38.1,
        "gap_x_mm": 2.0,
        "gap_y_mm": 0.0,
        "margin_top_mm": 15.1,
        "margin_right_mm": 5.0,
        "margin_bottom_mm": 15.2,
        "margin_left_mm": 5.0,
        "columns": 2,
        "rows": 7,
        "qr_size_mm": 27.0,
        "font_size_pt": 14.0,
        "show_border": True,
    },
    "a4_8_large": {
        "name": "A4 Grande Campo — 8 Etiquetas (2×4 • 95,0 × 65,0 mm)",
        "page_format": "a4_portrait",
        "page_width_mm": 210.0,
        "page_height_mm": 297.0,
        "label_width_mm": 95.0,
        "label_height_mm": 65.0,
        "gap_x_mm": 4.0,
        "gap_y_mm": 4.0,
        "margin_top_mm": 12.5,
        "margin_right_mm": 8.0,
        "margin_bottom_mm": 12.5,
        "margin_left_mm": 8.0,
        "columns": 2,
        "rows": 4,
        "qr_size_mm": 38.0,
        "font_size_pt": 17.0,
        "show_border": True,
    },
    "a4_40_compact": {
        "name": "A4 Compacta — 40 Etiquetas (4×10 • 48,5 × 25,4 mm)",
        "page_format": "a4_portrait",
        "page_width_mm": 210.0,
        "page_height_mm": 297.0,
        "label_width_mm": 48.5,
        "label_height_mm": 25.4,
        "gap_x_mm": 0.0,
        "gap_y_mm": 0.0,
        "margin_top_mm": 21.5,
        "margin_right_mm": 8.0,
        "margin_bottom_mm": 21.5,
        "margin_left_mm": 8.0,
        "columns": 4,
        "rows": 10,
        "qr_size_mm": 17.5,
        "font_size_pt": 9.5,
        "show_border": True,
    },
    "thermal_60x40": {
        "name": "Rolo Térmico Individual — 1×1 (60,0 × 40,0 mm)",
        "page_format": "custom",
        "page_width_mm": 64.0,
        "page_height_mm": 44.0,
        "label_width_mm": 60.0,
        "label_height_mm": 40.0,
        "gap_x_mm": 0.0,
        "gap_y_mm": 0.0,
        "margin_top_mm": 2.0,
        "margin_right_mm": 2.0,
        "margin_bottom_mm": 2.0,
        "margin_left_mm": 2.0,
        "columns": 1,
        "rows": 1,
        "qr_size_mm": 26.0,
        "font_size_pt": 12.5,
        "show_border": False,
    },
    "custom": {
        "name": "Dimensões Personalizadas (Livre em mm)",
        "page_format": "a4_portrait",
        "page_width_mm": 210.0,
        "page_height_mm": 297.0,
        "label_width_mm": 63.5,
        "label_height_mm": 33.9,
        "gap_x_mm": 2.5,
        "gap_y_mm": 0.0,
        "margin_top_mm": 12.9,
        "margin_right_mm": 7.2,
        "margin_bottom_mm": 12.9,
        "margin_left_mm": 7.2,
        "columns": 3,
        "rows": 8,
        "qr_size_mm": 23.0,
        "font_size_pt": 11.5,
        "show_border": True,
    },
}


def _parse_float(val: Any, default: float) -> float:
    if val is None or str(val).strip() == "":
        return default
    return round(float(str(val).strip().replace(",", ".")), 2)


def _parse_int(val: Any, default: int) -> int:
    if val is None or str(val).strip() == "":
        return default
    return int(float(str(val).strip().replace(",", ".")))


def validate_and_normalize_layout(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Valida e normaliza todas as dimensões em milímetros da página e das etiquetas,
    impedindo cortes, sobreposições, estouro de margens ou QR Codes ilegíveis.
    """
    preset_key = str(raw.get("preset") or "a4_24_standard").strip()
    if preset_key not in LABEL_PRESETS:
        preset_key = "custom"
    base = LABEL_PRESETS[preset_key]

    page_format = str(raw.get("page_format") or base["page_format"]).strip()
    if page_format not in PAGE_FORMATS:
        page_format = "custom"

    try:
        if page_format != "custom":
            page_w = PAGE_FORMATS[page_format]["width_mm"]
            page_h = PAGE_FORMATS[page_format]["height_mm"]
        else:
            page_w = _parse_float(raw.get("page_width_mm"), base["page_width_mm"])
            page_h = _parse_float(raw.get("page_height_mm"), base["page_height_mm"])

        label_w = _parse_float(raw.get("label_width_mm"), base["label_width_mm"])
        label_h = _parse_float(raw.get("label_height_mm"), base["label_height_mm"])
        gap_x = _parse_float(raw.get("gap_x_mm"), base["gap_x_mm"])
        gap_y = _parse_float(raw.get("gap_y_mm"), base["gap_y_mm"])
        margin_top = _parse_float(raw.get("margin_top_mm"), base["margin_top_mm"])
        margin_right = _parse_float(raw.get("margin_right_mm"), base["margin_right_mm"])
        margin_bottom = _parse_float(raw.get("margin_bottom_mm"), base["margin_bottom_mm"])
        margin_left = _parse_float(raw.get("margin_left_mm"), base["margin_left_mm"])
        columns = _parse_int(raw.get("columns"), base["columns"])
        rows = _parse_int(raw.get("rows"), base["rows"])
        qr_size = _parse_float(raw.get("qr_size_mm"), base["qr_size_mm"])
        font_size = _parse_float(raw.get("font_size_pt"), base["font_size_pt"])
    except (ValueError, TypeError) as exc:
        raise SupabaseServiceError("Informe valores numéricos válidos para as dimensões da etiqueta e da página.") from exc

    show_border = str(raw.get("show_border", base["show_border"])).lower() in ("1", "true", "on", "yes")

    errors: list[str] = []
    if not (30.0 <= page_w <= 1000.0 and 25.0 <= page_h <= 1500.0):
        errors.append("As dimensões da folha devem estar entre 30×25 mm e 1000×1500 mm.")
    if not (22.0 <= label_w <= page_w and 16.0 <= label_h <= page_h):
        errors.append("A etiqueta deve ter no mínimo 22×16 mm e caber dentro da folha.")
    if gap_x < 0 or gap_y < 0:
        errors.append("Os espaçamentos horizontal e vertical não podem ser negativos.")
    if any(m < 0 for m in (margin_top, margin_right, margin_bottom, margin_left)):
        errors.append("As margens da página não podem ser negativas.")
    if not (1 <= columns <= 12 and 1 <= rows <= 30):
        errors.append("Informe entre 1 e 12 colunas e entre 1 e 30 linhas por página.")
    if qr_size < 12.0:
        errors.append("O tamanho do QR Code deve ser de pelo menos 12 mm para garantir leitura confiável por celulares.")
    if not (6.0 <= font_size <= 42.0):
        errors.append("O tamanho da fonte deve estar entre 6 pt e 42 pt.")

    # Validação geométrica contra cortes na folha
    used_width = margin_left + (columns * label_w) + ((columns - 1) * gap_x) + margin_right
    used_height = margin_top + (rows * label_h) + ((rows - 1) * gap_y) + margin_bottom

    if used_width > page_w + 0.6:
        errors.append(
            f"Largura insuficiente na folha: margens + {columns} coluna(s) + espaçamentos somam "
            f"{used_width:.1f} mm, ultrapassando os {page_w:.1f} mm da página."
        )
    if used_height > page_h + 0.6:
        errors.append(
            f"Altura insuficiente na folha: margens + {rows} linha(s) + espaçamentos somam "
            f"{used_height:.1f} mm, ultrapassando os {page_h:.1f} mm da página."
        )

    # Validação de encaixe interno do QR Code dentro da etiqueta
    is_horizontal_card = label_w >= (label_h * 1.18)
    if is_horizontal_card:
        max_qr_w = round(label_w * 0.56, 1)
        max_qr_h = round(label_h - 3.0, 1)
        max_qr_allowed = min(max_qr_w, max_qr_h)
    else:
        max_qr_allowed = round(min(label_w - 4.0, label_h * 0.62), 1)

    if qr_size > max_qr_allowed + 0.5:
        errors.append(
            f"O QR Code ({qr_size:.1f} mm) excede a área útil da etiqueta ({label_w:.1f}×{label_h:.1f} mm). "
            f"Reduza o QR Code para até {max_qr_allowed:.1f} mm ou aumente a etiqueta."
        )

    if errors:
        raise SupabaseServiceError(" ".join(errors))

    return {
        "preset": preset_key,
        "page_format": page_format,
        "page_width_mm": page_w,
        "page_height_mm": page_h,
        "label_width_mm": label_w,
        "label_height_mm": label_h,
        "gap_x_mm": gap_x,
        "gap_y_mm": gap_y,
        "margin_top_mm": margin_top,
        "margin_right_mm": margin_right,
        "margin_bottom_mm": margin_bottom,
        "margin_left_mm": margin_left,
        "columns": columns,
        "rows": rows,
        "labels_per_page": columns * rows,
        "qr_size_mm": qr_size,
        "font_size_pt": font_size,
        "show_border": show_border,
        "is_horizontal_card": is_horizontal_card,
    }


def build_tag_sequence(
    prefix: str,
    start_number: int,
    end_number: int | None = None,
    quantity: int | None = None,
    padding_digits: int = 5,
    max_batch_size: int = 500,
) -> tuple[list[str], int, int, int]:
    """
    Gera a lista sequencial de identificadores (ex.: BT-00001 .. BT-00024).
    Aceita quantidade OU número final, validando consistência entre ambos.
    """
    clean_prefix = (prefix or "").strip().upper()
    if len(clean_prefix) > 25:
        raise SupabaseServiceError("O prefixo da etiqueta deve ter no máximo 25 caracteres.")
    if clean_prefix and not re.match(r"^[A-Z0-9_-]+$", clean_prefix):
        raise SupabaseServiceError("Use apenas letras, números, hífen (-) ou sublinhado (_) no prefixo.")

    if not (1 <= padding_digits <= 10):
        raise SupabaseServiceError("A quantidade de dígitos numéricos deve estar entre 1 e 10.")
    if start_number < 0:
        raise SupabaseServiceError("A numeração inicial não pode ser negativa.")

    if end_number is not None and quantity is not None:
        expected_end = start_number + quantity - 1
        if end_number != expected_end:
            # Prioriza o intervalo explícito start..end se válido, recalculando a quantidade
            if end_number >= start_number:
                quantity = (end_number - start_number) + 1
            else:
                end_number = expected_end
    elif quantity is not None:
        if quantity < 1:
            raise SupabaseServiceError("Informe uma quantidade de pelo menos 1 etiqueta.")
        end_number = start_number + quantity - 1
    elif end_number is not None:
        if end_number < start_number:
            raise SupabaseServiceError("A numeração final deve ser maior ou igual à numeração inicial.")
        quantity = (end_number - start_number) + 1
    else:
        raise SupabaseServiceError("Informe a quantidade desejada ou o intervalo numérico das etiquetas.")

    assert end_number is not None and quantity is not None
    if quantity < 1:
        raise SupabaseServiceError("A quantidade de etiquetas deve ser de no mínimo 1.")
    if quantity > max_batch_size:
        raise SupabaseServiceError(f"Gere até {max_batch_size} etiquetas por lote de impressão.")

    sequence = [f"{clean_prefix}{num:0{padding_digits}d}" for num in range(start_number, end_number + 1)]
    return sequence, start_number, end_number, quantity


def suggest_next_sequence_start(organization_id: str, prefix: str = "AN-") -> int:
    """Sugere o próximo número sequencial livre na organização para o prefixo informado."""
    clean_prefix = (prefix or "AN-").strip().upper()
    try:
        client = get_supabase_client()
        rows = (
            client.table("tag_units")
            .select("tag_number")
            .eq("organization_id", organization_id)
            .ilike("tag_number", f"{clean_prefix}%")
            .order("created_at", desc=True)
            .limit(250)
            .execute()
            .data
            or []
        )
        max_num = 0
        for row in rows:
            tag = str(row.get("tag_number") or "")
            if tag.upper().startswith(clean_prefix):
                suffix = tag[len(clean_prefix) :]
                if suffix.isdigit():
                    max_num = max(max_num, int(suffix))
        return max_num + 1
    except Exception:
        return 1


def create_tag_batch(
    organization_id: str,
    form_data: dict[str, Any],
    base_url: str,
    created_by: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Cria um conjunto (lote) de etiquetas em `tag_batches`, insere cada etiqueta individualmente
    em `tag_units` com token QR aleatório e seguro (UUIDv4) e status 'available',
    e gera os arquivos PNG de QR Code sem criar registros de animais.
    """
    prefix = (form_data.get("prefix") or "AN-").strip().upper()
    try:
        padding_digits = _parse_int(form_data.get("padding_digits"), 5)
        start_number = _parse_int(form_data.get("start_number"), 1)
        raw_end = form_data.get("end_number")
        raw_qty = form_data.get("quantity")
        end_number = _parse_int(raw_end, start_number) if str(raw_end or "").strip() != "" else None
        quantity = _parse_int(raw_qty, 24) if str(raw_qty or "").strip() != "" else None
    except ValueError as exc:
        raise SupabaseServiceError("Informe números inteiros válidos para numeração inicial, final e quantidade.") from exc

    # Se o usuário editou ambos, respeita a sincronia: quantity manda quando start+qty-1 == end, senão recalcula
    mode_priority = str(form_data.get("range_mode") or "quantity")
    if mode_priority == "range" and end_number is not None:
        quantity = None
    elif mode_priority == "quantity" and quantity is not None:
        end_number = None

    tag_numbers, start_num, end_num, qty = build_tag_sequence(
        prefix=prefix,
        start_number=start_number,
        end_number=end_number,
        quantity=quantity,
        padding_digits=padding_digits,
    )

    layout = validate_and_normalize_layout(form_data)
    custom_text = (form_data.get("custom_text") or "").strip()[:120] or None
    batch_name = (form_data.get("batch_name") or "").strip()[:160] or f"Conjunto {tag_numbers[0]} a {tag_numbers[-1]}"
    property_id = (form_data.get("property_id") or "").strip() or None
    if property_id and not is_valid_uuid(property_id):
        property_id = None

    try:
        client = get_supabase_client()

        # 1. Verifica conflitos de numeração dentro da organização em tag_units
        existing_units = (
            client.table("tag_units")
            .select("tag_number")
            .eq("organization_id", organization_id)
            .in_("tag_number", tag_numbers)
            .execute()
            .data
            or []
        )
        if existing_units:
            sample = ", ".join(sorted(r["tag_number"] for r in existing_units)[:5])
            raise SupabaseServiceError(
                f"Numeração já existente na organização ({sample}). Ajuste o número inicial para evitar duplicidade."
            )

        # 2. Verifica conflitos com brincos de animais já cadastrados
        existing_animals = (
            client.table("animals")
            .select("ear_tag")
            .in_("ear_tag", tag_numbers)
            .execute()
            .data
            or []
        )
        if existing_animals:
            sample = ", ".join(sorted(r["ear_tag"] for r in existing_animals)[:5])
            raise SupabaseServiceError(
                f"Já existem animais cadastrados com os brincos ({sample}). Escolha outra numeração."
            )

        # 3. Cria o registro de conjunto no histórico (`tag_batches`)
        batch_id = str(uuid.uuid4())
        batch_record = {
            "id": batch_id,
            "organization_id": organization_id,
            "property_id": property_id,
            "batch_name": batch_name,
            "prefix": prefix,
            "padding_digits": padding_digits,
            "start_number": start_num,
            "end_number": end_num,
            "quantity": qty,
            "custom_text": custom_text,
            "layout_config": layout,
            "created_by": created_by,
        }
        inserted_batch = client.table("tag_batches").insert(batch_record).execute().data[0]

        # 4. Cria as unidades individuais (`tag_units`) com tokens UUID exclusivos e aleatórios
        used_tokens: set[str] = set()
        unit_rows: list[dict[str, Any]] = []
        for tag_num in tag_numbers:
            token = str(uuid.uuid4())
            while token in used_tokens:
                token = str(uuid.uuid4())
            used_tokens.add(token)

            unit_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": organization_id,
                    "batch_id": batch_id,
                    "animal_id": None,
                    "tag_number": tag_num,
                    "qr_token": token,
                    "status": "available",
                    "custom_text": custom_text,
                }
            )

        inserted_units = client.table("tag_units").insert(unit_rows).execute().data or []

        # 5. Gera individualmente os arquivos PNG de QR Code apontando para a URL exclusiva com token seguro
        for unit in inserted_units:
            generate_animal_qrcode(qr_code_token=unit["qr_token"], base_url=base_url)

        return inserted_batch, inserted_units
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def list_tag_batches(organization_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Lista o histórico de conjuntos de etiquetas gerados com contagem de disponibilidade."""
    try:
        client = get_supabase_client()
        batches = (
            client.table("tag_batches")
            .select("*, properties(id, name), tag_units(id, status)")
            .eq("organization_id", organization_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
        for b in batches:
            units = b.get("tag_units") or []
            b["available_count"] = sum(1 for u in units if u.get("status") == "available")
            b["activated_count"] = sum(1 for u in units if u.get("status") == "activated")
            b["assigned_count"] = sum(1 for u in units if u.get("status") == "assigned")
            b["retired_count"] = sum(1 for u in units if u.get("status") == "retired")
        return batches
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def get_tag_batch_detail(
    batch_id: str,
    organization_id: str,
    base_url: str,
) -> dict[str, Any] | None:
    """Retorna um conjunto gerado e todas as suas etiquetas individuais prontas para visualização/impressão."""
    if not is_valid_uuid(batch_id):
        return None
    try:
        client = get_supabase_client()
        res = (
            client.table("tag_batches")
            .select("*, properties(id, name)")
            .eq("id", batch_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
            .data
        )
        if not res:
            return None

        batch = res[0]
        layout = validate_and_normalize_layout(batch.get("layout_config") or {})
        batch["layout_config"] = layout

        units = (
            client.table("tag_units")
            .select("*, animals(id, ear_tag, name, qr_code_token)")
            .eq("batch_id", batch_id)
            .order("tag_number")
            .execute()
            .data
            or []
        )
        for u in units:
            _, public_url = ensure_qrcode_exists(u["qr_token"], base_url)
            u["public_url"] = public_url
            meta = TAG_STATUS_META.get(u.get("status", "available"), TAG_STATUS_META["available"])
            u["status_label"] = meta["label"]
            u["status_badge_class"] = meta["badge_class"]

        per_page = max(1, int(layout["labels_per_page"]))
        pages = [units[i : i + per_page] for i in range(0, len(units), per_page)]
        batch["units"] = units
        batch["pages"] = pages
        batch["total_pages"] = len(pages)
        return batch
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def update_batch_layout(
    batch_id: str,
    organization_id: str,
    layout_form: dict[str, Any],
) -> dict[str, Any]:
    """Permite ajustar dimensões, folha, texto opcional ou margens para reimprimir um conjunto já gerado."""
    if not is_valid_uuid(batch_id):
        raise SupabaseServiceError("Conjunto de etiquetas inválido.")
    layout = validate_and_normalize_layout(layout_form)
    custom_text = (layout_form.get("custom_text") or "").strip()[:120] or None

    try:
        client = get_supabase_client()
        updated = (
            client.table("tag_batches")
            .update({"layout_config": layout, "custom_text": custom_text})
            .eq("id", batch_id)
            .eq("organization_id", organization_id)
            .execute()
            .data
        )
        if not updated:
            raise SupabaseServiceError("Conjunto de etiquetas não encontrado.")
        client.table("tag_units").update({"custom_text": custom_text}).eq("batch_id", batch_id).execute()
        return updated[0]
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def list_tag_units(
    organization_id: str,
    status_filter: str | None = None,
    search_term: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Lista etiquetas individuais da organização com filtros por status e numeração."""
    try:
        client = get_supabase_client()
        query = (
            client.table("tag_units")
            .select("*, tag_batches(id, batch_name), animals(id, ear_tag, name, qr_code_token)")
            .eq("organization_id", organization_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status_filter and status_filter in TAG_STATUS_META:
            query = query.eq("status", status_filter)
        if search_term and search_term.strip():
            query = query.ilike("tag_number", f"%{search_term.strip()}%")

        rows = query.execute().data or []
        for u in rows:
            meta = TAG_STATUS_META.get(u.get("status", "available"), TAG_STATUS_META["available"])
            u["status_label"] = meta["label"]
            u["status_badge_class"] = meta["badge_class"]
            u["public_url"] = build_animal_public_url(u["qr_token"], "")
        return rows
    except Exception as exc:
        raise translate_supabase_error(exc) from exc


def list_available_tag_units_safe(organization_id: str | None) -> list[dict[str, Any]]:
    """Retorna etiquetas disponíveis ou reservadas para vínculo no formulário de novo animal."""
    if not organization_id or not is_valid_uuid(organization_id):
        return []
    try:
        rows = (
            get_supabase_client()
            .table("tag_units")
            .select("id, tag_number, qr_token, status, custom_text")
            .eq("organization_id", organization_id)
            .in_("status", ["available", "assigned"])
            .order("tag_number")
            .limit(300)
            .execute()
            .data
            or []
        )
        return rows
    except TagMigrationRequiredError:
        return []
    except Exception:
        return []


def get_tag_unit_by_token_or_id_safe(identifier: str) -> dict[str, Any] | None:
    """Busca uma etiqueta pelo qr_token (ao escanear uma etiqueta ainda sem animal) ou id."""
    clean = (identifier or "").strip()
    if not clean or not is_valid_uuid(clean):
        return None
    try:
        client = get_supabase_client()
        by_token = client.table("tag_units").select("*").eq("qr_token", clean).limit(1).execute().data
        if by_token:
            unit = by_token[0]
            meta = TAG_STATUS_META.get(unit.get("status", "available"), TAG_STATUS_META["available"])
            unit["status_label"] = meta["label"]
            unit["status_badge_class"] = meta["badge_class"]
            return unit

        by_id = client.table("tag_units").select("*").eq("id", clean).limit(1).execute().data
        if by_id:
            unit = by_id[0]
            meta = TAG_STATUS_META.get(unit.get("status", "available"), TAG_STATUS_META["available"])
            unit["status_label"] = meta["label"]
            unit["status_badge_class"] = meta["badge_class"]
            return unit
        return None
    except Exception:
        return None


def get_tag_unit_by_number_safe(tag_number: str) -> dict[str, Any] | None:
    """Busca uma etiqueta pelo número visível (ex.: AN-00001) para consulta rápida."""
    clean = (tag_number or "").strip()
    if not clean:
        return None
    escaped = clean.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    try:
        rows = (
            get_supabase_client()
            .table("tag_units")
            .select("*")
            .ilike("tag_number", escaped)
            .limit(1)
            .execute()
            .data
        )
        if not rows:
            return None
        unit = rows[0]
        meta = TAG_STATUS_META.get(unit.get("status", "available"), TAG_STATUS_META["available"])
        unit["status_label"] = meta["label"]
        unit["status_badge_class"] = meta["badge_class"]
        return unit
    except Exception:
        return None


def find_linkable_tag_by_number_safe(organization_id: str | None, tag_number: str) -> dict[str, Any] | None:
    """Localiza etiqueta disponível/reservada caso o usuário digite manualmente seu número no cadastro do animal."""
    if not organization_id or not tag_number.strip():
        return None
    escaped = tag_number.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    try:
        res = (
            get_supabase_client()
            .table("tag_units")
            .select("*")
            .eq("organization_id", organization_id)
            .ilike("tag_number", escaped)
            .in_("status", ["available", "assigned"])
            .limit(1)
            .execute()
            .data
        )
        return res[0] if res else None
    except Exception:
        return None


def activate_tag_unit_for_animal(tag_unit_id: str, animal_id: str) -> None:
    """Marca a etiqueta pré-impressa como 'activated' e vincula-a ao animal recém-cadastrado."""
    if not is_valid_uuid(tag_unit_id) or not is_valid_uuid(animal_id):
        return
    try:
        now_iso = datetime.now().astimezone().isoformat()
        get_supabase_client().table("tag_units").update(
            {
                "animal_id": animal_id,
                "status": "activated",
                "activated_at": now_iso,
            }
        ).eq("id", tag_unit_id).execute()
    except Exception:
        pass


def update_tag_unit_status(
    unit_id: str,
    organization_id: str,
    new_status: str,
) -> dict[str, Any]:
    """Atualiza manualmente o estado de uma etiqueta não vinculada (available, assigned, retired)."""
    if not is_valid_uuid(unit_id):
        raise SupabaseServiceError("Etiqueta inválida.")
    if new_status not in ("available", "assigned", "retired"):
        raise SupabaseServiceError("Status permitido manualmente: disponível, reservada ou inativada.")

    try:
        client = get_supabase_client()
        found = (
            client.table("tag_units")
            .select("*")
            .eq("id", unit_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
            .data
        )
        if not found:
            raise SupabaseServiceError("Etiqueta não encontrada.")
        unit = found[0]
        if unit.get("status") == "activated" or unit.get("animal_id"):
            raise SupabaseServiceError("Etiquetas já ativadas e vinculadas a um animal não podem voltar para disponível.")

        now_iso = datetime.now().astimezone().isoformat()
        updates: dict[str, Any] = {"status": new_status}
        if new_status == "assigned":
            updates["assigned_at"] = now_iso
        elif new_status == "retired":
            updates["retired_at"] = now_iso

        res = (
            client.table("tag_units")
            .update(updates)
            .eq("id", unit_id)
            .eq("organization_id", organization_id)
            .execute()
            .data
        )
        return res[0]
    except Exception as exc:
        raise translate_supabase_error(exc) from exc
