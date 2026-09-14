import { refreshStoreDropdown } from './store.js';

let inventoryData = [];
let statusTimer = null;
const ROWS_PER_PAGE = 20;
let scrapeStartedThisSession = sessionStorage.getItem('inventoryScrapeStarted') === 'true';
let rebuildPromptShown = false;
let lastLoggedScrapeStatus = null;
let statusRequestErrorLogged = false;

function displayBuiltAt(timestamp) {
    const element = document.getElementById('lastBuiltAt');
    if (!element || !timestamp) return;
    const date = new Date(timestamp);
    element.textContent = `Última actualización: ${date.toLocaleString()}`;
}

function setInventoryButtonsDisabled(disabled) {
    ['reloadBtn', 'downloadBtn'].forEach(id => {
        const button = document.getElementById(id);
        if (button) button.disabled = disabled;
    });
}

function showScrapingCard() {
    document.getElementById('scraperSpinner')?.classList.remove('d-none');
    const title = document.getElementById('preTableTitle');
    const text = document.getElementById('preTableText');
    if (title) title.textContent = 'Preparando inventario';
    if (text) text.textContent = 'Accediendo a https://grupogranvalle.com/sistema/';
    document.getElementById('preTableMessage')?.classList.remove('d-none');
}

function clearRenderedInventory() {
    inventoryData = [];
    document.getElementById('tableContainer')?.replaceChildren();
    document.getElementById('tableContainer')?.classList.add('d-none');
    document.getElementById('storeFilterSection')?.classList.add('d-none');
    document.getElementById('actionButtons')?.classList.add('d-none');
    const storeSelect = document.getElementById('storeSelect');
    const lineSelect = document.getElementById('lineSelect');
    const sublineSelect = document.getElementById('sublineSelect');
    if (storeSelect) storeSelect.replaceChildren(new Option('Cargando sucursales...', ''));
    if (lineSelect) lineSelect.replaceChildren(new Option('Todas las líneas', ''));
    if (sublineSelect) sublineSelect.replaceChildren(new Option('Todas las sublíneas', ''));
}

function renderInventory(rows, store) {
    const container = document.getElementById('tableContainer');
    if (!container) return;
    const line = document.getElementById('lineSelect')?.value || '';
    const subline = document.getElementById('sublineSelect')?.value || '';
    if (!store) {
        container.replaceChildren();
        container.classList.add('d-none');
        const spinner = document.getElementById('scraperSpinner');
        const title = document.getElementById('preTableTitle');
        const text = document.getElementById('preTableText');
        spinner?.classList.add('d-none');
        if (title) title.textContent = 'Selecciona una sucursal';
        if (text) text.textContent = 'Elige una sucursal para visualizar el inventario.';
        document.getElementById('preTableMessage')?.classList.remove('d-none');
        return;
    }
    const filtered = rows.filter(row =>
        row.TIENDA === store &&
        (!line || row.LINEA === line) &&
        (!subline || row.SUBLINEA === subline)
    );
    const views = [
        {
            id: 'mayoreo',
            label: 'MAYOREO',
            warehouse: 'MAYOREO',
            columns: ['PRODUCTO', 'CANTIDAD UNITARIA', 'CANT', 'N° CAJAS'],
        },
        {
            id: 'menudeo',
            label: 'MENUDEO',
            warehouse: 'MENUDEO',
            columns: ['PRODUCTO', 'CANTIDAD UNITARIA', 'IMPORTE'],
        },
        {
            id: 'precios',
            label: 'PRECIOS',
            warehouse: 'MAYOREO',
            columns: ['PRODUCTO', 'IMPORTE'],
        },
    ];
    const tabList = document.createElement('ul');
    tabList.className = 'nav nav-tabs mb-3';
    const tabContent = document.createElement('div');
    tabContent.className = 'tab-content';

    views.forEach((view, index) => {
        const tab = document.createElement('li');
        tab.className = 'nav-item';
        const button = document.createElement('button');
        button.className = `nav-link${index === 0 ? ' active' : ''}`;
        button.textContent = view.label;
        button.type = 'button';
        button.addEventListener('click', () => {
            tabList.querySelectorAll('.nav-link').forEach(item => item.classList.remove('active'));
            tabContent.querySelectorAll('.tab-pane').forEach(item => item.classList.remove('show', 'active'));
            button.classList.add('active');
            document.getElementById(`inventory-pane-${view.id}`)?.classList.add('show', 'active');
        });
        tab.appendChild(button);
        tabList.appendChild(tab);

        const pane = document.createElement('div');
        pane.id = `inventory-pane-${view.id}`;
        pane.className = `tab-pane fade${index === 0 ? ' show active' : ''}`;
        const sourceRows = view.warehouse
            ? filtered.filter(row => row.ALMACEN === view.warehouse)
            : filtered.filter(row => row.IMPORTE !== null && row.IMPORTE !== undefined && row.IMPORTE !== '');
        const uniqueRows = view.id === 'precios'
            ? sourceRows.filter((row, rowIndex, allRows) => allRows.findIndex(item => item.PRODUCTO === row.PRODUCTO) === rowIndex)
            : sourceRows;
        pane.appendChild(buildPaginatedTable(uniqueRows, view.columns));
        tabContent.appendChild(pane);
    });

    container.replaceChildren(tabList, tabContent);
    container.classList.remove('d-none');
    document.getElementById('preTableMessage')?.classList.add('d-none');
}

