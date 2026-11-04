document.addEventListener("DOMContentLoaded", () => {
    const escapeHtml = (str) => {
        const div = document.createElement("div");
        div.textContent = str ?? "";
        return div.innerHTML;
    };

    // -------------------------------------------------------------------------
    // 1. Autofill de dados da vacina ao selecionar no catálogo
    // -------------------------------------------------------------------------
    const bindVaccineSelectAutofill = (selectEl, scopeEl) => {
        if (!selectEl || !scopeEl) return;
        selectEl.addEventListener("change", () => {
            const opt = selectEl.options[selectEl.selectedIndex];
            if (!opt) return;
            const manufacturer = opt.getAttribute("data-manufacturer") || "";
            const route = opt.getAttribute("data-route") || "";
            const unit = opt.getAttribute("data-unit") || "";
            const itemType = opt.getAttribute("data-item-type") || "vacina";

            const manInput = scopeEl.querySelector('[name="manufacturer"]');
            const routeInput = scopeEl.querySelector('[name="administration_route"]');
            const unitInput = scopeEl.querySelector('[name="dosage_unit"]');
            const dosageInput = scopeEl.querySelector('[name="dosage"]');
            const batchInput = scopeEl.querySelector('[name="product_batch"]');
            const batchReqStar = scopeEl.querySelector("#applyBatchRequiredStar");
            const examWrap = scopeEl.querySelector("#applyExamResultGroup");
            const isHistorical = scopeEl.querySelector('[name="is_historical_record"]')?.value === "true";

            if (manInput && manufacturer) manInput.value = manufacturer;
            if (routeInput && route) routeInput.value = route;
            if (unitInput && unit) unitInput.value = unit;

            const isExam = itemType === "exame_preventivo";
            if (examWrap) examWrap.classList.toggle("d-none", !isExam);
            if (isExam && dosageInput && !dosageInput.value) dosageInput.value = "1";
            if (batchInput) batchInput.required = !isHistorical && !isExam;
            if (batchReqStar) batchReqStar.classList.toggle("d-none", isHistorical || isExam);
        });
    };

    // -------------------------------------------------------------------------
    // 2. Modal reutilizável de Confirmação / Registro Individual de Vacinação
    // -------------------------------------------------------------------------
    const applyModalEl = document.getElementById("confirmVaccinationModal");
    if (applyModalEl) {
        const applyModal = new bootstrap.Modal(applyModalEl);
        const vaccineSelect = applyModalEl.querySelector('[name="vaccine_id"]');
        bindVaccineSelectAutofill(vaccineSelect, applyModalEl);

        document.addEventListener("click", (evt) => {
            const btn = evt.target.closest(".js-open-apply-modal");
            if (!btn) return;

            const scheduleId = btn.getAttribute("data-schedule-id") || "";
            const animalId = btn.getAttribute("data-animal-id") || "";
            const animalLabel = btn.getAttribute("data-animal-label") || "";
            const vaccineId = btn.getAttribute("data-vaccine-id") || "";
            const doseNumber = btn.getAttribute("data-dose-number") || "1";
            const manufacturer = btn.getAttribute("data-manufacturer") || "";
            const route = btn.getAttribute("data-route") || "";
            const unit = btn.getAttribute("data-unit") || "mL";
            const isHistorical = btn.getAttribute("data-historical") === "1";

            applyModalEl.querySelector('[name="schedule_id"]').value = scheduleId;
            applyModalEl.querySelector('[name="animal_id"]').value = animalId;
            applyModalEl.querySelector('[name="dose_number"]').value = doseNumber;
            applyModalEl.querySelector('[name="is_historical_record"]').value = isHistorical ? "true" : "false";

            const titleBadge = applyModalEl.querySelector("#applyModalAnimalBadge");
            if (titleBadge) titleBadge.textContent = animalLabel || "Animal selecionado";

            const histBanner = applyModalEl.querySelector("#applyModalHistoricalNotice");
            const batchInput = applyModalEl.querySelector('[name="product_batch"]');
            const batchReqStar = applyModalEl.querySelector("#applyBatchRequiredStar");
            if (histBanner) histBanner.classList.toggle("d-none", !isHistorical);
            if (batchInput) batchInput.required = !isHistorical;
            if (batchReqStar) batchReqStar.classList.toggle("d-none", isHistorical);

            if (vaccineSelect) {
                vaccineSelect.value = vaccineId;
                // Se veio de um agendamento fixo, trava visualmente a troca acidental mas envia via hidden/select
                if (!vaccineId && vaccineSelect.options.length > 1) {
                    vaccineSelect.selectedIndex = 0;
                }
            }

            const manInput = applyModalEl.querySelector('[name="manufacturer"]');
            const routeInput = applyModalEl.querySelector('[name="administration_route"]');
            const unitInput = applyModalEl.querySelector('[name="dosage_unit"]');

            if (manufacturer && manInput) manInput.value = manufacturer;
            if (route && routeInput) routeInput.value = route;
            if (unit && unitInput) unitInput.value = unit;

            if (vaccineSelect) {
                vaccineSelect.dispatchEvent(new Event("change"));
            }

            applyModal.show();
        });
    }

    // -------------------------------------------------------------------------
    // 3. Modal de Atualização de Status Não-Aplicado (Não realizada / Cancelada / Desconhecido)
    // -------------------------------------------------------------------------
    const statusModalEl = document.getElementById("scheduleStatusModal");
    if (statusModalEl) {
        const statusModal = new bootstrap.Modal(statusModalEl);
        const statusForm = statusModalEl.querySelector("form");

        document.addEventListener("click", (evt) => {
            const btn = evt.target.closest(".js-open-status-modal");
            if (!btn) return;
            const actionUrl = btn.getAttribute("data-action-url") || "";
            const desc = btn.getAttribute("data-schedule-desc") || "";
            const presetStatus = btn.getAttribute("data-preset-status") || "nao_realizada";

            if (statusForm && actionUrl) statusForm.setAttribute("action", actionUrl);
            const descEl = statusModalEl.querySelector("#statusModalScheduleDesc");
            if (descEl) descEl.textContent = desc;
            const sel = statusModalEl.querySelector('[name="status"]');
            if (sel) sel.value = presetStatus;

            statusModal.show();
        });
    }

    // -------------------------------------------------------------------------
    // 4. Filtro dinâmico de Lote por Propriedade (Cadastro de Animal & Filtros)
    // -------------------------------------------------------------------------
    const propSelect = document.getElementById("property_id");
    const lotSelect = document.getElementById("lot_id");
    if (propSelect && lotSelect && lotSelect.hasAttribute("data-filter-by-property")) {
        const filterLots = () => {
            const propId = propSelect.value;
            Array.from(lotSelect.options).forEach((opt) => {
                if (!opt.value) {
                    opt.hidden = false;
                    return;
                }
                const optProp = opt.getAttribute("data-property-id");
                const match = !propId || optProp === propId;
                opt.hidden = !match;
                if (!match && opt.selected) {
                    lotSelect.value = "";
                }
            });
        };
        propSelect.addEventListener("change", filterLots);
        filterLots();
    }

    // Sugestão inteligente de faixa etária e histórico no cadastro de animais adultos
    const birthInput = document.getElementById("birth_date");
    const agePreviewBadge = document.getElementById("liveAgePreview");
    const onboardingSelect = document.getElementById("sanitary_onboarding_mode");
    const adultHintBox = document.getElementById("adultOnboardingHint");

    if (birthInput && agePreviewBadge) {
        const updateAgePreview = () => {
            if (!birthInput.value) {
                agePreviewBadge.textContent = "Informe a data de nascimento";
                if (adultHintBox) adultHintBox.classList.add("d-none");
                return;
            }
            const parts = birthInput.value.split("-").map(Number);
            const birthDt = new Date(parts[0], parts[1] - 1, parts[2]);
            const now = new Date();
            const todayDt = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            const diffDays = Math.max(0, Math.floor((todayDt - birthDt) / 86400000));

            let cat = "Adulto";
            if (diffDays <= 30) cat = "Recém-nascido";
            else if (diffDays <= 180) cat = "Lactente / Filhote";
            else if (diffDays <= 365) cat = "Jovem";

            agePreviewBadge.textContent = `${cat} • ${diffDays} dia(s)`;

            if (adultHintBox) {
                adultHintBox.classList.toggle("d-none", diffDays <= 30);
            }
        };
        birthInput.addEventListener("change", updateAgePreview);
        updateAgePreview();
    }

    // -------------------------------------------------------------------------
    // 5. Calendário Sanitário Mensal — Clique no Dia
    // -------------------------------------------------------------------------
    const calendarDataScript = document.getElementById("calendarDaysJson");
    const dayDetailContainer = document.getElementById("calendarDayDetailBody");
    const dayDetailTitle = document.getElementById("calendarDayDetailTitle");

    if (calendarDataScript && dayDetailContainer) {
        let dayMap = {};
        try {
            dayMap = JSON.parse(calendarDataScript.textContent || "{}");
        } catch {
            dayMap = {};
        }

        const escapeHtml = (str) => {
            const div = document.createElement("div");
            div.textContent = str ?? "";
            return div.innerHTML;
        };

        const renderDay = (dateIso) => {
            document.querySelectorAll(".calendar-day-cell.selected-day").forEach((el) => {
                el.classList.remove("selected-day");
            });
            const cell = document.querySelector(`.calendar-day-cell[data-date="${dateIso}"]`);
            if (cell) cell.classList.add("selected-day");

            const info = dayMap[dateIso];
            if (!info) {
                dayDetailContainer.innerHTML = '<p class="text-muted small mb-0">Selecione uma data do mês.</p>';
                return;
            }
            if (dayDetailTitle) {
                dayDetailTitle.textContent = `Atividades em ${info.date_br}`;
            }

            const campaigns = info.campaigns || [];
            const events = info.events || [];

            if (campaigns.length === 0 && events.length === 0) {
                dayDetailContainer.innerHTML = `
                    <div class="text-center py-4">
                        <i class="bi bi-calendar2-check fs-3 text-muted d-block mb-2"></i>
                        <p class="text-muted small mb-0">Nenhuma atividade sanitária prevista ou registrada nesta data.</p>
                    </div>
                `;
                return;
            }

            let html = '<div class="d-grid gap-2">';

            campaigns.forEach((c) => {
                html += `
                    <div class="p-3 rounded-3 border bg-light-subtle">
                        <div class="d-flex justify-content-between align-items-start gap-2 mb-1">
                            <span class="badge bg-success-subtle text-success-emphasis">
                                <i class="bi bi-megaphone-fill me-1"></i>Campanha Programada
                            </span>
                            <a href="/sanitario/cartelas/${encodeURIComponent(c.id)}" class="btn btn-sm btn-outline-agro py-0 px-2">
                                Abrir Cartela
                            </a>
                        </div>
                        <div class="fw-bold">${escapeHtml(c.name)}</div>
                        <div class="small text-muted">${escapeHtml(c.vaccine_name)} &bull; ${escapeHtml(c.property_name)} (${escapeHtml(c.lot_name)})</div>
                    </div>
                `;
            });

            events.forEach((ev) => {
                const animalLabel = `#${ev.ear_tag}${ev.animal_name ? " — " + ev.animal_name : ""}`;
                const applyBtn = ev.can_apply
                    ? `<button type="button"
                            class="btn btn-sm btn-agro js-open-apply-modal"
                            data-schedule-id="${escapeHtml(ev.id)}"
                            data-animal-id="${escapeHtml(ev.animal_id)}"
                            data-animal-label="${escapeHtml(animalLabel)}"
                            data-vaccine-id="${escapeHtml(ev.vaccine_id)}"
                            data-dose-number="${escapeHtml(String(ev.dose_number || 1))}"
                            data-manufacturer="${escapeHtml(ev.manufacturer || "")}"
                            data-route="${escapeHtml(ev.administration_route || "")}"
                            data-unit="${escapeHtml(ev.dosage_unit || "mL")}">
                            <i class="bi bi-check2-circle me-1"></i>Aplicar
                       </button>`
                    : "";

                html += `
                    <div class="p-3 rounded-3 border bg-white">
                        <div class="d-flex justify-content-between align-items-center gap-2 mb-1">
                            <span class="${escapeHtml(ev.status_badge_class)}">${escapeHtml(ev.status_label)}</span>
                            <span class="small text-muted">${escapeHtml(ev.age_category_name)}</span>
                        </div>
                        <div class="fw-bold text-dark">
                            <a href="/animal/${encodeURIComponent(ev.qr_code_token)}" class="text-decoration-none text-dark">
                                ${escapeHtml(animalLabel)}
                            </a>
                        </div>
                        <div class="small text-muted mb-2">
                            ${escapeHtml(ev.vaccine_name)} (${escapeHtml(String(ev.dose_number))}ª dose) &bull; ${escapeHtml(ev.lot_name)}
                        </div>
                        <div class="d-flex flex-wrap gap-2">
                            ${applyBtn}
                            <a href="/animal/${encodeURIComponent(ev.qr_code_token)}" class="btn btn-sm btn-outline-secondary">
                                Carteira
                            </a>
                        </div>
                    </div>
                `;
            });

            html += "</div>";
            dayDetailContainer.innerHTML = html;
        };

        document.querySelectorAll(".calendar-day-cell[data-in-month='1']").forEach((cell) => {
            cell.addEventListener("click", () => {
                renderDay(cell.getAttribute("data-date"));
            });
        });

        const todayCell = document.querySelector(".calendar-day-cell.is-today[data-in-month='1']");
        const firstBusyCell = document.querySelector(".calendar-day-cell[data-in-month='1'][data-has-items='1']");
        const initialCell = todayCell || firstBusyCell || document.querySelector(".calendar-day-cell[data-in-month='1']");
        if (initialCell) {
            renderDay(initialCell.getAttribute("data-date"));
        }
    }

    // -------------------------------------------------------------------------
    // 6. Formulário de Nova Campanha — Seleção por Lote ou Seleção Manual
    // -------------------------------------------------------------------------
    const campaignForm = document.getElementById("campaignCreateForm");
    if (campaignForm) {
        const campPropSelect = document.getElementById("camp_property_id");
        const campLotSelect = document.getElementById("camp_lot_id");
        const campVacSelect = document.getElementById("camp_vaccine_id");
        const modeRadios = campaignForm.querySelectorAll('input[name="selection_mode"]');
        const lotBlock = document.getElementById("lotSelectionBlock");
        const manualSearchBlock = document.getElementById("manualSearchBlock");
        const manualSearchInput = document.getElementById("manualAnimalSearch");
        const animalsContainer = document.getElementById("campaignAnimalsList");
        const countBadge = document.getElementById("selectedAnimalsCountBadge");
        const selectAllBtn = document.getElementById("selectAllCampaignAnimalsBtn");

        let loadedPropertyAnimals = [];
        let manuallyCheckedIds = new Set();

        const getMode = () => {
            const checked = campaignForm.querySelector('input[name="selection_mode"]:checked');
            return checked ? checked.value : "lote";
        };

        const updateCount = () => {
            const checkedCount = animalsContainer.querySelectorAll('input[name="animal_ids"]:checked').length;
            if (countBadge) countBadge.textContent = `${checkedCount} selecionado(s)`;
        };

        const renderAnimalsList = () => {
            const mode = getMode();
            const selectedLotId = campLotSelect ? campLotSelect.value : "";
            const term = (manualSearchInput ? manualSearchInput.value : "").trim().toLowerCase();
            const vacOpt = campVacSelect ? campVacSelect.options[campVacSelect.selectedIndex] : null;
            const targetSp = vacOpt ? (vacOpt.getAttribute("data-target-species") || "todas") : "todas";

            let filtered = loadedPropertyAnimals;
            if (targetSp && targetSp !== "todas") {
                filtered = filtered.filter((a) => !a.species || a.species === targetSp);
            }
            if (mode === "lote") {
                if (!selectedLotId) {
                    animalsContainer.innerHTML = '<div class="text-muted small py-3 text-center">Selecione um lote acima para listar automaticamente seus animais ativos compatíveis.</div>';
                    updateCount();
                    return;
                }
                filtered = filtered.filter((a) => a.lot_id === selectedLotId);
            } else if (term) {
                filtered = filtered.filter((a) =>
                    `${a.ear_tag} ${a.name} ${a.breed} ${a.species_label || ""} ${a.housing_display || ""}`.toLowerCase().includes(term)
                );
            }

            if (filtered.length === 0) {
                animalsContainer.innerHTML = '<div class="text-muted small py-3 text-center">Nenhum animal ativo encontrado para este critério nesta propriedade.</div>';
                updateCount();
                return;
            }

            animalsContainer.innerHTML = filtered
                .map((a) => {
                    const isChecked = mode === "lote" ? true : manuallyCheckedIds.has(a.id);
                    const labelName = a.name ? ` — ${escapeHtml(a.name)}` : "";
                    return `
                        <label class="d-flex align-items-center justify-content-between gap-2 p-2 px-3 border rounded-3 bg-white cursor-pointer">
                            <div class="d-flex align-items-center gap-2">
                                <input class="form-check-input mt-0 js-camp-animal-chk" type="checkbox" name="animal_ids" value="${escapeHtml(a.id)}" ${isChecked ? "checked" : ""}>
                                <div>
                                    <span class="fw-bold text-dark">#${escapeHtml(a.ear_tag)}${labelName}</span>
                                    <div class="small text-muted">${escapeHtml(a.species_label || "Bovino")} &bull; ${escapeHtml(a.breed)} &bull; ${escapeHtml(a.age_category_name)} (${escapeHtml(a.age_label)})</div>
                                </div>
                            </div>
                            <span class="badge bg-light text-dark border">${escapeHtml(a.lot_name)}</span>
                        </label>
                    `;
                })
                .join("");

            animalsContainer.querySelectorAll(".js-camp-animal-chk").forEach((chk) => {
                chk.addEventListener("change", () => {
                    if (chk.checked) manuallyCheckedIds.add(chk.value);
                    else manuallyCheckedIds.delete(chk.value);
                    updateCount();
                });
            });
            updateCount();
        };

        const loadPropertyData = async () => {
            const propId = campPropSelect.value;
            if (!propId) return;
            animalsContainer.innerHTML = '<div class="text-muted small py-3 text-center">Carregando animais da propriedade...</div>';
            try {
                const resp = await fetch(`/sanitario/api/propriedades/${encodeURIComponent(propId)}/animais`);
                const data = await resp.json();
                loadedPropertyAnimals = data.animals || [];
                manuallyCheckedIds.clear();

                if (campLotSelect) {
                    const prevLot = campLotSelect.value;
                    campLotSelect.innerHTML = '<option value="">Selecione um lote...</option>' +
                        (data.lots || []).map((l) => `<option value="${escapeHtml(l.id)}">${escapeHtml(l.name)}</option>`).join("");
                    if ((data.lots || []).some((l) => l.id === prevLot)) {
                        campLotSelect.value = prevLot;
                    } else if (data.lots && data.lots.length === 1) {
                        campLotSelect.value = data.lots[0].id;
                    }
                }
                renderAnimalsList();
            } catch {
                animalsContainer.innerHTML = '<div class="text-danger small py-3 text-center">Falha ao consultar animais da propriedade.</div>';
            }
        };

        const syncModeUI = () => {
            const mode = getMode();
            if (lotBlock) lotBlock.classList.toggle("d-none", mode !== "lote");
            if (manualSearchBlock) manualSearchBlock.classList.toggle("d-none", mode !== "manual");
            renderAnimalsList();
        };

        modeRadios.forEach((r) => r.addEventListener("change", syncModeUI));
        if (campPropSelect) campPropSelect.addEventListener("change", loadPropertyData);
        if (campLotSelect) campLotSelect.addEventListener("change", renderAnimalsList);
        if (campVacSelect) campVacSelect.addEventListener("change", renderAnimalsList);
        if (manualSearchInput) manualSearchInput.addEventListener("input", renderAnimalsList);
        if (selectAllBtn) {
            selectAllBtn.addEventListener("click", () => {
                const boxes = animalsContainer.querySelectorAll(".js-camp-animal-chk");
                const allChecked = Array.from(boxes).every((b) => b.checked);
                boxes.forEach((b) => {
                    b.checked = !allChecked;
                    if (b.checked) manuallyCheckedIds.add(b.value);
                    else manuallyCheckedIds.delete(b.value);
                });
                updateCount();
            });
        }

        syncModeUI();
        loadPropertyData();
    }
});
