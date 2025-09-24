import { showScraperNotification, hideScraperNotification } from './scraperNotification.js';
import { renderInventoryTabs } from './tables.js';

let cooldownTimer = null;
let lastScrapedStoreName = '';

async function syncCooldownUI(reloadBtn, logoutBtn) {
    if (!reloadBtn) return;
    const storeSelect = document.getElementById('storeSelect');
    // Cancel any running timer
    if (cooldownTimer) {
        clearInterval(cooldownTimer);
        cooldownTimer = null;
    }
    try {
        const res = await fetch('/cooldown_status');
        const data = await res.json();
        let remaining = data.cooldown || 0;
        if (remaining > 0) {
            reloadBtn.disabled = true;
            if (logoutBtn) logoutBtn.disabled = true;
            if (storeSelect) storeSelect.disabled = true;
            reloadBtn.innerHTML = `<i class="bi bi-arrow-clockwise me-1"></i>Actualizar (${remaining}s)`;
            cooldownTimer = setInterval(() => {
                remaining--;
                if (remaining > 0) {
                    reloadBtn.innerHTML = `<i class="bi bi-arrow-clockwise me-1"></i>Actualizar (${remaining}s)`;
                } else {
                    clearInterval(cooldownTimer);
                    cooldownTimer = null;
                    reloadBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Actualizar';
                    reloadBtn.disabled = false;
                    if (logoutBtn) logoutBtn.disabled = false;
                    if (storeSelect) storeSelect.disabled = false;
                }
            }, 1000);
        } else {
            reloadBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Actualizar';
            reloadBtn.disabled = false;
            if (logoutBtn) logoutBtn.disabled = false;
            if (storeSelect) storeSelect.disabled = false;
        }
    } catch {
        reloadBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Actualizar';
        reloadBtn.disabled = false;
        if (logoutBtn) logoutBtn.disabled = false;
        if (storeSelect) storeSelect.disabled = false;
    }
}

