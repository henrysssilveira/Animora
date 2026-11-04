from io import BytesIO
import re
from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from services.auth_service import (
    admin_required,
    get_current_operator,
    is_admin_authenticated,
    property_required,
)
from services.label_pdf_service import generate_labels_pdf_bytes
from services.label_service import (
    LABEL_PRESETS,
    PAGE_FORMATS,
    TAG_STATUS_META,
    create_tag_batch,
    get_tag_batch_detail,
    get_tag_unit_by_token_or_id_safe,
    list_tag_batches,
    list_tag_units,
    suggest_next_sequence_start,
    update_batch_layout,
    update_tag_unit_status,
)
from services.qrcode_service import ensure_qrcode_exists
from services.sanitary_service import get_sanitary_context
from services.supabase_service import (
    MigrationRequiredError,
    SupabaseServiceError,
    TagMigrationRequiredError,
)


labels_bp = Blueprint("labels", __name__, url_prefix="/etiquetas")


@labels_bp.route("/", methods=["GET", "POST"])
@admin_required
def generator():
    """Tela exclusiva Admin: Criação de QR Codes em Lote + Configurador de Dimensões + Pré-visualização."""
    default_preset = LABEL_PRESETS["a4_24_standard"]

    try:
        ctx = get_sanitary_context()
        next_start = suggest_next_sequence_start(ctx["organization_id"], "AN-")
        default_qty = default_preset["columns"] * default_preset["rows"]

        form_data = {
            "batch_name": "",
            "property_id": "",
            "prefix": "AN-",
            "padding_digits": "5",
            "start_number": str(next_start),
            "quantity": str(default_qty),
            "end_number": str(next_start + default_qty - 1),
            "range_mode": "quantity",
            "custom_text": "",
            "preset": "a4_24_standard",
            "page_format": default_preset["page_format"],
            "page_width_mm": str(default_preset["page_width_mm"]),
            "page_height_mm": str(default_preset["page_height_mm"]),
            "label_width_mm": str(default_preset["label_width_mm"]),
            "label_height_mm": str(default_preset["label_height_mm"]),
            "gap_x_mm": str(default_preset["gap_x_mm"]),
            "gap_y_mm": str(default_preset["gap_y_mm"]),
            "margin_top_mm": str(default_preset["margin_top_mm"]),
            "margin_right_mm": str(default_preset["margin_right_mm"]),
            "margin_bottom_mm": str(default_preset["margin_bottom_mm"]),
            "margin_left_mm": str(default_preset["margin_left_mm"]),
            "columns": str(default_preset["columns"]),
            "rows": str(default_preset["rows"]),
            "qr_size_mm": str(default_preset["qr_size_mm"]),
            "font_size_pt": str(default_preset["font_size_pt"]),
            "show_border": "true",
        }

        if request.method == "POST":
            form_data = {k: request.form.get(k, "") for k in form_data}
            if "show_border" not in request.form:
                form_data["show_border"] = "false"

            try:
                batch, units = create_tag_batch(
                    organization_id=ctx["organization_id"],
                    form_data=form_data,
                    base_url=request.url_root,
                    created_by=get_current_operator()["name"],
                )
                flash(
                    f"Conjunto '{batch['batch_name']}' gerado com sucesso! "
                    f"{len(units)} etiqueta(s) disponível(is) cadastrada(s) no Supabase com QR Codes exclusivos.",
                    "success",
                )
                return redirect(url_for("labels.batch_detail", batch_id=batch["id"]))
            except SupabaseServiceError as exc:
                flash(str(exc), "danger")

        recent_batches = []
        tag_migration_error = None
        try:
            recent_batches = list_tag_batches(ctx["organization_id"], limit=5)
        except TagMigrationRequiredError as exc:
            tag_migration_error = str(exc)

        return render_template(
            "labels/generator.html",
            ctx=ctx,
            form_data=form_data,
            presets=LABEL_PRESETS,
            page_formats=PAGE_FORMATS,
            recent_batches=recent_batches,
            tag_migration_error=tag_migration_error,
        )
    except MigrationRequiredError as exc:
        return render_template(
            "labels/generator.html",
            ctx={"properties": []},
            form_data={},
            presets=LABEL_PRESETS,
            page_formats=PAGE_FORMATS,
            recent_batches=[],
            tag_migration_error=str(exc),
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("dashboard"))


@labels_bp.route("/historico")
@property_required
def history():
    """
    Estoque e Atribuição de Etiquetas (`tag_units`) disponível para Property e Admin.
    O histórico de lotes para reimpressão e geração de novos QR Codes fica visível para Admin.
    """
    status_filter = request.args.get("status", "").strip()
    search_q = request.args.get("q", "").strip()
    is_admin = is_admin_authenticated()

    try:
        ctx = get_sanitary_context()
        batches = list_tag_batches(ctx["organization_id"], limit=50) if is_admin else []
        units = list_tag_units(
            organization_id=ctx["organization_id"],
            status_filter=status_filter or None,
            search_term=search_q or None,
            limit=200,
        )
        return render_template(
            "labels/history.html",
            ctx=ctx,
            batches=batches,
            units=units,
            status_meta=TAG_STATUS_META,
            status_filter=status_filter,
            search_q=search_q,
        )
    except (TagMigrationRequiredError, MigrationRequiredError) as exc:
        return render_template(
            "labels/history.html",
            ctx={"properties": []},
            batches=[],
            units=[],
            status_meta=TAG_STATUS_META,
            status_filter=status_filter,
            search_q=search_q,
            tag_migration_error=str(exc),
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("dashboard"))


