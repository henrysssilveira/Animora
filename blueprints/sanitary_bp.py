from datetime import date, datetime
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from services.auth_service import (
    admin_required,
    get_current_operator,
    is_admin_authenticated,
    operator_required,
)
from services.farm_service import (
    create_farm_access_profile,
    delete_entire_farm,
    delete_farm_access_profile,
    delete_farm_operational_data,
    delete_single_campaign,
    delete_single_lot,
    delete_single_vaccine,
    list_all_farm_access_profiles,
    list_farms_with_stats,
    toggle_farm_access_profile,
)
from services.classification_service import (
    AGE_CATEGORY_LABELS,
    enrich_animals_list,
    filter_animals_by_age_category,
    filter_animals_by_species,
)
from services.management_service import (
    create_management_record,
    list_management_alerts_safe,
    save_feeding_plan,
)
from services.species_service import normalize_species
from services.sanitary_service import (
    HEALTH_RECORD_TYPE_LABELS,
    add_protocol_rule,
    confirm_vaccination_application,
    create_campaign_with_schedules,
    create_health_record,
    create_lot,
    create_property,
    get_campaign_cartela_detail,
    get_monthly_calendar_data,
    get_protocol_detail,
    get_sanitary_context,
    get_sanitary_dashboard_data,
    list_campaign_cartelas,
    list_protocols,
    list_vaccines,
    save_protocol,
    save_vaccine,
    toggle_protocol_rule_status,
    toggle_vaccine_status,
    update_schedule_status_with_audit,
)
from services.schedule_engine import (
    ONBOARDING_MODE_LABELS,
    SCHEDULE_STATUS_META,
    generate_schedules_for_animal,
    generate_schedules_for_protocol,
    sync_property_schedules,
)
from services.supabase_service import (
    MigrationRequiredError,
    SupabaseServiceError,
    get_animal_by_token_or_id,
    is_valid_uuid,
    list_animals,
    update_animal_sanitary_profile,
)

sanitary_bp = Blueprint("sanitary", __name__, url_prefix="/sanitario")


def _safe_redirect_back(default_endpoint: str = "sanitary.dashboard", **kwargs) -> str:
    next_url = (request.form.get("next") or request.args.get("next") or "").strip()
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return url_for(default_endpoint, **kwargs)


