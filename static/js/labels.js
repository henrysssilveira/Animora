/**
 * Animora — Módulo de Impressão em Lote de Etiquetas QR Code
 * Configurador interativo em milímetros, sincronização sequencial e pré-visualização proporcional.
 */
document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------------------
    // 1. Vínculo rápido de Etiqueta Pré-Impressa no Cadastro de Animal
    // -------------------------------------------------------------------------
    const tagUnitSelect = document.getElementById("tag_unit_id");
    const earTagInput = document.getElementById("ear_tag");
    if (tagUnitSelect && earTagInput) {
        const alwaysReadonly = earTagInput.hasAttribute("readonly") && tagUnitSelect.hasAttribute("required");
        tagUnitSelect.addEventListener("change", () => {
            const opt = tagUnitSelect.options[tagUnitSelect.selectedIndex];
            const tagNumber = opt ? opt.getAttribute("data-tag-number") : "";
            if (tagNumber) {
                earTagInput.value = tagNumber;
                earTagInput.readOnly = true;
                earTagInput.classList.add("bg-light");
            } else if (!alwaysReadonly) {
                earTagInput.readOnly = false;
                earTagInput.classList.remove("bg-light");
            }
        });
        if (tagUnitSelect.value) {
            tagUnitSelect.dispatchEvent(new Event("change"));
        }
    }

    // -------------------------------------------------------------------------
    // 2. Editor de Layout & Pré-visualização de Folhas de Etiquetas
    // -------------------------------------------------------------------------
    const form = document.getElementById("labelConfiguratorForm");
    if (!form) return;

    const presetsEl = document.getElementById("labelPresetsJson");
    const formatsEl = document.getElementById("pageFormatsJson");
    const existingUnitsEl = document.getElementById("batchUnitsJson");

    const PRESETS = presetsEl ? JSON.parse(presetsEl.textContent) : {};
    const PAGE_FORMATS = formatsEl ? JSON.parse(formatsEl.textContent) : {};
    const EXISTING_UNITS = existingUnitsEl ? JSON.parse(existingUnitsEl.textContent) : null;

    const getField = (name) => form.elements.namedItem(name);

    const presetSelect = getField("preset");
    const pageFormatSelect = getField("page_format");
    const pageWidthInput = getField("page_width_mm");
    const pageHeightInput = getField("page_height_mm");

    const prefixInput = getField("prefix");
    const paddingInput = getField("padding_digits");
    const startInput = getField("start_number");
    const qtyInput = getField("quantity");
    const endInput = getField("end_number");
    const rangeModeInput = getField("range_mode");
    const customTextInput = getField("custom_text");
    const showBorderInput = getField("show_border");

    const seqSummaryEl = document.getElementById("sequenceRangeSummary");
    const sheetsSummaryEl = document.getElementById("sheetsCountSummary");
    const fitAlertEl = document.getElementById("liveLayoutFitAlert");
    const previewStageEl = document.getElementById("liveSheetsStage");

    const numVal = (el, fallback) => {
        if (!el) return fallback;
        const parsed = parseFloat(String(el.value).replace(",", "."));
        return Number.isFinite(parsed) ? parsed : fallback;
    };

    const intVal = (el, fallback) => {
        if (!el) return fallback;
        const parsed = parseInt(String(el.value), 10);
        return Number.isFinite(parsed) ? parsed : fallback;
    };

    const padNumber = (num, digits) => {
        const s = String(Math.max(0, num));
        return s.length >= digits ? s : "0".repeat(digits - s.length) + s;
    };

    // SVG compacto simulando um QR Code nítido para pré-visualização instantânea antes de salvar
    const buildSampleQrSvg = () => `
        <svg viewBox="0 0 29 29" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges" aria-hidden="true">
            <rect width="29" height="29" fill="#FFFFFF"/>
            <path fill="#111111" d="
                M2,2 h7 v7 h-7 z M3,3 v5 h5 v-5 z M4,4 h3 v3 h-3 z
                M20,2 h7 v7 h-7 z M21,3 v5 h5 v-5 z M22,4 h3 v3 h-3 z
                M2,20 h7 v7 h-7 z M3,21 v5 h5 v-5 z M4,22 h3 v3 h-3 z
                M11,2 h2 v1 h-2 z M15,2 h3 v2 h-3 z M11,5 h1 v3 h-1 z M13,4 h2 v2 h-2 z M16,6 h2 v2 h-2 z
                M2,11 h3 v2 h-3 z M7,11 h2 v2 h-2 z M11,10 h3 v2 h-3 z M15,11 h2 v3 h-2 z M19,11 h3 v1 h-3 z M24,11 h3 v2 h-3 z
                M4,14 h2 v2 h-2 z M8,14 h3 v2 h-3 z M13,14 h2 v2 h-2 z M18,14 h2 v3 h-2 z M22,14 h2 v2 h-2 z M25,15 h2 v2 h-2 z
                M2,17 h2 v2 h-2 z M6,17 h2 v1 h-2 z M10,17 h4 v2 h-4 z M16,18 h2 v2 h-2 z M20,18 h5 v5 h-5 z M21,19 v3 h3 v-3 z M22,20 h1 v1 h-1 z
                M11,21 h2 v2 h-2 z M14,21 h3 v1 h-3 z M11,24 h3 v3 h-3 z M16,23 h2 v4 h-2 z M26,21 h1 v5 h-1 z M21,25 h4 v2 h-4 z
            "/>
        </svg>
    `;

    const syncPageDimensionsLock = () => {
        if (!pageFormatSelect || !pageWidthInput || !pageHeightInput) return;
        const fmtKey = pageFormatSelect.value;
        if (fmtKey && fmtKey !== "custom" && PAGE_FORMATS[fmtKey]) {
            pageWidthInput.value = PAGE_FORMATS[fmtKey].width_mm;
            pageHeightInput.value = PAGE_FORMATS[fmtKey].height_mm;
            pageWidthInput.readOnly = true;
            pageHeightInput.readOnly = true;
            pageWidthInput.classList.add("bg-light");
            pageHeightInput.classList.add("bg-light");
        } else {
            pageWidthInput.readOnly = false;
            pageHeightInput.readOnly = false;
            pageWidthInput.classList.remove("bg-light");
            pageHeightInput.classList.remove("bg-light");
        }
    };

    const applyPresetValues = (presetKey) => {
        const p = PRESETS[presetKey];
        if (!p || presetKey === "custom") return;
        const keys = [
            "page_format",
            "page_width_mm",
            "page_height_mm",
            "label_width_mm",
            "label_height_mm",
            "gap_x_mm",
            "gap_y_mm",
            "margin_top_mm",
            "margin_right_mm",
            "margin_bottom_mm",
            "margin_left_mm",
            "columns",
            "rows",
            "qr_size_mm",
            "font_size_pt",
        ];
        keys.forEach((k) => {
            const field = getField(k);
            if (field && p[k] !== undefined) {
                field.value = p[k];
            }
        });
        if (showBorderInput && p.show_border !== undefined) {
            showBorderInput.checked = Boolean(p.show_border);
        }
        syncPageDimensionsLock();
    };

    // Sincronização bidirecional entre Quantidade e Numeração Final
    const syncSequenceByQuantity = () => {
        if (!startInput || !qtyInput || !endInput) return;
        const start = Math.max(0, intVal(startInput, 1));
        const qty = Math.max(1, Math.min(500, intVal(qtyInput, 24)));
        endInput.value = start + qty - 1;
        if (rangeModeInput) rangeModeInput.value = "quantity";
    };

    const syncSequenceByEndNumber = () => {
        if (!startInput || !qtyInput || !endInput) return;
        const start = Math.max(0, intVal(startInput, 1));
        const end = Math.max(start, intVal(endInput, start));
        const qty = Math.min(500, end - start + 1);
        qtyInput.value = qty;
        endInput.value = start + qty - 1;
        if (rangeModeInput) rangeModeInput.value = "range";
    };

    const buildCurrentUnitsForPreview = () => {
        const customText = customTextInput ? customTextInput.value.trim() : "";
        if (Array.isArray(EXISTING_UNITS)) {
            return EXISTING_UNITS.map((u) => ({
                tag_number: u.tag_number,
                qr_url: u.qr_image_url,
                custom_text: customText,
            }));
        }

        const prefix = (prefixInput ? prefixInput.value : "AN-").trim().toUpperCase();
        const digits = Math.max(1, Math.min(10, intVal(paddingInput, 5)));
        const start = Math.max(0, intVal(startInput, 1));
        const qty = Math.max(1, Math.min(500, intVal(qtyInput, 24)));

        const items = [];
        for (let i = 0; i < qty; i += 1) {
            items.push({
                tag_number: `${prefix}${padNumber(start + i, digits)}`,
                qr_url: null,
                custom_text: customText,
            });
        }
        return items;
    };

    const renderLivePreview = () => {
        if (!previewStageEl) return;

        const pageW = Math.max(30, numVal(pageWidthInput, 210));
        const pageH = Math.max(25, numVal(pageHeightInput, 297));
        const labelW = Math.max(10, numVal(getField("label_width_mm"), 63.5));
        const labelH = Math.max(10, numVal(getField("label_height_mm"), 33.9));
        const gapX = Math.max(0, numVal(getField("gap_x_mm"), 2.5));
        const gapY = Math.max(0, numVal(getField("gap_y_mm"), 0));
        const marginTop = Math.max(0, numVal(getField("margin_top_mm"), 12.9));
        const marginRight = Math.max(0, numVal(getField("margin_right_mm"), 7.2));
        const marginBottom = Math.max(0, numVal(getField("margin_bottom_mm"), 12.9));
        const marginLeft = Math.max(0, numVal(getField("margin_left_mm"), 7.2));
        const cols = Math.max(1, Math.min(12, intVal(getField("columns"), 3)));
        const rows = Math.max(1, Math.min(30, intVal(getField("rows"), 8)));
        const qrSize = Math.max(8, numVal(getField("qr_size_mm"), 23));
        const fontSizePt = Math.max(6, numVal(getField("font_size_pt"), 11.5));
        const showBorder = showBorderInput ? showBorderInput.checked : true;

        const units = buildCurrentUnitsForPreview();
        const perPage = cols * rows;
        const totalPages = Math.max(1, Math.ceil(units.length / perPage));

        if (seqSummaryEl && units.length > 0) {
            seqSummaryEl.textContent = `${units[0].tag_number} até ${units[units.length - 1].tag_number} (${units.length} etiqueta${units.length === 1 ? "" : "s"})`;
        }
        if (sheetsSummaryEl) {
            sheetsSummaryEl.textContent = `${perPage}/folha • ${totalPages} folha${totalPages === 1 ? "" : "s"}`;
        }

        // Validações geométricas em tempo real
        const warnings = [];
        const usedW = marginLeft + cols * labelW + (cols - 1) * gapX + marginRight;
        const usedH = marginTop + rows * labelH + (rows - 1) * gapY + marginBottom;

        if (usedW > pageW + 0.6) {
            warnings.push(
                `Largura excedida: margens + ${cols} coluna(s) + espaçamentos ocupam ${usedW.toFixed(1)} mm em uma folha de ${pageW.toFixed(1)} mm.`
            );
        }
        if (usedH > pageH + 0.6) {
            warnings.push(
                `Altura excedida: margens + ${rows} linha(s) + espaçamentos ocupam ${usedH.toFixed(1)} mm em uma folha de ${pageH.toFixed(1)} mm.`
            );
        }
        if (qrSize < 12) {
            warnings.push("O QR Code está menor que 12 mm; aumente-o para garantir leitura rápida por câmeras de celular.");
        }

        const isHorizontal = labelW >= labelH * 1.18;
        const maxQrAllowed = isHorizontal
            ? Math.min(labelW * 0.56, labelH - 3.0)
            : Math.min(labelW - 4.0, labelH * 0.62);

        if (qrSize > maxQrAllowed + 0.5) {
            warnings.push(
                `O QR Code (${qrSize.toFixed(1)} mm) ultrapassa o espaço seguro da etiqueta (${maxQrAllowed.toFixed(1)} mm máx.).`
            );
        }

        if (fitAlertEl) {
            if (warnings.length > 0) {
                fitAlertEl.className = "alert alert-danger rounded-3 py-2 px-3 small mb-3";
                fitAlertEl.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> <strong>Ajuste necessário antes de imprimir:</strong> ${warnings.join(" ")}`;
            } else {
                const freeW = Math.max(0, pageW - usedW).toFixed(1);
                const freeH = Math.max(0, pageH - usedH).toFixed(1);
                fitAlertEl.className = "alert alert-success rounded-3 py-2 px-3 small mb-3";
                fitAlertEl.innerHTML = `<i class="bi bi-rulers me-1"></i> <strong>Encaixe validado em milímetros:</strong> grade ${cols}×${rows} (${perPage} por folha) sem cortes nem sobreposições. Folga restante: ${freeW} mm (H) / ${freeH} mm (V).`;
            }
        }

        // Escala proporcional em pixels para caber confortavelmente na tela mantendo proporção exata em mm
        const maxPreviewWidthPx = Math.min(580, Math.max(300, previewStageEl.clientWidth - 40));
        const pxPerMm = Math.min(maxPreviewWidthPx / pageW, 3.4);
        const ptToPx = (pt) => pt * 0.3528 * pxPerMm;

        const sampleSvg = buildSampleQrSvg();
        const maxRenderedPages = Math.min(totalPages, 25); // Exibe até 25 folhas empilhadas no navegador
        const htmlPages = [];

        for (let pIdx = 0; pIdx < maxRenderedPages; pIdx += 1) {
            const pageUnits = units.slice(pIdx * perPage, (pIdx + 1) * perPage);
            const slotsHtml = [];

            for (let slot = 0; slot < perPage; slot += 1) {
                const item = pageUnits[slot];
                const cardW = (labelW * pxPerMm).toFixed(2);
                const cardH = (labelH * pxPerMm).toFixed(2);

                if (!item) {
                    slotsHtml.push(
                        `<div class="label-preview-empty-slot" style="width:${cardW}px;height:${cardH}px;" title="Espaço vazio na folha"></div>`
                    );
                    continue;
                }

                const qrPx = Math.min(qrSize, Math.max(8, maxQrAllowed)) * pxPerMm;
                const padPx = Math.max(2, 1.8 * pxPerMm);
                const brandFontPx = Math.max(6.5, Math.min(ptToPx(fontSizePt * 0.62), 13));
                const numFontPx = Math.max(7.5, ptToPx(fontSizePt));
                const customFontPx = Math.max(6, ptToPx(fontSizePt * 0.66));

                const qrContent = item.qr_url
                    ? `<img src="${item.qr_url}" alt="QR ${item.tag_number}" loading="lazy">`
                    : sampleSvg;

                const customLine = item.custom_text
                    ? `<div class="label-preview-custom" style="font-size:${customFontPx.toFixed(1)}px;">${escapeHtml(item.custom_text)}</div>`
                    : "";

                slotsHtml.push(`
                    <div class="label-preview-card ${isHorizontal ? "layout-horizontal" : "layout-vertical"} ${showBorder ? "with-cut-border" : ""}"
                         style="width:${cardW}px;height:${cardH}px;padding:${padPx.toFixed(1)}px;gap:${(padPx * 0.85).toFixed(1)}px;">
                        <div class="label-preview-qr" style="width:${qrPx.toFixed(1)}px;height:${qrPx.toFixed(1)}px;">
                            ${qrContent}
                        </div>
                        <div class="label-preview-meta">
                            <div class="label-preview-brand" style="font-size:${brandFontPx.toFixed(1)}px;">ANIMORA</div>
                            <div class="label-preview-number" style="font-size:${numFontPx.toFixed(1)}px;">${escapeHtml(item.tag_number)}</div>
                            ${customLine}
                        </div>
                    </div>
                `);
            }

            htmlPages.push(`
                <div class="mb-3 text-center">
                    <div class="badge bg-dark bg-opacity-75 text-white mb-2 fw-semibold">
                        Folha ${pIdx + 1} de ${totalPages} &bull; ${pageW} × ${pageH} mm
                    </div>
                    <div class="label-sheet-paper mx-auto"
                         style="width:${(pageW * pxPerMm).toFixed(2)}px;
                                min-height:${(pageH * pxPerMm).toFixed(2)}px;
                                padding:${(marginTop * pxPerMm).toFixed(2)}px ${(marginRight * pxPerMm).toFixed(2)}px ${(marginBottom * pxPerMm).toFixed(2)}px ${(marginLeft * pxPerMm).toFixed(2)}px;">
                        <div class="label-sheet-grid"
                             style="grid-template-columns:repeat(${cols}, ${(labelW * pxPerMm).toFixed(2)}px);
                                    grid-auto-rows:${(labelH * pxPerMm).toFixed(2)}px;
                                    column-gap:${(gapX * pxPerMm).toFixed(2)}px;
                                    row-gap:${(gapY * pxPerMm).toFixed(2)}px;">
                            ${slotsHtml.join("")}
                        </div>
                    </div>
                </div>
            `);
        }

        previewStageEl.innerHTML = htmlPages.join("");
    };

    const escapeHtml = (str) =>
        String(str || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");

    // Eventos de controles
    if (presetSelect) {
        presetSelect.addEventListener("change", () => {
            applyPresetValues(presetSelect.value);
            renderLivePreview();
        });
    }

    if (pageFormatSelect) {
        pageFormatSelect.addEventListener("change", () => {
            syncPageDimensionsLock();
            if (presetSelect) presetSelect.value = "custom";
            renderLivePreview();
        });
    }

    const manualLayoutFields = [
        "page_width_mm",
        "page_height_mm",
        "label_width_mm",
        "label_height_mm",
        "gap_x_mm",
        "gap_y_mm",
        "margin_top_mm",
        "margin_right_mm",
        "margin_bottom_mm",
        "margin_left_mm",
        "columns",
        "rows",
        "qr_size_mm",
        "font_size_pt",
    ];
    manualLayoutFields.forEach((name) => {
        const el = getField(name);
        if (el) {
            el.addEventListener("input", () => {
                if (presetSelect) presetSelect.value = "custom";
                renderLivePreview();
            });
        }
    });

    if (showBorderInput) {
        showBorderInput.addEventListener("change", renderLivePreview);
    }
    if (customTextInput) {
        customTextInput.addEventListener("input", renderLivePreview);
    }
    if (prefixInput) {
        prefixInput.addEventListener("input", renderLivePreview);
    }
    if (paddingInput) {
        paddingInput.addEventListener("input", renderLivePreview);
    }
    if (startInput) {
        startInput.addEventListener("input", () => {
            syncSequenceByQuantity();
            renderLivePreview();
        });
    }
    if (qtyInput) {
        qtyInput.addEventListener("input", () => {
            syncSequenceByQuantity();
            renderLivePreview();
        });
    }
    if (endInput) {
        endInput.addEventListener("input", () => {
            syncSequenceByEndNumber();
            renderLivePreview();
        });
    }

    // Botão rápido "Preencher 1 Folha Completa"
    const fillOneSheetBtn = document.getElementById("fillSingleSheetQtyBtn");
    if (fillOneSheetBtn && qtyInput) {
        fillOneSheetBtn.addEventListener("click", () => {
            const cols = Math.max(1, intVal(getField("columns"), 3));
            const rows = Math.max(1, intVal(getField("rows"), 8));
            qtyInput.value = cols * rows;
            syncSequenceByQuantity();
            renderLivePreview();
        });
    }

    syncPageDimensionsLock();
    renderLivePreview();
    window.addEventListener("resize", renderLivePreview);
});
