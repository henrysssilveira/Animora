document.addEventListener("DOMContentLoaded", () => {
    // Filtro rápido de busca na listagem do Rebanho
    const searchInput = document.getElementById("herdSearchInput");
    if (searchInput) {
        const rows = document.querySelectorAll(".herd-item-row");
        const emptySearchFeedback = document.getElementById("emptySearchFeedback");

        searchInput.addEventListener("input", () => {
            const term = searchInput.value.trim().toLowerCase();
            let visibleCount = 0;

            rows.forEach((row) => {
                const searchable = (row.getAttribute("data-search") || "").toLowerCase();
                const matches = !term || searchable.includes(term);
                row.style.display = matches ? "" : "none";
                if (matches) visibleCount += 1;
            });

            if (emptySearchFeedback) {
                emptySearchFeedback.classList.toggle("d-none", visibleCount > 0);
            }
        });
    }

    // Botão para copiar o link público de identificação do animal
    const copyBtn = document.getElementById("copyPublicUrlBtn");
    if (copyBtn) {
        copyBtn.addEventListener("click", async () => {
            const url = copyBtn.getAttribute("data-url");
            if (!url) return;

            try {
                await navigator.clipboard.writeText(url);
                const originalHtml = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="bi bi-check2 me-1"></i> Link copiado!';
                setTimeout(() => {
                    copyBtn.innerHTML = originalHtml;
                }, 2000);
            } catch {
                window.prompt("Copie a URL pública do animal:", url);
            }
        });
    }

    // Botão para imprimir exclusivamente o QR Code de identificação
    const printQrBtn = document.getElementById("printQrBtn");
    if (printQrBtn) {
        printQrBtn.addEventListener("click", () => {
            window.print();
        });
    }
});