# ----------------------------------------------------------------------------
# 1. Visão Geral (Dashboard Sanitário)
# ----------------------------------------------------------------------------
@sanitary_bp.route("/")
@operator_required
def dashboard():
    property_filter = request.args.get("property_id", "").strip()
    species_filter = request.args.get("species", "todas").strip().lower()
    try:
        ctx = get_sanitary_context()
        kpis = get_sanitary_dashboard_data(
            organization_id=ctx["organization_id"],
            property_id=property_filter or None,
            species=species_filter if species_filter != "todas" else None,
            age_brackets=ctx["age_brackets"],
        )
        active_vaccines = list_vaccines(
            ctx["organization_id"],
            only_active=True,
            species=species_filter if species_filter != "todas" else None,
        )
        return render_template(
            "sanitary/dashboard.html",
            ctx=ctx,
            kpis=kpis,
            active_vaccines=active_vaccines,
            selected_property_id=property_filter,
            selected_species=species_filter,
            now_dt_local=datetime.now().strftime("%Y-%m-%dT%H:%M"),
            today_iso=date.today().isoformat(),
        )
    except MigrationRequiredError as exc:
        return render_template(
            "sanitary/dashboard.html",
            ctx={"properties": [], "lots": [], "migration_ready": False},
            kpis=None,
            active_vaccines=[],
            selected_property_id="",
            selected_species=species_filter,
            migration_error=str(exc),
            now_dt_local=datetime.now().strftime("%Y-%m-%dT%H:%M"),
            today_iso=date.today().isoformat(),
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return render_template(
            "sanitary/dashboard.html",
            ctx={"properties": [], "lots": [], "migration_ready": False},
            kpis=None,
            active_vaccines=[],
            selected_property_id="",
            selected_species=species_filter,
            db_error=str(exc),
            now_dt_local=datetime.now().strftime("%Y-%m-%dT%H:%M"),
            today_iso=date.today().isoformat(),
        )


@sanitary_bp.route("/sincronizar", methods=["POST"])
@operator_required
def sync_schedules():
    property_id = request.form.get("property_id", "").strip() or None
    try:
        ctx = get_sanitary_context()
        stats = sync_property_schedules(
            property_id=property_id,
            organization_id=ctx["organization_id"],
        )
        flash(
            f"Sincronização concluída: {stats['animals_evaluated']} animal(is) verificado(s) e "
            f"{stats['created_schedules']} novo(s) agendamento(s) gerado(s).",
            "success",
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(_safe_redirect_back("sanitary.dashboard"))


# ----------------------------------------------------------------------------
# 2. Calendário Sanitário Mensal
# ----------------------------------------------------------------------------
@sanitary_bp.route("/calendario")
@operator_required
def calendar_view():
    today = date.today()
    try:
        year = max(2020, min(2040, int(request.args.get("year", today.year))))
        month = max(1, min(12, int(request.args.get("month", today.month))))
    except ValueError:
        year, month = today.year, today.month

    filters = {
        "property_id": request.args.get("property_id", "").strip(),
        "lot_id": request.args.get("lot_id", "").strip(),
        "vaccine_id": request.args.get("vaccine_id", "").strip(),
        "species": request.args.get("species", "todas").strip().lower(),
        "age_category": request.args.get("age_category", "todas").strip(),
        "status": request.args.get("status", "todos").strip(),
    }

    try:
        ctx = get_sanitary_context()
        vaccines = list_vaccines(ctx["organization_id"])
        cal_data = get_monthly_calendar_data(
            organization_id=ctx["organization_id"],
            year=year,
            month=month,
            filters=filters,
            age_brackets=ctx["age_brackets"],
        )
        return render_template(
            "sanitary/calendar.html",
            ctx=ctx,
            vaccines=vaccines,
            active_vaccines=[v for v in vaccines if v.get("is_active")],
            cal=cal_data,
            filters=filters,
            age_categories=AGE_CATEGORY_LABELS,
            status_meta=SCHEDULE_STATUS_META,
            now_dt_local=datetime.now().strftime("%Y-%m-%dT%H:%M"),
            today_iso=today.isoformat(),
        )
    except MigrationRequiredError as exc:
        return render_template(
            "sanitary/calendar.html",
            ctx={"properties": [], "lots": []},
            vaccines=[],
            active_vaccines=[],
            cal=None,
            filters=filters,
            age_categories=AGE_CATEGORY_LABELS,
            status_meta=SCHEDULE_STATUS_META,
            migration_error=str(exc),
            now_dt_local=datetime.now().strftime("%Y-%m-%dT%H:%M"),
            today_iso=today.isoformat(),
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("sanitary.dashboard"))


# ----------------------------------------------------------------------------
# 3. Cartelas de Vacinação e Campanhas
# ----------------------------------------------------------------------------
@sanitary_bp.route("/cartelas")
@operator_required
def campaigns_list():
    property_filter = request.args.get("property_id", "").strip()
    try:
        ctx = get_sanitary_context()
        campaigns = list_campaign_cartelas(
            organization_id=ctx["organization_id"],
            property_id=property_filter or None,
        )
        return render_template(
            "sanitary/campaigns.html",
            ctx=ctx,
            campaigns=campaigns,
            selected_property_id=property_filter,
        )
    except MigrationRequiredError as exc:
        return render_template(
            "sanitary/campaigns.html",
            ctx={"properties": [], "lots": []},
            campaigns=[],
            selected_property_id="",
            migration_error=str(exc),
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("sanitary.dashboard"))


@sanitary_bp.route("/cartelas/nova", methods=["GET", "POST"])
@operator_required
def campaign_new():
    try:
        ctx = get_sanitary_context()
        active_vaccines = list_vaccines(ctx["organization_id"], only_active=True)

        form_data = {
            "name": "",
            "vaccine_id": "",
            "scheduled_date": date.today().isoformat(),
            "property_id": ctx["properties"][0]["id"] if ctx["properties"] else "",
            "lot_id": "",
            "selection_mode": "lote",
            "description": "",
            "notes": "",
        }

        if request.method == "POST":
            form_data = {k: request.form.get(k, "") for k in form_data}
            selected_animals = request.form.getlist("animal_ids")
            try:
                created_camp, count_sched = create_campaign_with_schedules(
                    organization_id=ctx["organization_id"],
                    payload=form_data,
                    selected_animal_ids=selected_animals,
                )
                flash(
                    f"Campanha '{created_camp['name']}' criada com sucesso! "
                    f"Foram gerados {count_sched} agendamento(s) individual(is).",
                    "success",
                )
                return redirect(url_for("sanitary.campaign_detail", campaign_id=created_camp["id"]))
            except SupabaseServiceError as exc:
                flash(str(exc), "danger")

        return render_template(
            "sanitary/campaign_form.html",
            ctx=ctx,
            active_vaccines=active_vaccines,
            form_data=form_data,
        )
    except MigrationRequiredError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("sanitary.dashboard"))
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("sanitary.campaigns_list"))