@labels_bp.route("/lotes/<string:batch_id>")
@admin_required
def batch_detail(batch_id: str):
    """Pré-visualização real das folhas geradas, ajuste de dimensões para reimpressão e exportação PDF (Admin)."""
    try:
        ctx = get_sanitary_context()
        batch = get_tag_batch_detail(batch_id, ctx["organization_id"], request.url_root)
        if not batch:
            flash("Conjunto de etiquetas não encontrado.", "warning")
            return redirect(url_for("labels.history"))

        return render_template(
            "labels/batch_detail.html",
            ctx=ctx,
            batch=batch,
            layout=batch["layout_config"],
            presets=LABEL_PRESETS,
            page_formats=PAGE_FORMATS,
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("labels.history"))


@labels_bp.route("/lotes/<string:batch_id>/layout", methods=["POST"])
@admin_required
def save_layout(batch_id: str):
    """Atualiza dimensões em milímetros ou texto personalizado de um lote já gerado (Admin)."""
    try:
        ctx = get_sanitary_context()
        payload = dict(request.form)
        if "show_border" not in request.form:
            payload["show_border"] = "false"
        update_batch_layout(batch_id, ctx["organization_id"], payload)
        flash("Configurações de layout da página/etiqueta atualizadas para impressão!", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("labels.batch_detail", batch_id=batch_id))


@labels_bp.route("/lotes/<string:batch_id>/pdf")
@admin_required
def export_pdf(batch_id: str):
    """Gera e exporta o arquivo PDF vetorial em escala real (mm) pronto para impressão (Admin)."""
    try:
        ctx = get_sanitary_context()
        batch = get_tag_batch_detail(batch_id, ctx["organization_id"], request.url_root)
        if not batch:
            flash("Conjunto de etiquetas não encontrado.", "warning")
            return redirect(url_for("labels.history"))

        pdf_bytes = generate_labels_pdf_bytes(
            units=batch["units"],
            layout=batch["layout_config"],
            base_url=request.url_root,
            document_title=batch["batch_name"],
        )
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", batch["batch_name"]).strip("_") or "etiquetas"
        as_download = request.args.get("inline") != "1"

        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=as_download,
            download_name=f"animora_{safe_name}.pdf",
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("labels.batch_detail", batch_id=batch_id))


@labels_bp.route("/lotes/<string:batch_id>/imprimir")
@admin_required
def print_sheet(batch_id: str):
    """Versão limpa em HTML/CSS (@page e @media print em milímetros) para impressão direta (Admin)."""
    try:
        ctx = get_sanitary_context()
        batch = get_tag_batch_detail(batch_id, ctx["organization_id"], request.url_root)
        if not batch:
            flash("Conjunto de etiquetas não encontrado.", "warning")
            return redirect(url_for("labels.history"))

        auto_print = request.args.get("autoprint", "1") == "1"
        return render_template(
            "labels/print_sheet.html",
            batch=batch,
            layout=batch["layout_config"],
            auto_print=auto_print,
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("labels.batch_detail", batch_id=batch_id))


@labels_bp.route("/unidades/<string:unit_id>/qrcode/download")
@admin_required
def download_unit_qr(unit_id: str):
    """Baixa o QR Code individual em PNG de uma etiqueta específica (Admin)."""
    unit = get_tag_unit_by_token_or_id_safe(unit_id)
    if not unit:
        flash("Etiqueta não encontrada.", "warning")
        return redirect(url_for("labels.history"))

    file_path, _ = ensure_qrcode_exists(unit["qr_token"], request.url_root)
    safe_tag = re.sub(r"[^A-Za-z0-9_-]+", "_", str(unit.get("tag_number", "etiqueta"))).strip("_")
    return send_file(
        BytesIO(file_path.read_bytes()),
        mimetype="image/png",
        as_attachment=True,
        download_name=f"animora_etiqueta_{safe_tag}.png",
    )


@labels_bp.route("/unidades/<string:unit_id>/status", methods=["POST"])
@property_required
def change_unit_status(unit_id: str):
    """Altera o status operacional de uma etiqueta ainda não vinculada (available, assigned, retired)."""
    try:
        ctx = get_sanitary_context()
        new_status = request.form.get("status", "").strip()
        if new_status == "retired" and not is_admin_authenticated():
            flash("Apenas o perfil Admin pode baixar/inativar permanentemente etiquetas QR.", "warning")
            return redirect(url_for("labels.history", status=request.form.get("current_filter", "")))

        updated = update_tag_unit_status(unit_id, ctx["organization_id"], new_status)
        st_label = TAG_STATUS_META.get(updated["status"], {}).get("label", updated["status"])
        flash(f"Etiqueta {updated['tag_number']} marcada como '{st_label}'.", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("labels.history", status=request.form.get("current_filter", "")))