function setFilterOptions(selectId, label, values) {
    const select = document.getElementById(selectId);
    if (!select) return;
    select.replaceChildren(new Option(label, ''));
    [...values].sort().forEach(value => select.add(new Option(value, value)));
}

function updateHierarchyFilters() {
    const store = document.getElementById('storeSelect')?.value || '';
    const lineSelect = document.getElementById('lineSelect');
    const sublineSelect = document.getElementById('sublineSelect');
    const storeRows = inventoryData.filter(row => row.TIENDA === store);
    const selectedLine = lineSelect?.value || '';
    const lines = [...new Set(storeRows.map(row => row.LINEA).filter(Boolean))];
    setFilterOptions('lineSelect', 'Todas las líneas', lines);
    if (lineSelect && lines.includes(selectedLine)) lineSelect.value = selectedLine;
    const lineRows = storeRows.filter(row => !lineSelect?.value || row.LINEA === lineSelect.value);
    const selectedSubline = sublineSelect?.value || '';
    const sublines = [...new Set(lineRows.map(row => row.SUBLINEA).filter(Boolean))];
    setFilterOptions('sublineSelect', 'Todas las sublíneas', sublines);
    if (sublineSelect && sublines.includes(selectedSubline)) sublineSelect.value = selectedSubline;
}

function buildPaginatedTable(rows, columns) {
    const wrapper = document.createElement('div');
    let currentPage = 1;
    const totalPages = Math.max(1, Math.ceil(rows.length / ROWS_PER_PAGE));

    const renderPage = () => {
        const start = (currentPage - 1) * ROWS_PER_PAGE;
        const pageRows = rows.slice(start, start + ROWS_PER_PAGE);
        wrapper.replaceChildren(buildTable(pageRows, columns));

        if (rows.length <= ROWS_PER_PAGE) return;

        const controls = document.createElement('div');
        controls.className = 'd-flex justify-content-center align-items-center gap-2 mt-3';

        const previous = document.createElement('button');
        previous.className = 'btn btn-sm btn-outline-secondary';
        previous.textContent = 'Anterior';
        previous.disabled = currentPage === 1;
        previous.addEventListener('click', () => {
            currentPage--;
            renderPage();
        });

        const pageLabel = document.createElement('span');
        pageLabel.textContent = `Página ${currentPage} de ${totalPages}`;

        const next = document.createElement('button');
        next.className = 'btn btn-sm btn-outline-secondary';
        next.textContent = 'Siguiente';
        next.disabled = currentPage === totalPages;
        next.addEventListener('click', () => {
            currentPage++;
            renderPage();
        });

        controls.append(previous, pageLabel, next);
        wrapper.appendChild(controls);
    };

    renderPage();
    return wrapper;
}

function buildTable(rows, columns) {
    const table = document.createElement('table');
    table.className = 'table table-striped table-hover align-middle mb-0';
    const head = document.createElement('thead');
    head.className = 'table-warning';
    const headRow = document.createElement('tr');
    columns.forEach(column => {
        const cell = document.createElement('th');
        cell.textContent = column;
        headRow.appendChild(cell);
    });
    head.appendChild(headRow);
    table.appendChild(head);
    const body = document.createElement('tbody');
    rows.forEach(row => {
        const tr = document.createElement('tr');
        columns.forEach(column => {
            const cell = document.createElement('td');
            const value = row[column];
            cell.textContent = column === 'IMPORTE' && value !== null && value !== undefined && value !== ''
                ? `$${value}`
                : value ?? '';
            tr.appendChild(cell);
        });
        body.appendChild(tr);
    });
    table.appendChild(body);
    return table;
}

async function loadInventory() {
    const response = await fetch('/api/inventory');
    if (!response.ok) throw new Error('Inventory is not available');
    const result = await response.json();
    inventoryData = result.data || [];
    setInventoryButtonsDisabled(false);
    updateHierarchyFilters();
    renderInventory(inventoryData, document.getElementById('storeSelect')?.value || '');
}