@sanitary_bp.route("/cartelas/<string:campaign_id>")
@operator_required
def campaign_detail(campaign_id: str):
    try:
        ctx = get_sanitary_context()
        campaign = get_campaign_cartela_detail(
            campaign_id=campaign_id,
            organization_id=ctx["organization_id"],
            age_brackets=ctx["age_brackets"],
        )
        if not campaign:
            flash("Cartela de campanha não encontrada.", "warning")
            return redirect(url_for("sanitary.campaigns_list"))

        active_vaccines = list_vaccines(ctx["organization_id"], only_active=True)
        return render_template(
            "sanitary/campaign_detail.html",
            ctx=ctx,
            campaign=campaign,
            active_vaccines=active_vaccines,
            now_dt_local=datetime.now().strftime("%Y-%m-%dT%H:%M"),
            today_iso=date.today().isoformat(),
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("sanitary.campaigns_list"))


# ----------------------------------------------------------------------------
# 4. Catálogo e Gestão de Vacinas
# ----------------------------------------------------------------------------
@sanitary_bp.route("/vacinas", methods=["GET", "POST"])
@operator_required
def vaccines_view():
    species_filter = request.args.get("species", "todas").strip().lower()
    type_filter = request.args.get("item_type", "todos").strip().lower()
    try:
        ctx = get_sanitary_context()
        edit_id = request.args.get("editar", "").strip()

        if request.method == "POST":
            target_id = request.form.get("vaccine_id", "").strip() or None
            try:
                saved = save_vaccine(
                    organization_id=ctx["organization_id"],
                    payload=request.form,
                    vaccine_id=target_id,
                )
                action_word = "atualizado" if target_id else "cadastrado"
                flash(f"{saved['item_type_label']} '{saved['commercial_name']}' {action_word} com sucesso!", "success")
                return redirect(url_for("sanitary.vaccines_view"))
            except SupabaseServiceError as exc:
                flash(str(exc), "danger")

        all_vaccines = list_vaccines(ctx["organization_id"])
        editing_vaccine = next((v for v in all_vaccines if v["id"] == edit_id), None) if edit_id else None
        vaccines = list_vaccines(
            ctx["organization_id"],
            species=species_filter if species_filter != "todas" else None,
            item_type=type_filter if type_filter != "todos" else None,
        )

        return render_template(
            "sanitary/vaccines.html",
            ctx=ctx,
            vaccines=vaccines,
            editing_vaccine=editing_vaccine,
            selected_species=species_filter,
            selected_item_type=type_filter,
        )
    except MigrationRequiredError as exc:
        return render_template(
            "sanitary/vaccines.html",
            ctx={"properties": [], "lots": []},
            vaccines=[],
            editing_vaccine=None,
            selected_species=species_filter,
            selected_item_type=type_filter,
            migration_error=str(exc),
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("sanitary.dashboard"))


@sanitary_bp.route("/vacinas/<string:vaccine_id>/status", methods=["POST"])
@operator_required
def vaccine_toggle(vaccine_id: str):
    try:
        ctx = get_sanitary_context()
        updated = toggle_vaccine_status(vaccine_id, ctx["organization_id"])
        st = "ativada" if updated.get("is_active") else "inativada"
        flash(f"Vacina '{updated['commercial_name']}' {st}.", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("sanitary.vaccines_view"))