export function setupInventory() {
    const reloadBtn = document.getElementById('reloadBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    const clearCacheBtn = document.getElementById('clearCacheBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const tableContainer = document.getElementById('tableContainer');
    const preTableMessage = document.getElementById('preTableMessage');
    const storeTitle = document.getElementById('storeTitle');
    if (!reloadBtn) return;

    // Do NOT sync cooldown on page load
    // syncCooldownUI(reloadBtn, logoutBtn); // <-- Remove or comment out this line

    reloadBtn.addEventListener('click', async function() {
        const storeSelect = document.getElementById('storeSelect');
        const statusMessage = document.getElementById('statusMessage');
        if (!storeSelect.value) {
            statusMessage.textContent = 'Selecciona una sucursal.';
            return;
        }
        statusMessage.textContent = 'Cargando inventario...';
        showScraperNotification();
        // Disable buttons and dropdown while scraping
        reloadBtn.disabled = true;
        downloadBtn.disabled = true;
        if (clearCacheBtn) clearCacheBtn.disabled = true;
        if (logoutBtn) logoutBtn.disabled = true;
        if (storeSelect) storeSelect.disabled = true;
        try {
            const res = await fetch(`/scrape?store_name=${encodeURIComponent(storeSelect.value)}`);
            if (res.status === 429) {
                const data = await res.json();
                statusMessage.textContent = data.error || 'Debes esperar antes de volver a actualizar.';
                await syncCooldownUI(reloadBtn, logoutBtn); // Only show cooldown after first use
                hideScraperNotification();
                if (storeTitle) {
                    storeTitle.classList.add('d-none');
                    storeTitle.textContent = '';
                }
                return;
            }
            const rawData = await res.json();
            if (rawData && rawData.wholesale && Array.isArray(rawData.wholesale) && rawData.wholesale.length > 0) {
                if (preTableMessage) preTableMessage.classList.add('d-none');
                if (tableContainer) tableContainer.classList.remove('d-none');
                renderInventoryTabs(tableContainer, rawData.wholesale, rawData.retail, rawData.prices);
                downloadBtn.disabled = false;
                if (clearCacheBtn) clearCacheBtn.disabled = false;
                statusMessage.textContent = '';
                lastScrapedStoreName = storeSelect && storeSelect.options[storeSelect.selectedIndex] ? storeSelect.options[storeSelect.selectedIndex].text : '';
                if (storeTitle) {
                    storeTitle.textContent = lastScrapedStoreName;
                    storeTitle.classList.remove('d-none');
                }
                await syncCooldownUI(reloadBtn, logoutBtn); // Only show cooldown after first use
            } else {
                if (preTableMessage) preTableMessage.classList.remove('d-none');
                if (tableContainer) tableContainer.classList.add('d-none');
                downloadBtn.disabled = true;
                if (clearCacheBtn) clearCacheBtn.disabled = true;
                statusMessage.textContent = 'No se encontraron datos.';
                if (storeTitle) {
                    storeTitle.classList.add('d-none');
                    storeTitle.textContent = '';
                }
            }
        } catch (err) {
            if (preTableMessage) preTableMessage.classList.remove('d-none');
            if (tableContainer) tableContainer.classList.add('d-none');
            downloadBtn.disabled = true;
            if (clearCacheBtn) clearCacheBtn.disabled = true;
            statusMessage.textContent = 'Error al cargar inventario.';
            if (storeTitle) {
                storeTitle.classList.add('d-none');
                storeTitle.textContent = '';
            }
        }
        // Do not re-enable storeSelect here; let syncCooldownUI handle it after cooldown ends
        hideScraperNotification();
    });

    // Borrar/Clear cache functionality
    if (clearCacheBtn) {
        // Bootstrap modal for confirmation
        const clearCacheModal = document.getElementById('clearCacheModal');
        const clearCacheModalBody = document.getElementById('clearCacheModalBody');
        const confirmClearCacheBtn = document.getElementById('confirmClearCacheBtn');
        let pendingClear = false;
        clearCacheBtn.addEventListener('click', function() {
            // Use lastScrapedStoreName instead of current dropdown
            clearCacheModalBody.textContent = `¿Estás seguro de que deseas borrar el inventario actual?`;
            pendingClear = true;
            const modal = new bootstrap.Modal(clearCacheModal);
            modal.show();
        });
        if (confirmClearCacheBtn) {
            confirmClearCacheBtn.addEventListener('click', async function() {
                if (!pendingClear) return;
                pendingClear = false;
                const statusMessage = document.getElementById('statusMessage');
                statusMessage.textContent = 'Borrando datos en caché...';
                showScraperNotification();
                clearCacheBtn.disabled = true;
                reloadBtn.disabled = true;
                downloadBtn.disabled = true;
                if (logoutBtn) logoutBtn.disabled = true;
                if (storeSelect) storeSelect.disabled = true;
                try {
                    const res = await fetch('/clear_cache', { method: 'POST' });
                    const result = await res.json();
                    if (result.success) {
                        if (preTableMessage) preTableMessage.classList.remove('d-none');
                        if (tableContainer) tableContainer.classList.add('d-none');
                        downloadBtn.disabled = true;
                        statusMessage.textContent = 'Inventario anterior borrado.';
                        if (storeTitle) {
                            storeTitle.classList.add('d-none');
                            storeTitle.textContent = '';
                        }
                    } else {
                        statusMessage.textContent = result.message || 'No se pudo borrar el caché.';
                    }
                } catch (err) {
                    statusMessage.textContent = 'Error al borrar el caché.';
                }
                await syncCooldownUI(reloadBtn, logoutBtn);
                // Do NOT re-enable storeSelect here; let syncCooldownUI handle it after cooldown ends
                // Hide modal after action
                const modal = bootstrap.Modal.getInstance(clearCacheModal);
                if (modal) modal.hide();
            });
        }
    }

    // Save/download Excel functionality
    if (downloadBtn) {
        downloadBtn.addEventListener('click', async function() {
            const statusMessage = document.getElementById('statusMessage');
            statusMessage.textContent = 'Preparando archivo para descargar...';
            showScraperNotification();
            // Disable buttons and dropdown while downloading
            reloadBtn.disabled = true;
            downloadBtn.disabled = true;
            if (clearCacheBtn) clearCacheBtn.disabled = true;
            if (logoutBtn) logoutBtn.disabled = true;
            if (storeSelect) storeSelect.disabled = true;
            try {
                const res = await fetch('/save');
                if (!res.ok) throw new Error('No se pudo descargar el archivo.');
                const disposition = res.headers.get('Content-Disposition');
                let filename = 'inventario.xlsx';
                if (disposition && disposition.includes('filename=')) {
                    filename = disposition.split('filename=')[1].replace(/"/g, '');
                }
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
                statusMessage.textContent = '';
            } catch (err) {
                statusMessage.textContent = 'Error al descargar el archivo.';
            }
            // Always re-enable downloadBtn so user can save again
            downloadBtn.disabled = false;
            await syncCooldownUI(reloadBtn, logoutBtn);
            if (clearCacheBtn) clearCacheBtn.disabled = false;
            // Do NOT re-enable storeSelect here; let syncCooldownUI handle it after cooldown ends
            hideScraperNotification();
        });
    }
}