async function pollScrapeStatus() {
    const logoutButton = document.getElementById('logoutBtn');
    try {
        const response = await fetch('/api/inventory/status');
        if (!response.ok) throw new Error('Status unavailable');
        statusRequestErrorLogged = false;
        const status = await response.json();
        const statusChanged = status.status !== lastLoggedScrapeStatus;
        if (status.status === 'running') {
            scrapeStartedThisSession = true;
            setInventoryButtonsDisabled(true);
            if (logoutButton) logoutButton.disabled = true;
            if (statusChanged) console.info('[Inventario] Scraper iniciado.');
            lastLoggedScrapeStatus = status.status;
            return;
        }
        if (status.status === 'error') {
            if (logoutButton) logoutButton.disabled = false;
            setInventoryButtonsDisabled(false);
            if (statusChanged) console.error('[Inventario] El scraper falló:', status.message);
            lastLoggedScrapeStatus = status.status;
            document.getElementById('statusMessage').textContent = status.message || 'No se pudo cargar el inventario.';
            clearInterval(statusTimer);
            return;
        }
        if (status.status === 'completed') {
            if (statusChanged && scrapeStartedThisSession) console.info('[Inventario] Scraper terminado.');
            lastLoggedScrapeStatus = status.status;
            if (!scrapeStartedThisSession && !rebuildPromptShown) {
                rebuildPromptShown = true;
                const rebuild = window.confirm('Ya existe un inventario cargado. ¿Deseas reconstruir el dataframe?');
                if (rebuild) {
                    scrapeStartedThisSession = true;
                    clearRenderedInventory();
                    showScrapingCard();
                    await fetch('/api/inventory/scrape', { method: 'POST' });
                    clearInterval(statusTimer);
                    statusTimer = setInterval(pollScrapeStatus, 1000);
                    return;
                }
            }
            if (logoutButton) logoutButton.disabled = false;
            setInventoryButtonsDisabled(false);
            displayBuiltAt(status.built_at);
            clearInterval(statusTimer);
            const stores = await refreshStoreDropdown();
            if (stores.length > 0) {
                document.getElementById('storeFilterSection')?.classList.remove('d-none');
                document.getElementById('actionButtons')?.classList.remove('d-none');
            }
            await loadInventory();
            sessionStorage.removeItem('inventoryScrapeStarted');
        }
    } catch (error) {
        if (logoutButton) logoutButton.disabled = false;
        if (!statusRequestErrorLogged) {
            console.error('[Inventario] No se pudo consultar el estado del scraper.', error);
            statusRequestErrorLogged = true;
        }
        document.getElementById('statusMessage').textContent = 'No se pudo consultar el estado del inventario.';
    }
}

export function setupInventory() {
    const storeSelect = document.getElementById('storeSelect');
    const lineSelect = document.getElementById('lineSelect');
    const sublineSelect = document.getElementById('sublineSelect');
    const reloadButton = document.getElementById('reloadBtn');
    const downloadButton = document.getElementById('downloadBtn');
    if (!storeSelect) return;

    storeSelect.addEventListener('change', () => {
        updateHierarchyFilters();
        renderInventory(inventoryData, storeSelect.value);
    });
    lineSelect?.addEventListener('change', () => {
        updateHierarchyFilters();
        renderInventory(inventoryData, storeSelect.value);
    });
    sublineSelect?.addEventListener('change', () => renderInventory(inventoryData, storeSelect.value));

    reloadButton?.addEventListener('click', async () => {
        showScrapingCard();
        setInventoryButtonsDisabled(true);
        await fetch('/api/inventory/scrape', { method: 'POST' });
        scrapeStartedThisSession = true;
        clearInterval(statusTimer);
        statusTimer = setInterval(pollScrapeStatus, 1000);
        await pollScrapeStatus();
    });

    downloadButton?.addEventListener('click', () => {
        const store = storeSelect.value;
        const line = lineSelect?.value || '';
        const subline = sublineSelect?.value || '';
        const rows = inventoryData.filter(row =>
            row.TIENDA === store &&
            (!line || row.LINEA === line) &&
            (!subline || row.SUBLINEA === subline)
        );
        if (!rows.length) return;
        const columns = ['PRODUCTO', 'LINEA', 'SUBLINEA', 'TIENDA', 'ALMACEN', 'CANTIDAD UNITARIA', 'PRESENTACION', 'CANT', 'N° CAJAS', 'IMPORTE'];
        const csv = [columns, ...rows.map(row => columns.map(column => {
            const value = row[column] ?? '';
            return `"${String(value).replaceAll('"', '""')}"`;
        }))].map(row => row.join(',')).join('\n');
        const link = document.createElement('a');
        link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
        link.download = `inventario_${store}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    });

    /*
    // Legacy manual refresh implementation retained for reference.
    reloadButton?.addEventListener('click', async () => {
        await fetch('/api/inventory/scrape', { method: 'POST' });
        clearInterval(statusTimer);
        statusTimer = setInterval(pollScrapeStatus, 1000);
        await pollScrapeStatus();
    });
    */

    pollScrapeStatus();
    statusTimer = setInterval(pollScrapeStatus, 1000);
}