# ----------------------------------------------------------------------------
# 5. Protocolos Sanitários e Regras
# ----------------------------------------------------------------------------
@sanitary_bp.route("/protocolos", methods=["GET", "POST"])
@operator_required
def protocols_view():
    property_filter = request.args.get("property_id", "").strip()
    species_filter = request.args.get("species", "todas").strip().lower()
    try:
        ctx = get_sanitary_context()
        if request.method == "POST":
            try:
                saved, sync_stats = save_protocol(
                    organization_id=ctx["organization_id"],
                    payload=request.form,
                )
                flash(
                    f"Protocolo '{saved['name']}' salvo com sucesso! "
                    "Agora configure as regras preventivas (vacinas, vermífugos ou exames).",
                    "success",
                )
                return redirect(url_for("sanitary.protocol_detail", protocol_id=saved["id"]))
            except SupabaseServiceError as exc:
                flash(str(exc), "danger")

        protocols = list_protocols(
            ctx["organization_id"],
            property_id=property_filter or None,
            species=species_filter if species_filter != "todas" else None,
        )
        return render_template(
            "sanitary/protocols.html",
            ctx=ctx,
            protocols=protocols,
            selected_property_id=property_filter,
            selected_species=species_filter,
            age_categories=AGE_CATEGORY_LABELS,
            operator=get_current_operator(),
        )
    except MigrationRequiredError as exc:
        return render_template(
            "sanitary/protocols.html",
            ctx={"properties": [], "lots": []},
            protocols=[],
            selected_property_id="",
            age_categories=AGE_CATEGORY_LABELS,
            operator=get_current_operator(),
            migration_error=str(exc),
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("sanitary.dashboard"))


@sanitary_bp.route("/protocolos/<string:protocol_id>", methods=["GET", "POST"])
@operator_required
def protocol_detail(protocol_id: str):
    try:
        ctx = get_sanitary_context()
        if request.method == "POST":
            form_action = request.form.get("form_action", "add_rule")
            try:
                if form_action == "update_protocol":
                    saved, stats = save_protocol(
                        organization_id=ctx["organization_id"],
                        payload=request.form,
                        protocol_id=protocol_id,
                    )
                    msg = f"Protocolo '{saved['name']}' atualizado!"
                    if stats["created_schedules"] > 0:
                        msg += f" {stats['created_schedules']} novo(s) agendamento(s) gerado(s)."
                    flash(msg, "success")
                elif form_action == "sync_protocol":
                    stats = generate_schedules_for_protocol(protocol_id)
                    flash(
                        f"Pendências processadas para {stats['animals_evaluated']} animal(is): "
                        f"{stats['created_schedules']} novo(s) agendamento(s) criado(s).",
                        "success",
                    )
                else:
                    _, stats = add_protocol_rule(
                        organization_id=ctx["organization_id"],
                        protocol_id=protocol_id,
                        payload=request.form,
                    )
                    msg = "Regra sanitária adicionada ao protocolo!"
                    if stats["created_schedules"] > 0:
                        msg += f" {stats['created_schedules']} agendamento(s) gerado(s) para o rebanho compatível."
                    flash(msg, "success")
                return redirect(url_for("sanitary.protocol_detail", protocol_id=protocol_id))
            except SupabaseServiceError as exc:
                flash(str(exc), "danger")

        protocol = get_protocol_detail(protocol_id, ctx["organization_id"])
        if not protocol:
            flash("Protocolo sanitário não encontrado.", "warning")
            return redirect(url_for("sanitary.protocols_view"))

        vaccines = list_vaccines(ctx["organization_id"], only_active=True)
        return render_template(
            "sanitary/protocol_detail.html",
            ctx=ctx,
            protocol=protocol,
            vaccines=vaccines,
            age_categories=AGE_CATEGORY_LABELS,
            operator=get_current_operator(),
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("sanitary.protocols_view"))


