import { createTabs, renderPaginatedTable } from './table.js';
import { showScraperNotification, hideScraperNotification } from './scraperNotification.js';

export function setupInventory() {
    const reloadBtn = document.getElementById('reloadBtn');
    const downloadBtn = document.getElementById('downloadBtn');
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
        try {
            const res = await fetch(`/scrape?store_name=${encodeURIComponent(storeSelect.value)}`);
            const rawData = await res.json();
            if (rawData && rawData.wholesale && Array.isArray(rawData.wholesale) && rawData.wholesale.length > 0) {
                if (preTableMessage) preTableMessage.classList.add('d-none');
                if (tableContainer) tableContainer.classList.remove('d-none');
                createTabs(tableContainer);
                renderPaginatedTable(
                    rawData.wholesale,
                    [
                        { key: 'presentacion', header: 'Presentación' },
                        { key: '# cajas', header: '# Cajas' }
                    ],
                    'tabPanel-mayoreo', 1, 50
                );
                renderPaginatedTable(
                    rawData.retail,
                    [
                        { key: 'presentacion', header: 'Presentación' },
                        { key: '# piezas', header: '# Piezas' }
                    ],
                    'tabPanel-menudeo', 1, 50
                );
                renderPaginatedTable(
                    rawData.prices,
                    [
                        { key: 'presentacion', header: 'Presentación' },
                        { key: 'precio', header: 'Precio' }
                    ],
                    'tabPanel-precios', 1, 50
                );
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
        hideScraperNotification();
    });
}
