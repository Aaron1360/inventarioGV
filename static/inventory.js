import { showScraperNotification, hideScraperNotification } from './scraperNotification.js';
import { renderInventoryTabs } from './tables.js';

export function setupInventory() {
    const reloadBtn = document.getElementById('reloadBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const tableContainer = document.getElementById('tableContainer');
    const preTableMessage = document.getElementById('preTableMessage');
    if (!reloadBtn) return;
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
        if (logoutBtn) logoutBtn.disabled = true;
        try {
            const res = await fetch(`/scrape?store_name=${encodeURIComponent(storeSelect.value)}`);
            const rawData = await res.json();
            if (rawData && rawData.wholesale && Array.isArray(rawData.wholesale) && rawData.wholesale.length > 0) {
                if (preTableMessage) preTableMessage.classList.add('d-none');
                if (tableContainer) tableContainer.classList.remove('d-none');
                renderInventoryTabs(tableContainer, rawData.wholesale, rawData.retail, rawData.prices);
                downloadBtn.disabled = false;
                statusMessage.textContent = '';
            } else {
                if (preTableMessage) preTableMessage.classList.remove('d-none');
                if (tableContainer) tableContainer.classList.add('d-none');
                downloadBtn.disabled = true;
                statusMessage.textContent = 'No se encontraron datos.';
            }
        } catch (err) {
            if (preTableMessage) preTableMessage.classList.remove('d-none');
            if (tableContainer) tableContainer.classList.add('d-none');
            downloadBtn.disabled = true;
            statusMessage.textContent = 'Error al cargar inventario.';
        }
        // Re-enable buttons
        reloadBtn.disabled = false;
        if (logoutBtn) logoutBtn.disabled = false;
        hideScraperNotification();
    });

    // Save/download Excel functionality
    if (downloadBtn) {
        downloadBtn.addEventListener('click', async function() {
            const statusMessage = document.getElementById('statusMessage');
            statusMessage.textContent = 'Preparando archivo para descargar...';
            showScraperNotification();
            // Disable buttons while downloading
            reloadBtn.disabled = true;
            downloadBtn.disabled = true;
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
            if (logoutBtn) logoutBtn.disabled = false;
            hideScraperNotification();
        });
    }
}
