import { refreshStoreDropdown } from './store.js';

let inventoryData = [];
let statusTimer = null;
const ROWS_PER_PAGE = 20;
let scrapeStartedThisSession = sessionStorage.getItem('inventoryScrapeStarted') === 'true';
let rebuildPromptShown = false;
let lastLoggedScrapeStatus = null;
let statusRequestErrorLogged = false;
let updateCooldownTimer = null;
let dataframeBuiltAt = null;

function displayBuiltAt(timestamp) {
    const element = document.getElementById('lastBuiltAt');
    if (!element || !timestamp) return;
    dataframeBuiltAt = timestamp;
    const date = new Date(timestamp);
    element.textContent = `Última actualización: ${date.toLocaleString()}`;
}

function buildInventoryFilename(store) {
    const date = new Date(dataframeBuiltAt || Date.now());
    const datePart = [
        date.getFullYear(),
        String(date.getMonth() + 1).padStart(2, '0'),
        String(date.getDate()).padStart(2, '0'),
    ].join('-');
    const hour = date.getHours() % 12 || 12;
    const timePart = `${String(hour).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}${date.getHours() >= 12 ? 'PM' : 'AM'}`;
    return `inventario_${store}_${datePart}_${timePart}.xlsx`;
}

function setInventoryButtonsDisabled(disabled) {
    ['reloadBtn', 'downloadBtn'].forEach(id => {
        const button = document.getElementById(id);
        if (button) button.disabled = disabled;
    });
    if (!disabled && updateCooldownTimer) {
        const reloadButton = document.getElementById('reloadBtn');
        if (reloadButton) reloadButton.disabled = true;
    }
}

function startUpdateCooldown(seconds) {
    const button = document.getElementById('reloadBtn');
    if (!button) return;
    if (updateCooldownTimer) clearInterval(updateCooldownTimer);
    let remaining = seconds;
    button.disabled = true;
    button.textContent = `Actualizar (${remaining}s)`;
    updateCooldownTimer = setInterval(() => {
        remaining--;
        if (remaining <= 0) {
            clearInterval(updateCooldownTimer);
            updateCooldownTimer = null;
            button.disabled = false;
            button.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Actualizar';
            return;
        }
        button.textContent = `Actualizar (${remaining}s)`;
    }, 1000);
}

function showScrapingCard() {
    document.getElementById('scraperSpinner')?.classList.remove('d-none');
    const title = document.getElementById('preTableTitle');
    const text = document.getElementById('preTableText');
    if (title) title.textContent = 'Preparando inventario';
    if (text) text.textContent = 'Accediendo a https://grupogranvalle.com/sistema/';
    document.getElementById('preTableMessage')?.classList.remove('d-none');
}

function showScrapeError(message) {
    document.getElementById('scraperSpinner')?.classList.add('d-none');
    const title = document.getElementById('preTableTitle');
    const text = document.getElementById('preTableText');
    if (title) title.textContent = 'No se pudo cargar el inventario';
    if (text) text.textContent = message;
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
            showScrapeError(status.message || 'No se pudo cargar el inventario.');
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
                    const rebuildResponse = await fetch('/api/inventory/scrape', { method: 'POST' });
                    if (rebuildResponse.status === 429) {
                        const error = await rebuildResponse.json();
                        const retryAfter = Number(rebuildResponse.headers.get('Retry-After')) || 60;
                        startUpdateCooldown(retryAfter);
                        document.getElementById('statusMessage').textContent = error.detail || 'Espera antes de reconstruir el dataframe.';
                        rebuildPromptShown = false;
                        return;
                    }
                    if (!rebuildResponse.ok) {
                        throw new Error('No se pudo iniciar la reconstrucción del dataframe.');
                    }
                    scrapeStartedThisSession = true;
                    clearRenderedInventory();
                    showScrapingCard();
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
            if (!status.loaded) {
                throw new Error(status.message || 'El dataframe no está disponible.');
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
        showScrapeError(error.message || 'No se pudo cargar el inventario.');
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
        lastLoggedScrapeStatus = null;
        try {
            const response = await fetch('/api/inventory/scrape', { method: 'POST' });
            if (response.status === 429) {
                const error = await response.json();
                const retryAfter = Number(response.headers.get('Retry-After')) || 60;
                startUpdateCooldown(retryAfter);
                document.getElementById('statusMessage').textContent = error.detail || 'Espera antes de actualizar nuevamente.';
                return;
            }
            if (!response.ok) throw new Error('No se pudo iniciar el scraper.');
            const scrapeResult = await response.json();
            startUpdateCooldown(Number(scrapeResult.cooldown) || 60);
            clearRenderedInventory();
            showScrapingCard();
            setInventoryButtonsDisabled(true);
            scrapeStartedThisSession = true;
            clearInterval(statusTimer);
            statusTimer = setInterval(pollScrapeStatus, 1000);
            await pollScrapeStatus();
        } catch (error) {
            setInventoryButtonsDisabled(false);
            document.getElementById('statusMessage').textContent = error.message;
        }
    });

    downloadButton?.addEventListener('click', () => {
        const store = storeSelect.value;
        const line = lineSelect?.value || '';
        const subline = sublineSelect?.value || '';
        if (!store) return;
        const params = new URLSearchParams({ tienda: store });
        if (line) params.set('linea', line);
        if (subline) params.set('sublinea', subline);
        fetch(`/api/inventory/export?${params.toString()}`)
            .then(response => {
                if (!response.ok) throw new Error('No se pudo generar el archivo Excel.');
                return response.blob();
            })
            .then(blob => {
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = buildInventoryFilename(store);
                link.click();
                URL.revokeObjectURL(link.href);
            })
            .catch(error => {
                document.getElementById('statusMessage').textContent = error.message;
            });
    });

    pollScrapeStatus();
    statusTimer = setInterval(pollScrapeStatus, 1000);
}
