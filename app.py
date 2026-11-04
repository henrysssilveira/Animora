import re
import uuid
from datetime import date, datetime
from flask import Flask, flash, redirect, render_template, request, send_file, url_for

from blueprints.labels_bp import labels_bp
from blueprints.sanitary_bp import sanitary_bp
from config import Config
from services.auth_service import (
    ACCESS_LEVEL_LABELS,
    ROLE_LABELS,
    authenticate_operator,
    get_access_level,
    get_current_operator,
    is_admin_authenticated,
    is_operator_authenticated,
    is_property_authenticated,
    logout_operator,
    property_required,
)
from services.classification_service import (
    AGE_CATEGORY_LABELS,
    calculate_age_days,
    classify_age_days,
    enrich_animal_with_age,
    enrich_animals_list,
    filter_animals_by_age_category,
    filter_animals_by_species,
    summarize_age_categories,
)
from services.demo_cleanup_service import clean_demo_command
from services.label_service import (
    activate_tag_unit_for_animal,
    find_linkable_tag_by_number_safe,
    get_tag_unit_by_number_safe,
    get_tag_unit_by_token_or_id_safe,
    list_available_tag_units_safe,
)
from services.management_service import (
    get_feeding_plan_for_animal_safe,
    list_management_alerts_safe,
    list_management_records_for_animal_safe,
)
from services.qrcode_service import ensure_qrcode_exists, generate_animal_qrcode
from services.sanitary_service import (
    HEALTH_RECORD_TYPE_LABELS,
    create_health_record,
    get_animal_sanitary_card,
    get_sanitary_context_safe,
    list_vaccines,
)
from services.schedule_engine import (
    ONBOARDING_MODE_LABELS,
    generate_schedules_for_animal,
)
from services.species_service import (
    ACCOMMODATION_TYPE_LABELS,
    MANAGEMENT_ROUTINE_META,
    PREVENTIVE_ITEM_TYPE_META,
    PROPERTY_FOCUS_LABELS,
    PROTOCOL_PURPOSE_LABELS,
    REPRODUCTIVE_STATUS_LABELS,
    SPECIES_CHOICES,
    SPECIES_META,
    TARGET_SPECIES_LABELS,
    get_routines_for_species,
    get_species_meta,
    normalize_species,
)
from services.supabase_service import (
    DuplicateEarTagError,
    SupabaseServiceError,
    create_animal,
    get_animal_by_ear_tag,
    get_animal_by_token_or_id,
    is_valid_uuid,
    list_animals,
)

