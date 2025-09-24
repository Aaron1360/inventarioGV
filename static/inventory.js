import { showScraperNotification, hideScraperNotification } from './scraperNotification.js';
import { renderInventoryTabs } from './tables.js';

const COOLDOWN_SECONDS = 60;
let cooldownTimer = null;

export function setupInventory() {
    const reloadBtn = document.getElementById('reloadBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    const clearCacheBtn = document.getElementById('clearCacheBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const tableContainer = document.getElementById('tableContainer');
    const preTableMessage = document.getElementById('preTableMessage');
    if (!reloadBtn) return;

    function startCooldown() {
        let remaining = COOLDOWN_SECONDS;
        reloadBtn.disabled = true;
        if (logoutBtn) logoutBtn.disabled = true;
        reloadBtn.textContent = `Actualizar (${remaining}s)`;
        cooldownTimer = setInterval(() => {
            remaining--;
            if (remaining > 0) {
                reloadBtn.textContent = `Actualizar (${remaining}s)`;
            } else {
                clearInterval(cooldownTimer);
                reloadBtn.textContent = 'Actualizar';
                reloadBtn.disabled = false;
                if (logoutBtn) logoutBtn.disabled = false;
            }
        }, 1000);
    }

    reloadBtn.addEventListener('click', async function() {
        const storeSelect = document.getElementById('storeSelect');
        const statusMessage = document.getElementById('statusMessage');
        if (!storeSelect.value) {
            statusMessage.textContent = 'Selecciona una sucursal.';
            return;
        }
        statusMessage.textContent = 'Cargando inventario...';
        showScraperNotification();
        // Disable buttons while scraping
        reloadBtn.disabled = true;
        downloadBtn.disabled = true;
        if (clearCacheBtn) clearCacheBtn.disabled = true;
        if (logoutBtn) logoutBtn.disabled = true;
        try {
            const res = await fetch(`/scrape?store_name=${encodeURIComponent(storeSelect.value)}`);
            if (res.status === 429) {
                const data = await res.json();
                statusMessage.textContent = data.error || 'Debes esperar antes de volver a actualizar.';
                // Start cooldown with remaining seconds if provided
                const match = /([0-9]+)\s*segundos/.exec(data.error);
                let seconds = COOLDOWN_SECONDS;
                if (match) seconds = parseInt(match[1]);
                let remaining = seconds;
                reloadBtn.disabled = true;
                if (logoutBtn) logoutBtn.disabled = true;
                reloadBtn.textContent = `Actualizar (${remaining}s)`;
                if (cooldownTimer) clearInterval(cooldownTimer);
                cooldownTimer = setInterval(() => {
                    remaining--;
                    if (remaining > 0) {
                        reloadBtn.textContent = `Actualizar (${remaining}s)`;
                    } else {
                        clearInterval(cooldownTimer);
                        reloadBtn.textContent = 'Actualizar';
                        reloadBtn.disabled = false;
                        if (logoutBtn) logoutBtn.disabled = false;
                    }
                }, 1000);
                hideScraperNotification();
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
                startCooldown();
            } else {
                if (preTableMessage) preTableMessage.classList.remove('d-none');
                if (tableContainer) tableContainer.classList.add('d-none');
                downloadBtn.disabled = true;
                if (clearCacheBtn) clearCacheBtn.disabled = true;
                statusMessage.textContent = 'No se encontraron datos.';
            }
        } catch (err) {
            if (preTableMessage) preTableMessage.classList.remove('d-none');
            if (tableContainer) tableContainer.classList.add('d-none');
            downloadBtn.disabled = true;
            if (clearCacheBtn) clearCacheBtn.disabled = true;
            statusMessage.textContent = 'Error al cargar inventario.';
        }
        // Do not re-enable logoutBtn here; only enable after cooldown ends
        if (!cooldownTimer) reloadBtn.disabled = false;
        hideScraperNotification();
    });

    // Borrar/Clear cache functionality
    if (clearCacheBtn) {
        clearCacheBtn.addEventListener('click', async function() {
            const statusMessage = document.getElementById('statusMessage');
            statusMessage.textContent = 'Borrando datos en caché...';
            showScraperNotification();
            clearCacheBtn.disabled = true;
            reloadBtn.disabled = true;
            downloadBtn.disabled = true;
            if (logoutBtn) logoutBtn.disabled = true;
            try {
                const res = await fetch('/clear_cache', { method: 'POST' });
                const result = await res.json();
                if (result.success) {
                    if (preTableMessage) preTableMessage.classList.remove('d-none');
                    if (tableContainer) tableContainer.classList.add('d-none');
                    downloadBtn.disabled = true;
                    statusMessage.textContent = 'Inventario anterior borrado.';
                } else {
                    statusMessage.textContent = result.message || 'No se pudo borrar el caché.';
                }
            } catch (err) {
                statusMessage.textContent = 'Error al borrar el caché.';
            }
            reloadBtn.disabled = false;
            if (logoutBtn) logoutBtn.disabled = false;
            hideScraperNotification();
        });
    }

    // Save/download Excel functionality
    if (downloadBtn) {
        downloadBtn.addEventListener('click', async function() {
            const statusMessage = document.getElementById('statusMessage');
            statusMessage.textContent = 'Preparando archivo para descargar...';
            showScraperNotification();
            // Disable buttons while downloading
            reloadBtn.disabled = true;
            downloadBtn.disabled = true;
            if (clearCacheBtn) clearCacheBtn.disabled = true;
            if (logoutBtn) logoutBtn.disabled = true;
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
            // Re-enable buttons
            reloadBtn.disabled = false;
            downloadBtn.disabled = false;
            if (clearCacheBtn) clearCacheBtn.disabled = false;
            if (logoutBtn) logoutBtn.disabled = false;
            hideScraperNotification();
        });
    }
}