@sanitary_bp.route("/regras/<string:rule_id>/status", methods=["POST"])
@operator_required
def rule_toggle(rule_id: str):
    protocol_id = request.form.get("protocol_id", "")
    try:
        ctx = get_sanitary_context()
        updated = toggle_protocol_rule_status(rule_id, ctx["organization_id"])
        st = "ativada" if updated.get("is_active") else "inativada"
        flash(f"Regra sanitária {st}. Registros históricos anteriores foram preservados.", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    if is_valid_uuid(protocol_id):
        return redirect(url_for("sanitary.protocol_detail", protocol_id=protocol_id))
    return redirect(url_for("sanitary.protocols_view"))


# ----------------------------------------------------------------------------
# 6. Carteira Sanitária dos Animais (Listagem & Consulta Rápida)
# ----------------------------------------------------------------------------
@sanitary_bp.route("/carteiras")
@operator_required
def health_cards_index():
    property_filter = request.args.get("property_id", "").strip()
    lot_filter = request.args.get("lot_id", "").strip()
    species_filter = request.args.get("species", "todas").strip().lower()
    age_filter = request.args.get("age_category", "todas").strip()
    onboarding_filter = request.args.get("onboarding_mode", "todos").strip()

    try:
        ctx = get_sanitary_context()
        raw_animals = list_animals(
            organization_id=ctx["organization_id"],
            property_id=property_filter or None,
            lot_id=lot_filter or None,
        )
        animals = enrich_animals_list(raw_animals, brackets=ctx["age_brackets"])
        animals = filter_animals_by_species(animals, species_filter)
        animals = filter_animals_by_age_category(animals, age_filter)

        if onboarding_filter and onboarding_filter != "todos":
            animals = [
                a for a in animals
                if (a.get("sanitary_onboarding_mode") or "acompanhamento_nascimento") == onboarding_filter
            ]

        prop_map = {p["id"]: p["name"] for p in ctx["properties"]}
        lot_map = {l["id"]: l["name"] for l in ctx["lots"]}
        for a in animals:
            a["property_name"] = prop_map.get(a.get("property_id"), "—")
            a["lot_name"] = lot_map.get(a.get("lot_id"), "Sem lote")
            a["onboarding_label"] = ONBOARDING_MODE_LABELS.get(
                a.get("sanitary_onboarding_mode") or "acompanhamento_nascimento",
                "Acompanhamento",
            )

        return render_template(
            "sanitary/health_cards_index.html",
            ctx=ctx,
            animals=animals,
            age_categories=AGE_CATEGORY_LABELS,
            onboarding_modes=ONBOARDING_MODE_LABELS,
            filters={
                "property_id": property_filter,
                "lot_id": lot_filter,
                "species": species_filter,
                "age_category": age_filter,
                "onboarding_mode": onboarding_filter,
            },
        )
    except MigrationRequiredError as exc:
        return render_template(
            "sanitary/health_cards_index.html",
            ctx={"properties": [], "lots": []},
            animals=[],
            age_categories=AGE_CATEGORY_LABELS,
            onboarding_modes=ONBOARDING_MODE_LABELS,
            filters={},
            migration_error=str(exc),
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("sanitary.dashboard"))


# ----------------------------------------------------------------------------
# 6B. Rotinas Zootécnicas & Manejo por Espécie (Casqueamento, Tosquia, Pesagem...)
# ----------------------------------------------------------------------------
@sanitary_bp.route("/manejo")
@operator_required
def management_routines_view():
    property_filter = request.args.get("property_id", "").strip()
    species_filter = request.args.get("species", "todas").strip().lower()
    try:
        ctx = get_sanitary_context()
        raw_animals = list_animals(
            organization_id=ctx["organization_id"],
            property_id=property_filter or None,
            only_active=True,
        )
        animals = enrich_animals_list(raw_animals, brackets=ctx["age_brackets"])
        filtered_animals = filter_animals_by_species(animals, species_filter)

        mgmt_data = list_management_alerts_safe(
            organization_id=ctx["organization_id"],
            property_id=property_filter or None,
            species=species_filter if species_filter != "todas" else None,
            age_brackets=ctx["age_brackets"],
        )

        return render_template(
            "sanitary/management.html",
            ctx=ctx,
            animals=filtered_animals,
            mgmt=mgmt_data,
            selected_property_id=property_filter,
            selected_species=species_filter,
            today_iso=date.today().isoformat(),
        )
    except MigrationRequiredError as exc:
        return render_template(
            "sanitary/management.html",
            ctx={"properties": [], "lots": []},
            animals=[],
            mgmt={"migration_004_ready": False, "overdue_alerts": [], "upcoming_alerts": [], "recent_records": []},
            selected_property_id="",
            selected_species=species_filter,
            migration_error=str(exc),
            today_iso=date.today().isoformat(),
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("sanitary.dashboard"))


@sanitary_bp.route("/manejo/registrar", methods=["POST"])
@operator_required
def add_management_record():
    try:
        ctx = get_sanitary_context()
        payload = dict(request.form)
        if not payload.get("specialist_or_responsible"):
            payload["specialist_or_responsible"] = get_current_operator()["name"]

        saved = create_management_record(ctx["organization_id"], payload)
        flash(f"Manejo '{saved['routine_short_label']}' registrado com sucesso!", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(_safe_redirect_back("sanitary.management_routines_view"))


@sanitary_bp.route("/cocho/salvar", methods=["POST"])
@operator_required
def save_animal_feeding_plan():
    try:
        ctx = get_sanitary_context()
        operator_name = get_current_operator()["name"]
        save_feeding_plan(ctx["organization_id"], request.form, operator_name)
        flash("Plano de Cocho / Arraçoamento salvo com sucesso!", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(_safe_redirect_back("animals_list"))


# ----------------------------------------------------------------------------
# 7. Propriedades e Lotes Auxiliares & Gestão de Acessos por Fazenda (Admin)
# ----------------------------------------------------------------------------
@sanitary_bp.route("/propriedades", methods=["GET", "POST"])
@operator_required
def properties_lots_view():
    try:
        ctx = get_sanitary_context()
        is_admin = is_admin_authenticated()

        if request.method == "POST":
            entity = request.form.get("entity_type", "property")
            try:
                if entity == "lot":
                    created = create_lot(ctx["organization_id"], request.form)
                    flash(f"Lote '{created['name']}' cadastrado com sucesso!", "success")
                else:
                    if not is_admin:
                        flash("Apenas o perfil de Administrador tem autorização para cadastrar novas fazendas.", "danger")
                        return redirect(url_for("sanitary.properties_lots_view"))
                    created = create_property(ctx["organization_id"], request.form)
                    flash(f"Fazenda '{created['name']}' cadastrada com sucesso!", "success")
                return redirect(url_for("sanitary.properties_lots_view"))
            except SupabaseServiceError as exc:
                flash(str(exc), "danger")

        farms_with_stats = []
        access_profiles = []
        if is_admin:
            try:
                farms_with_stats = list_farms_with_stats(ctx["organization_id"])
                access_profiles = list_all_farm_access_profiles(ctx["organization_id"])
            except Exception:
                farms_with_stats = []
                access_profiles = []

        return render_template(
            "sanitary/properties_lots.html",
            ctx=ctx,
            farms=farms_with_stats,
            access_profiles=access_profiles,
            is_admin=is_admin,
        )
    except MigrationRequiredError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("sanitary.dashboard"))
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("sanitary.dashboard"))


@sanitary_bp.route("/propriedades/<string:property_id>/acessos", methods=["POST"])
@admin_required
def create_property_access(property_id: str):
    """Cria um perfil de acesso exclusivo vinculado a uma fazenda (Admin Only)."""
    try:
        ctx = get_sanitary_context()
        profile = create_farm_access_profile(ctx["organization_id"], property_id, request.form)
        flash(
            f"Acesso '{profile['name']}' ({profile['role']}) criado com sucesso para esta fazenda! Chave/PIN: {profile['access_pin']}",
            "success",
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("sanitary.properties_lots_view"))


@sanitary_bp.route("/acessos/<string:profile_id>/status", methods=["POST"])
@admin_required
def toggle_access_status(profile_id: str):
    """Ativa ou desativa um perfil de acesso vinculado (Admin Only)."""
    try:
        updated = toggle_farm_access_profile(profile_id)
        st = "ativado" if updated.get("is_active") else "desativado"
        flash(f"Perfil de acesso {st} com sucesso!", "info")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("sanitary.properties_lots_view"))