ORIGIN_TYPE_LABELS: dict[str, str] = {
    "nascido_propriedade": "Nascido na propriedade",
    "adquirido_externo": "Adquirido externamente",
    "pre_existente": "Plantel pré-existente na propriedade",
}


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Garante que o diretório de QR Codes exista ao iniciar
    Config.QRCODES_DIR.mkdir(parents=True, exist_ok=True)

    # Registra os Blueprints modulares (Gestão Sanitária + Etiquetas QR)
    app.register_blueprint(sanitary_bp)
    app.register_blueprint(labels_bp)

    # Comandos administrativos via Flask CLI (ex.: `flask clean-demo`)
    app.cli.add_command(clean_demo_command)

    # -------------------------------------------------------------------------
    # Contexto global para os templates (3 níveis: Common, Property, Admin)
    # -------------------------------------------------------------------------
    @app.context_processor
    def inject_global_context() -> dict:
        return {
            "access_level": get_access_level(),
            "is_property_authenticated": is_property_authenticated(),
            "is_operator_authenticated": is_operator_authenticated(),
            "is_admin_authenticated": is_admin_authenticated(),
            "current_operator": get_current_operator(),
            "species_meta": SPECIES_META,
            "species_choices": SPECIES_CHOICES,
            "target_species_labels": TARGET_SPECIES_LABELS,
            "accommodation_types": ACCOMMODATION_TYPE_LABELS,
            "reproductive_statuses": REPRODUCTIVE_STATUS_LABELS,
            "property_focus_labels": PROPERTY_FOCUS_LABELS,
            "protocol_purpose_labels": PROTOCOL_PURPOSE_LABELS,
            "preventive_item_types": PREVENTIVE_ITEM_TYPE_META,
            "management_routines": MANAGEMENT_ROUTINE_META,
        }

    # -------------------------------------------------------------------------
    # Filtros Jinja2 para formatação no padrão brasileiro
    # -------------------------------------------------------------------------
    @app.template_filter("date_br")
    def format_date_br(value: str | None) -> str:
        if not value:
            return "Não informado"
        try:
            raw = str(value)[:10]
            parsed = datetime.strptime(raw, "%Y-%m-%d").date()
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            return str(value)

    @app.template_filter("datetime_br")
    def format_datetime_br(value: str | None) -> str:
        if not value:
            return "—"
        try:
            normalized = str(value).replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed.strftime("%d/%m/%Y às %H:%M")
        except ValueError:
            return str(value)

    @app.template_filter("weight_br")
    def format_weight_br(value: float | int | str | None) -> str:
        if value is None or value == "" or not isinstance(value, (int, float, str)):
            return "Não informado"
        try:
            num = float(value)
            formatted = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"{formatted} kg"
        except (ValueError, TypeError):
            return f"{value} kg"

    # -------------------------------------------------------------------------
    # Autenticação por Nível de Acesso (Property e Admin; Common é público)
    # -------------------------------------------------------------------------
    @app.route("/acesso", methods=["GET", "POST"])
    def operator_login():
        """Página de autenticação dos níveis Property e Admin."""
        requested_level = (
            request.args.get("level") or request.form.get("access_level") or "property"
        ).strip().lower()
        if requested_level not in ("property", "admin"):
            requested_level = "property"

        next_url = (request.args.get("next") or request.form.get("next") or "").strip()
        if not next_url.startswith("/") or next_url.startswith("//"):
            next_url = url_for("labels.generator") if requested_level == "admin" else url_for("dashboard")

        if request.method == "POST":
            operator_name = request.form.get("operator_name", "")
            operator_role = request.form.get("operator_role", "produtor")
            email = request.form.get("email", "")
            access_pin = request.form.get("access_pin", "")

            ok, err_msg = authenticate_operator(
                access_pin=access_pin,
                operator_name=operator_name,
                access_level=requested_level,
                operator_role=operator_role,
                email=email,
            )
            if ok:
                active_lbl = ACCESS_LEVEL_LABELS.get(get_access_level(), "Property")
                flash(f"Sessão iniciada com sucesso no nível {active_lbl}.", "success")
                return redirect(next_url)
            flash(err_msg or "Não foi possível autenticar.", "danger")

        property_roles = {k: v for k, v in ROLE_LABELS.items() if k != "admin"}
        return render_template(
            "access.html",
            next_url=next_url,
            selected_level=requested_level,
            access_levels={
                "property": ACCESS_LEVEL_LABELS["property"],
                "admin": ACCESS_LEVEL_LABELS["admin"],
            },
            roles=property_roles,
            show_property_dev_hint=(Config.DEBUG and not Config.IS_CUSTOM_PROPERTY_PIN_CONFIGURED),
            default_property_pin=(
                Config.PROPERTY_ACCESS_PIN if (Config.DEBUG and not Config.IS_CUSTOM_PROPERTY_PIN_CONFIGURED) else ""
            ),
            show_admin_dev_hint=(Config.DEBUG and not Config.IS_CUSTOM_ADMIN_PIN_CONFIGURED),
            default_admin_pin=(
                Config.ADMIN_ACCESS_PIN if (Config.DEBUG and not Config.IS_CUSTOM_ADMIN_PIN_CONFIGURED) else ""
            ),
        )

    @app.route("/sair", methods=["GET", "POST"])
    def operator_logout():
        logout_operator()
        flash("Sessão encerrada. Você está agora no nível Common (consulta pública).", "warning")
        return redirect(url_for("dashboard"))

    # -------------------------------------------------------------------------
    # Validação dos dados do formulário de cadastro/atribuição multi-espécie
    # -------------------------------------------------------------------------
    def validate_animal_form(form: dict, ctx: dict) -> tuple[dict, list[str]]:
        errors: list[str] = []

        ear_tag = form.get("ear_tag", "").strip()
        species = normalize_species(form.get("species", "bovino"))
        name = form.get("name", "").strip()
        sex = form.get("sex", "").strip()
        breed = form.get("breed", "").strip()
        coat_color = form.get("coat_color", "").strip()
        secondary_id = form.get("secondary_id", "").strip()
        reproductive_status = form.get("reproductive_status", "nao_informado").strip().lower()
        accommodation_type = form.get("accommodation_type", "").strip().lower()
        accommodation_name = form.get("accommodation_name", "").strip()
        birth_date_str = form.get("birth_date", "").strip()
        weight_str = form.get("initial_weight", "").strip()
        notes = form.get("notes", "").strip()

        property_id = form.get("property_id", "").strip()
        lot_id = form.get("lot_id", "").strip()
        origin_type = form.get("origin_type", "nascido_propriedade").strip()
        onboarding_mode = form.get("sanitary_onboarding_mode", "").strip()
        inclusion_date_str = form.get("inclusion_date", "").strip() or date.today().isoformat()
        initial_sanitary_notes = form.get("initial_sanitary_notes", "").strip()

        if not ear_tag:
            errors.append("O código de identificação (etiqueta QR / brinco / placa) é obrigatório.")
        elif len(ear_tag) > 100:
            errors.append("O código de identificação deve ter no máximo 100 caracteres.")

        if name and len(name) > 150:
            errors.append("O nome do animal deve ter no máximo 150 caracteres.")

        if sex not in ("Macho", "Fêmea"):
            errors.append("Selecione o sexo do animal (Macho ou Fêmea).")

        if not breed:
            errors.append("A raça do animal é obrigatória.")
        elif len(breed) > 100:
            errors.append("A raça deve ter no máximo 100 caracteres.")

        if coat_color and len(coat_color) > 80:
            errors.append("A pelagem deve ter no máximo 80 caracteres.")

        if secondary_id and len(secondary_id) > 100:
            errors.append("O registro/microchip secundário deve ter no máximo 100 caracteres.")

        if reproductive_status not in REPRODUCTIVE_STATUS_LABELS:
            reproductive_status = "nao_informado"

        if accommodation_type and accommodation_type not in ACCOMMODATION_TYPE_LABELS:
            accommodation_type = ""

        if accommodation_name and len(accommodation_name) > 120:
            errors.append("A identificação do alojamento/baia deve ter no máximo 120 caracteres.")

        parsed_birth: date | None = None
        if not birth_date_str:
            errors.append("A data de nascimento é obrigatória.")
        else:
            try:
                parsed_birth = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
                if parsed_birth > date.today():
                    errors.append("A data de nascimento não pode ser uma data futura.")
            except ValueError:
                errors.append("Informe uma data de nascimento válida.")

        try:
            parsed_inclusion = datetime.strptime(inclusion_date_str, "%Y-%m-%d").date()
            if parsed_inclusion > date.today():
                errors.append("A data de inclusão não pode ser futura.")
        except ValueError:
            errors.append("Informe uma data de inclusão válida.")

        initial_weight: float | None = None
        if weight_str:
            normalized_weight = weight_str.replace(",", ".")
            try:
                initial_weight = round(float(normalized_weight), 2)
                if initial_weight < 0:
                    errors.append("O peso inicial não pode ser negativo.")
                elif initial_weight > 3000:
                    errors.append("Informe um peso inicial válido em quilogramas (kg).")
            except ValueError:
                errors.append("Informe um valor numérico válido para o peso inicial.")

        if origin_type not in ("nascido_propriedade", "adquirido_externo", "pre_existente"):
            origin_type = "nascido_propriedade"

        age_days = calculate_age_days(parsed_birth) if parsed_birth else 0
        if not onboarding_mode or onboarding_mode not in ONBOARDING_MODE_LABELS:
            if age_days > 30 and origin_type in ("adquirido_externo", "pre_existente"):
                onboarding_mode = "historico_desconhecido"
            else:
                onboarding_mode = "acompanhamento_nascimento"

        if ctx.get("migration_ready") and ctx.get("properties"):
            valid_prop_ids = {p["id"] for p in ctx["properties"]}
            if not property_id:
                property_id = ctx["properties"][0]["id"]
            elif property_id not in valid_prop_ids:
                errors.append("Selecione uma propriedade válida.")

            if lot_id:
                valid_lot_ids = {l["id"] for l in ctx["lots"] if l.get("property_id") == property_id}
                if lot_id not in valid_lot_ids:
                    errors.append("O lote selecionado não pertence à propriedade informada.")
        else:
            property_id = ""
            lot_id = ""

        cleaned = {
            "ear_tag": ear_tag,
            "species": species,
            "name": name or None,
            "sex": sex,
            "breed": breed,
            "coat_color": coat_color or None,
            "secondary_id": secondary_id or None,
            "reproductive_status": reproductive_status if reproductive_status != "nao_informado" else None,
            "accommodation_type": accommodation_type or None,
            "accommodation_name": accommodation_name or None,
            "birth_date": birth_date_str,
            "initial_weight": initial_weight,
            "notes": notes or None,
            "organization_id": ctx.get("organization_id"),
            "property_id": property_id or None,
            "lot_id": lot_id or None,
            "status": "ativo",
            "origin_type": origin_type,
            "sanitary_onboarding_mode": onboarding_mode,
            "inclusion_date": inclusion_date_str,
            "initial_sanitary_notes": initial_sanitary_notes or None,
        }
        return cleaned, errors

    # -------------------------------------------------------------------------
    # Rotas principais da aplicação
    # -------------------------------------------------------------------------
    @app.route("/")
    def dashboard():
        """
        Rota inicial adaptativa por nível de acesso:
        - Common (público): exibe exclusivamente a Consulta Pública de Etiquetas / QR Code.
        - Property / Admin: exibe o Dashboard completo do rebanho e atalhos operacionais.
        """
        if not is_property_authenticated():
            return render_template("public_lookup.html", search_query="")

        animals: list[dict] = []
        db_error: str | None = None
        ctx = get_sanitary_context_safe()

        try:
            raw_animals = list_animals()
            animals = enrich_animals_list(raw_animals, brackets=ctx["age_brackets"])
        except SupabaseServiceError as exc:
            db_error = str(exc)

        total_animals = len(animals)
        males_count = sum(1 for a in animals if a.get("sex") == "Macho")
        females_count = sum(1 for a in animals if a.get("sex") == "Fêmea")
        age_summary = summarize_age_categories(animals)
        recent_animals = animals[:5]
        mgmt_alerts = list_management_alerts_safe(
            organization_id=ctx.get("organization_id"),
            age_brackets=ctx.get("age_brackets"),
        )

        return render_template(
            "dashboard.html",
            total_animals=total_animals,
            males_count=males_count,
            females_count=females_count,
            age_summary=age_summary,
            recent_animals=recent_animals,
            mgmt_alerts=mgmt_alerts,
            db_error=db_error,
        )

    @app.route("/consulta")
    def public_lookup():
        """
        Busca pública para usuários Common (e internos): localiza a ficha pública
        a partir do número da etiqueta/brinco, token UUID ou link completo do QR Code.
        """
        raw_q = (request.args.get("q") or "").strip()
        if not raw_q:
            return render_template("public_lookup.html", search_query="")

        cleaned_q = raw_q.lstrip("#").strip()
        if "/animal/" in cleaned_q:
            cleaned_q = cleaned_q.split("/animal/", 1)[1].split("?", 1)[0].strip("/")

        if is_valid_uuid(cleaned_q):
            return redirect(url_for("animal_detail", token=cleaned_q))

        try:
            animal = get_animal_by_ear_tag(cleaned_q)
            if animal and animal.get("qr_code_token"):
                return redirect(url_for("animal_detail", token=animal["qr_code_token"]))

            tag_unit = get_tag_unit_by_number_safe(cleaned_q)
            if tag_unit and tag_unit.get("qr_token"):
                return redirect(url_for("animal_detail", token=tag_unit["qr_token"]))
        except SupabaseServiceError as exc:
            flash(str(exc), "danger")
            return render_template("public_lookup.html", search_query=raw_q), 503

        flash(
            f"Nenhuma etiqueta ou animal localizado para '{raw_q}'. Verifique o código informado ou escaneie o QR Code.",
            "warning",
        )
        return render_template("public_lookup.html", search_query=raw_q), 404

    @app.route("/animals")
    @property_required
    def animals_list():
        """Página Plantel / Animais (Property e Admin): filtros por espécie, propriedade, faixa etária e busca."""
        animals: list[dict] = []
        db_error: str | None = None
        ctx = get_sanitary_context_safe()

        selected_species = request.args.get("species", "todas").strip().lower()
        selected_age = request.args.get("age_category", "todas").strip()
        selected_property = request.args.get("property_id", "").strip()
        search_q = request.args.get("q", "").strip()

        try:
            raw_animals = list_animals(property_id=selected_property or None)
            all_enriched = enrich_animals_list(raw_animals, brackets=ctx["age_brackets"])
            overall_species_counts = summarize_age_categories(all_enriched)
            species_filtered = filter_animals_by_species(all_enriched, selected_species)
            age_summary = summarize_age_categories(species_filtered)
            animals = filter_animals_by_age_category(species_filtered, selected_age)
            if search_q:
                q_low = search_q.lower()
                animals = [
                    a
                    for a in animals
                    if q_low in str(a.get("ear_tag") or "").lower()
                    or q_low in str(a.get("name") or "").lower()
                    or q_low in str(a.get("breed") or "").lower()
                    or q_low in str(a.get("housing_display") or "").lower()
                    or q_low in str(a.get("coat_color") or "").lower()
                ]
        except SupabaseServiceError as exc:
            db_error = str(exc)
            age_summary = summarize_age_categories([])
            overall_species_counts = age_summary

        prop_map = {p["id"]: p["name"] for p in ctx.get("properties", [])}
        lot_map = {l["id"]: l["name"] for l in ctx.get("lots", [])}
        for a in animals:
            a["property_name"] = prop_map.get(a.get("property_id"), "—")
            a["lot_name"] = lot_map.get(a.get("lot_id"), "—")

        return render_template(
            "animals.html",
            animals=animals,
            age_summary=age_summary,
            overall_species_counts=overall_species_counts,
            age_categories=AGE_CATEGORY_LABELS,
            selected_species=selected_species,
            selected_age=selected_age,
            selected_property=selected_property,
            search_q=search_q,
            ctx=ctx,
            db_error=db_error,
        )

    @app.route("/animals/new", methods=["GET", "POST"])
    @property_required
    def animal_new():
        """
        Adição e atribuição de bovino (Property e Admin):
        - Usuários Property atribuem animais vinculando etiquetas QR já criadas pelo Admin (`tag_units`).
        - Usuários Admin podem tanto vincular uma etiqueta pré-criada quanto gerar um QR Code avulso.
        """
        ctx = get_sanitary_context_safe()
        default_prop = ctx["properties"][0]["id"] if ctx.get("properties") else ""
        available_tags = list_available_tag_units_safe(ctx.get("organization_id"))
        can_create_adhoc_qr = is_admin_authenticated()

        preset_tag_id = request.args.get("tag_unit_id", "").strip()
        preset_ear_tag = ""
        if preset_tag_id:
            matched_preset = next((t for t in available_tags if t["id"] == preset_tag_id), None)
            if matched_preset:
                preset_ear_tag = matched_preset["tag_number"]
        elif not can_create_adhoc_qr and available_tags:
            preset_tag_id = available_tags[0]["id"]
            preset_ear_tag = available_tags[0]["tag_number"]

        preset_species = normalize_species(request.args.get("species", "bovino"))
        form_data = {
            "tag_unit_id": preset_tag_id,
            "ear_tag": preset_ear_tag,
            "species": preset_species,
            "name": "",
            "sex": "",
            "breed": "",
            "coat_color": "",
            "secondary_id": "",
            "reproductive_status": "nao_informado",
            "accommodation_type": get_species_meta(preset_species)["default_accommodation"],
            "accommodation_name": "",
            "birth_date": "",
            "initial_weight": "",
            "notes": "",
            "property_id": default_prop,
            "lot_id": "",
            "origin_type": "nascido_propriedade",
            "sanitary_onboarding_mode": "acompanhamento_nascimento",
            "inclusion_date": date.today().isoformat(),
            "initial_sanitary_notes": "",
            "initial_evaluation_text": "",
        }

        if request.method == "POST":
            form_data = {key: request.form.get(key, "") for key in form_data}

            linked_tag: dict | None = None
            chosen_tag_id = form_data.get("tag_unit_id", "").strip()
            if chosen_tag_id:
                cand = get_tag_unit_by_token_or_id_safe(chosen_tag_id)
                if cand and cand.get("status") in ("available", "assigned"):
                    linked_tag = cand
                    form_data["ear_tag"] = cand["tag_number"]
            elif form_data.get("ear_tag", "").strip():
                linked_tag = find_linkable_tag_by_number_safe(
                    ctx.get("organization_id"),
                    form_data["ear_tag"].strip(),
                )
                if linked_tag:
                    form_data["ear_tag"] = linked_tag["tag_number"]
                    form_data["tag_unit_id"] = linked_tag["id"]

            cleaned_data, validation_errors = validate_animal_form(form_data, ctx)

            if not can_create_adhoc_qr and not linked_tag:
                validation_errors.insert(
                    0,
                    "Selecione uma etiqueta QR disponível (criada pelo Admin) para atribuir ao animal. "
                    "A criação de novos QR Codes é exclusiva do perfil Admin.",
                )

            if validation_errors:
                for err in validation_errors:
                    flash(err, "danger")
                return render_template(
                    "animal_form.html",
                    form_data=form_data,
                    ctx=ctx,
                    available_tags=available_tags,
                    can_create_adhoc_qr=can_create_adhoc_qr,
                    onboarding_modes=ONBOARDING_MODE_LABELS,
                    max_date=date.today().isoformat(),
                ), 400

            try:
                animal_uuid = str(uuid.uuid4())
                qr_token = str(linked_tag["qr_token"]) if linked_tag else str(uuid.uuid4())

                cleaned_data["id"] = animal_uuid
                cleaned_data["qr_code_token"] = qr_token

                created_animal = create_animal(cleaned_data)

                if linked_tag:
                    activate_tag_unit_for_animal(linked_tag["id"], created_animal["id"])
                    ensure_qrcode_exists(
                        qr_code_token=created_animal["qr_code_token"],
                        base_url=request.url_root,
                    )
                else:
                    generate_animal_qrcode(
                        qr_code_token=created_animal["qr_code_token"],
                        base_url=request.url_root,
                    )

                age_days = calculate_age_days(created_animal.get("birth_date"))
                age_info = classify_age_days(age_days, brackets=ctx.get("age_brackets"))

                eval_text = form_data.get("initial_evaluation_text", "").strip()
                if eval_text and ctx.get("migration_ready") and created_animal.get("property_id"):
                    try:
                        create_health_record(
                            ctx["organization_id"],
                            {
                                "animal_id": created_animal["id"],
                                "record_type": "avaliacao_inicial",
                                "title": "Avaliação Sanitária Inicial no Cadastro",
                                "description": eval_text,
                                "veterinarian_or_responsible": get_current_operator()["name"],
                            },
                        )
                    except SupabaseServiceError:
                        pass

                sched_stats = {"created_schedules": 0}
                if ctx.get("migration_ready") and created_animal.get("property_id"):
                    sched_stats = generate_schedules_for_animal(created_animal)

                sched_msg = (
                    f" Foram gerados {sched_stats['created_schedules']} agendamento(s) sanitário(s) automáticos."
                    if sched_stats["created_schedules"] > 0
                    else ""
                )
                tag_msg = (
                    " Etiqueta QR vinculada e ativada com sucesso!"
                    if linked_tag
                    else " QR Code exclusivo gerado."
                )
                flash(
                    f"Animal (Etiqueta #{created_animal['ear_tag']}) registrado como {age_info['name']}!{tag_msg}{sched_msg}",
                    "success",
                )
                return redirect(
                    url_for(
                        "animal_detail",
                        token=created_animal["qr_code_token"],
                        registered="1",
                    )
                )
            except DuplicateEarTagError as exc:
                flash(str(exc), "warning")
                return render_template(
                    "animal_form.html",
                    form_data=form_data,
                    ctx=ctx,
                    available_tags=available_tags,
                    can_create_adhoc_qr=can_create_adhoc_qr,
                    onboarding_modes=ONBOARDING_MODE_LABELS,
                    max_date=date.today().isoformat(),
                ), 409
            except SupabaseServiceError as exc:
                flash(str(exc), "danger")
                return render_template(
                    "animal_form.html",
                    form_data=form_data,
                    ctx=ctx,
                    available_tags=available_tags,
                    can_create_adhoc_qr=can_create_adhoc_qr,
                    onboarding_modes=ONBOARDING_MODE_LABELS,
                    max_date=date.today().isoformat(),
                ), 503

        return render_template(
            "animal_form.html",
            form_data=form_data,
            ctx=ctx,
            available_tags=available_tags,
            can_create_adhoc_qr=can_create_adhoc_qr,
            onboarding_modes=ONBOARDING_MODE_LABELS,
            max_date=date.today().isoformat(),
        )

    @app.route("/animal/<string:token>")
    def animal_detail(token: str):
        """
        Ficha Individual e Carteira Sanitária do animal (acessada via QR Code ou busca):
        - Common (ou ?public=1): vê apenas dados públicos (de onde o animal veio, nome e informações principais).
        - Property / Admin: vê também a Carteira Sanitária completa, lotes e observações privadas.
        """
        db_error: str | None = None
        animal: dict | None = None
        ctx = get_sanitary_context_safe()

        try:
            raw_animal = get_animal_by_token_or_id(token)
            if raw_animal:
                animal = enrich_animal_with_age(raw_animal, brackets=ctx["age_brackets"])
        except SupabaseServiceError as exc:
            db_error = str(exc)

        if db_error:
            return render_template(
                "animal_detail.html",
                animal=None,
                db_error=db_error,
            ), 503

        if not animal:
            unlinked_tag = get_tag_unit_by_token_or_id_safe(token)
            if unlinked_tag:
                return render_template(
                    "animal_detail.html",
                    animal=None,
                    unlinked_tag=unlinked_tag,
                    db_error=None,
                ), 200
            return render_template(
                "animal_detail.html",
                animal=None,
                unlinked_tag=None,
                db_error=None,
            ), 404

        prop_obj = next((p for p in ctx.get("properties", []) if p["id"] == animal.get("property_id")), None)
        lot_map = {l["id"]: l["name"] for l in ctx.get("lots", [])}

        property_name = prop_obj["name"] if prop_obj else "Propriedade Animora"
        property_location = ""
        if prop_obj:
            loc_parts = [p for p in (prop_obj.get("municipality"), prop_obj.get("state")) if p]
            property_location = " / ".join(loc_parts)

        origin_key = str(animal.get("origin_type") or "nascido_propriedade")
        origin_label = ORIGIN_TYPE_LABELS.get(origin_key, "Nascido na propriedade")

        animal["property_name"] = property_name
        animal["property_location"] = property_location
        animal["origin_label"] = origin_label
        animal["lot_name"] = lot_map.get(animal.get("lot_id"), "Sem lote vinculado")
        animal["onboarding_label"] = ONBOARDING_MODE_LABELS.get(
            animal.get("sanitary_onboarding_mode") or "acompanhamento_nascimento",
            "Acompanhamento desde o nascimento",
        )

        qr_token = animal["qr_code_token"]
        _, public_url = ensure_qrcode_exists(qr_token, request.url_root)
        qr_image_url = url_for("static", filename=f"qrcodes/{qr_token}.png")
        just_registered = request.args.get("registered") == "1"

        force_public_preview = request.args.get("public") == "1"
        can_view_private_sanitary = is_property_authenticated() and not force_public_preview

        sanitary_card = None
        active_vaccines: list[dict] = []
        feeding_plan = None
        management_records: list[dict] = []
        species_routines = get_routines_for_species(animal.get("species"))
        migration_004_ready = True

        if can_view_private_sanitary:
            if ctx.get("migration_ready"):
                try:
                    sanitary_card = get_animal_sanitary_card(animal, ctx.get("organization_id"))
                    active_vaccines = list_vaccines(
                        ctx["organization_id"],
                        only_active=True,
                        species=animal.get("species"),
                    )
                    feeding_plan, feed_ok = get_feeding_plan_for_animal_safe(animal["id"])
                    management_records, mgmt_ok = list_management_records_for_animal_safe(animal["id"])
                    migration_004_ready = bool(feed_ok and mgmt_ok)
                except SupabaseServiceError as exc:
                    flash(str(exc), "warning")
        else:
            # Sanitiza campos privados em memória para o nível Common / consulta pública:
            # exibe Identificação + Espécie + Pelagem + Origem + Alojamento;
            # mantém Dieta/Cocho, Sanidade, Reprodução e Manejo restritos ao Property/Admin.
            animal = {
                "id": animal["id"],
                "ear_tag": animal["ear_tag"],
                "species": animal.get("species"),
                "species_label": animal.get("species_label"),
                "species_emoji": animal.get("species_emoji"),
                "species_badge_class": animal.get("species_badge_class"),
                "name": animal.get("name"),
                "sex": animal.get("sex"),
                "breed": animal.get("breed"),
                "coat_color": animal.get("coat_color"),
                "birth_date": animal.get("birth_date"),
                "age_days": animal.get("age_days"),
                "age_label": animal.get("age_label"),
                "age_category": animal.get("age_category"),
                "age_category_name": animal.get("age_category_name"),
                "age_badge_class": animal.get("age_badge_class"),
                "property_name": animal.get("property_name"),
                "property_location": animal.get("property_location"),
                "origin_label": animal.get("origin_label"),
                "accommodation_type": animal.get("accommodation_type"),
                "accommodation_type_label": animal.get("accommodation_type_label"),
                "accommodation_name": animal.get("accommodation_name"),
                "housing_display": animal.get("housing_display"),
                "qr_code_token": animal["qr_code_token"],
                "created_at": animal.get("created_at"),
            }

        return render_template(
            "animal_detail.html",
            animal=animal,
            qr_image_url=qr_image_url,
            public_url=public_url,
            just_registered=just_registered,
            can_view_private_sanitary=can_view_private_sanitary,
            force_public_preview=force_public_preview,
            sanitary_card=sanitary_card,
            active_vaccines=active_vaccines,
            feeding_plan=feeding_plan,
            management_records=management_records,
            species_routines=species_routines,
            migration_004_ready=migration_004_ready,
            health_record_types=HEALTH_RECORD_TYPE_LABELS,
            onboarding_modes=ONBOARDING_MODE_LABELS,
            ctx=ctx,
            now_dt_local=datetime.now().strftime("%Y-%m-%dT%H:%M"),
            today_iso=date.today().isoformat(),
            db_error=None,
        )

    @app.route("/animal/<string:token>/placa")
    @property_required
    def animal_stall_card(token: str):
        """
        Página imprimível de 'Placa de Baia / Cocho & Ficha Cadastral QR' (Property e Admin):
        Ideal para plastificar e fixar na baia/cocheira/cocho ou arquivar em pasta cadastral.
        """
        ctx = get_sanitary_context_safe()
        try:
            raw_animal = get_animal_by_token_or_id(token)
        except SupabaseServiceError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("animals_list"))

        if not raw_animal:
            flash("Animal não encontrado para emissão da placa/ficha.", "warning")
            return redirect(url_for("animals_list"))

        animal = enrich_animal_with_age(raw_animal, brackets=ctx["age_brackets"])
        prop_obj = next((p for p in ctx.get("properties", []) if p["id"] == animal.get("property_id")), None)
        lot_map = {l["id"]: l["name"] for l in ctx.get("lots", [])}

        animal["property_name"] = prop_obj["name"] if prop_obj else "Propriedade Animora"
        animal["property_location"] = (
            " / ".join([p for p in (prop_obj.get("municipality"), prop_obj.get("state")) if p])
            if prop_obj
            else ""
        )
        animal["origin_label"] = ORIGIN_TYPE_LABELS.get(
            str(animal.get("origin_type") or "nascido_propriedade"),
            "Nascido na propriedade",
        )
        animal["lot_name"] = lot_map.get(animal.get("lot_id"), "Sem lote")

        qr_token = animal["qr_code_token"]
        _, public_url = ensure_qrcode_exists(qr_token, request.url_root)
        qr_image_url = url_for("static", filename=f"qrcodes/{qr_token}.png")

        feeding_plan, _ = get_feeding_plan_for_animal_safe(animal["id"])
        card_mode = request.args.get("mode", "baia").strip().lower()
        if card_mode not in ("baia", "ficha"):
            card_mode = "baia"

        return render_template(
            "animal_stall_card.html",
            animal=animal,
            qr_image_url=qr_image_url,
            public_url=public_url,
            feeding_plan=feeding_plan,
            card_mode=card_mode,
        )

    @app.route("/animal/<string:token>/qrcode/download")
    @property_required
    def download_qrcode(token: str):
        """Faz o download do QR Code do animal em formato PNG (Property e Admin)."""
        try:
            animal = get_animal_by_token_or_id(token)
        except SupabaseServiceError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("animals_list"))

        if not animal:
            return render_template("animal_detail.html", animal=None, db_error=None), 404

        qr_token = animal["qr_code_token"]
        file_path, _ = ensure_qrcode_exists(qr_token, request.url_root)

        safe_tag = re.sub(r"[^A-Za-z0-9_-]+", "_", str(animal.get("ear_tag", "animal"))).strip("_")
        download_filename = f"animora_qrcode_brinco_{safe_tag or qr_token}.png"

        return send_file(
            file_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=download_filename,
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