@sanitary_bp.route("/acessos/<string:profile_id>/excluir", methods=["POST"])
@admin_required
def delete_access(profile_id: str):
    """Exclui permanentemente um perfil de acesso vinculado (Admin Only)."""
    try:
        delete_farm_access_profile(profile_id)
        flash("Perfil de acesso excluído com sucesso!", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("sanitary.properties_lots_view"))


@sanitary_bp.route("/propriedades/<string:property_id>/limpar-dados", methods=["POST"])
@admin_required
def wipe_property_data(property_id: str):
    """
    Exclui todos os dados operacionais da fazenda (animais, lotes, agendamentos, manejos),
    invalidando permanentemente todos os QR codes correspondentes (Admin Only).
    """
    try:
        ctx = get_sanitary_context()
        res = delete_farm_operational_data(property_id, ctx["organization_id"])
        flash(
            f"Dados da fazenda limpos com sucesso! {res['deleted_animals']} animais excluídos, "
            f"{res['invalidated_qr_tokens']} QR Codes invalidados e {res['deleted_lots']} lotes removidos.",
            "warning",
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("sanitary.properties_lots_view"))


@sanitary_bp.route("/propriedades/<string:property_id>/excluir", methods=["POST"])
@admin_required
def delete_property_route(property_id: str):
    """
    Exclui a fazenda inteira, limpando dados e invalidando todos os QR codes vinculados (Admin Only).
    """
    try:
        ctx = get_sanitary_context()
        res = delete_entire_farm(property_id, ctx["organization_id"])
        flash(
            f"Fazenda excluída com sucesso! {res['deleted_animals']} animais excluídos e "
            f"{res['invalidated_qr_tokens']} QR Codes foram invalidados permanentemente.",
            "warning",
        )
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("sanitary.properties_lots_view"))


@sanitary_bp.route("/lotes/<string:lot_id>/excluir", methods=["POST"])
@operator_required
def delete_lot_route(lot_id: str):
    """Exclusão unitária de lote (desvincula animais)."""
    try:
        delete_single_lot(lot_id)
        flash("Lote excluído com sucesso!", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("sanitary.properties_lots_view"))


@sanitary_bp.route("/cartelas/<string:campaign_id>/excluir", methods=["POST"])
@operator_required
def delete_campaign_route(campaign_id: str):
    """Exclusão unitária de cartela de campanha sanitária."""
    try:
        delete_single_campaign(campaign_id)
        flash("Cartela de campanha excluída com sucesso!", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("sanitary.campaigns_list"))


@sanitary_bp.route("/vacinas/<string:vaccine_id>/excluir", methods=["POST"])
@operator_required
def delete_vaccine_route(vaccine_id: str):
    """Exclusão unitária de item do catálogo preventivo."""
    try:
        delete_single_vaccine(vaccine_id)
        flash("Item preventivo excluído com sucesso!", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("sanitary.vaccines_list"))


# ----------------------------------------------------------------------------
# 8. Ações de Escrita: Confirmar Aplicação, Alterar Status, Ocorrências e Perfil
# ----------------------------------------------------------------------------
@sanitary_bp.route("/aplicacoes/confirmar", methods=["POST"])
@operator_required
def confirm_application():
    try:
        ctx = get_sanitary_context()
        payload = dict(request.form)
        if not payload.get("applied_by"):
            payload["applied_by"] = get_current_operator()["name"]

        confirm_vaccination_application(
            organization_id=ctx["organization_id"],
            payload=payload,
        )
        flash("Registro preventivo (vacina, vermífugo ou exame) confirmado permanentemente na Carteira Sanitária!", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(_safe_redirect_back("sanitary.dashboard"))


@sanitary_bp.route("/agendamentos/<string:schedule_id>/status", methods=["POST"])
@operator_required
def update_schedule_status(schedule_id: str):
    try:
        ctx = get_sanitary_context()
        new_status = request.form.get("status", "")
        reason = request.form.get("reason", "")
        operator_name = get_current_operator()["name"]

        update_schedule_status_with_audit(
            organization_id=ctx["organization_id"],
            schedule_id=schedule_id,
            new_status=new_status,
            reason=reason,
            operator_name=operator_name,
        )
        flash("Situação do agendamento atualizada e registrada no histórico!", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(_safe_redirect_back("sanitary.dashboard"))


@sanitary_bp.route("/ocorrencias/registrar", methods=["POST"])
@operator_required
def add_health_record():
    try:
        ctx = get_sanitary_context()
        payload = dict(request.form)
        if not payload.get("veterinarian_or_responsible"):
            payload["veterinarian_or_responsible"] = get_current_operator()["name"]

        saved = create_health_record(ctx["organization_id"], payload)
        label = HEALTH_RECORD_TYPE_LABELS.get(saved["record_type"], {}).get("label", "Registro")
        flash(f"{label} adicionado com sucesso à Carteira Sanitária!", "success")
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
    return redirect(_safe_redirect_back("sanitary.dashboard"))


@sanitary_bp.route("/animais/<string:animal_id>/perfil-sanitario", methods=["POST"])
@operator_required
def update_animal_profile(animal_id: str):
    try:
        ctx = get_sanitary_context()
        animal = get_animal_by_token_or_id(animal_id)
        if not animal:
            flash("Animal não encontrado.", "danger")
            return redirect(url_for("animals_list"))

        property_id = request.form.get("property_id", "").strip() or animal.get("property_id")
        lot_id = request.form.get("lot_id", "").strip() or None
        onboarding_mode = request.form.get("sanitary_onboarding_mode", "").strip()
        inclusion_date = request.form.get("inclusion_date", "").strip() or date.today().isoformat()
        initial_notes = request.form.get("initial_sanitary_notes", "").strip() or None

        if onboarding_mode not in ONBOARDING_MODE_LABELS:
            onboarding_mode = animal.get("sanitary_onboarding_mode") or "acompanhamento_nascimento"

        profile_updates: dict = {
            "property_id": property_id,
            "lot_id": lot_id,
            "sanitary_onboarding_mode": onboarding_mode,
            "inclusion_date": inclusion_date,
            "initial_sanitary_notes": initial_notes,
        }
        if "species" in request.form:
            profile_updates["species"] = normalize_species(request.form.get("species"))
        if "coat_color" in request.form:
            profile_updates["coat_color"] = request.form.get("coat_color", "").strip()[:80] or None
        if "secondary_id" in request.form:
            profile_updates["secondary_id"] = request.form.get("secondary_id", "").strip()[:100] or None
        if "reproductive_status" in request.form:
            repro = request.form.get("reproductive_status", "nao_informado").strip().lower()
            profile_updates["reproductive_status"] = repro if repro != "nao_informado" else None
        if "accommodation_type" in request.form:
            profile_updates["accommodation_type"] = request.form.get("accommodation_type", "").strip().lower() or None
        if "accommodation_name" in request.form:
            profile_updates["accommodation_name"] = request.form.get("accommodation_name", "").strip()[:120] or None

        updated = update_animal_sanitary_profile(animal["id"], profile_updates)
        updated["organization_id"] = updated.get("organization_id") or ctx["organization_id"]
        stats = generate_schedules_for_animal(updated)
        msg = "Perfil cadastral, alojamento e configuração sanitária atualizados!"
        if stats["created_schedules"] > 0:
            msg += f" {stats['created_schedules']} agendamento(s) gerado(s) com base nos protocolos compatíveis."
        flash(msg, "success")
        return redirect(url_for("animal_detail", token=updated["qr_code_token"]))
    except SupabaseServiceError as exc:
        flash(str(exc), "danger")
        return redirect(_safe_redirect_back("animals_list"))


# ----------------------------------------------------------------------------
# 9. Endpoint JSON interno (seleção dinâmica por lote/manual em Campanhas)
# ----------------------------------------------------------------------------
@sanitary_bp.route("/api/propriedades/<string:property_id>/animais")
@operator_required
def api_property_animals(property_id: str):
    if not is_valid_uuid(property_id):
        return jsonify({"error": "Propriedade inválida."}), 400
    lot_id = request.args.get("lot_id", "").strip() or None
    species_filter = request.args.get("species", "todas").strip().lower()
    search = request.args.get("q", "").strip().lower()

    try:
        ctx = get_sanitary_context()
        raw_animals = list_animals(
            organization_id=ctx["organization_id"],
            property_id=property_id,
            lot_id=lot_id if (lot_id and is_valid_uuid(lot_id)) else None,
            only_active=True,
        )
        animals = enrich_animals_list(raw_animals, brackets=ctx["age_brackets"])
        animals = filter_animals_by_species(animals, species_filter)
        lot_map = {l["id"]: l["name"] for l in ctx["lots"]}

        results = []
        for a in animals:
            haystack = (
                f"{a.get('ear_tag', '')} {a.get('name') or ''} "
                f"{a.get('breed', '')} {a.get('species_label', '')} {a.get('housing_display', '')}"
            ).lower()
            if search and search not in haystack:
                continue
            results.append(
                {
                    "id": a["id"],
                    "ear_tag": a["ear_tag"],
                    "name": a.get("name") or "",
                    "species": a.get("species"),
                    "species_label": a.get("species_label"),
                    "sex": a.get("sex"),
                    "breed": a.get("breed"),
                    "housing_display": a.get("housing_display") or "",
                    "age_label": a["age_label"],
                    "age_category": a["age_category"],
                    "age_category_name": a["age_category_name"],
                    "lot_id": a.get("lot_id"),
                    "lot_name": lot_map.get(a.get("lot_id"), "Sem lote"),
                }
            )

        prop_lots = [
            {"id": l["id"], "name": l["name"]}
            for l in ctx["lots"]
            if l.get("property_id") == property_id
        ]
        return jsonify({"animals": results, "lots": prop_lots})
    except SupabaseServiceError as exc:
        return jsonify({"error": str(exc)}), 500
