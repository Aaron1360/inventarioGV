// tables.js: Modularized table rendering and tab logic for inventory DataFrames

const ROWS_PER_PAGE = 30;

export function renderInventoryTabs(tableContainer, wholesale, retail, prices) {
    if (!tableContainer) return;
    tableContainer.innerHTML = `
        <ul class="nav nav-tabs mb-3" id="dataTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="tab-mayoreo" data-bs-toggle="tab" data-bs-target="#tabPanel-mayoreo" type="button" role="tab">Mayoreo</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="tab-menudeo" data-bs-toggle="tab" data-bs-target="#tabPanel-menudeo" type="button" role="tab">Menudeo</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="tab-precios" data-bs-toggle="tab" data-bs-target="#tabPanel-precios" type="button" role="tab">Precios</button>
            </li>
        </ul>
        <div class="tab-content" id="dataTabsContent">
            <div class="tab-pane fade show active" id="tabPanel-mayoreo" role="tabpanel"></div>
            <div class="tab-pane fade" id="tabPanel-menudeo" role="tabpanel"></div>
            <div class="tab-pane fade" id="tabPanel-precios" role="tabpanel"></div>
        </div>
    `;
    renderPaginatedTable('tabPanel-mayoreo', wholesale, [
        { key: 'presentacion', header: 'Presentación' },
        { key: 'cajas', header: 'Cajas' }
    ], 1);
    renderPaginatedTable('tabPanel-menudeo', retail, [
        { key: 'presentacion', header: 'Presentación' },
        { key: 'piezas', header: 'Piezas' }
    ], 1);
    renderPaginatedTable('tabPanel-precios', prices, [
        { key: 'presentacion', header: 'Presentación' },
        { key: 'precio', header: 'Precio' }
    ], 1);
}

function renderPaginatedTable(containerId, data, columns, page) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!Array.isArray(data) || data.length === 0) {
        container.innerHTML = '<div class="text-center text-muted">No hay datos para mostrar.</div>';
        return;
    }
    const totalPages = Math.ceil(data.length / ROWS_PER_PAGE);
    const startIdx = (page - 1) * ROWS_PER_PAGE;
    const endIdx = Math.min(startIdx + ROWS_PER_PAGE, data.length);
    let html = `<div class="table-scroll-wrapper">
        <table class="table table-striped table-hover align-middle mb-0">
            <thead class="table-warning">
                <tr><th>#</th>`;
    columns.forEach(col => {
        html += `<th>${col.header}</th>`;
    });
    html += `</tr></thead><tbody>`;
    for (let i = startIdx; i < endIdx; i++) {
        let rowClass = '';
        let cajasCellClass = '';
        if (containerId === 'tabPanel-mayoreo' && columns.some(c => c.key === 'cajas')) {
            const cajas = parseFloat(data[i]['cajas']);
            if (!isNaN(cajas) && cajas > 0) {
                cajasCellClass = 'cajas-highlight';
            }
        }
        html += `<tr${rowClass ? ` class="${rowClass}"` : ''}>`;
        html += `<td>${i + 1}</td>`;
        columns.forEach(col => {
            if (col.key === 'cajas' && cajasCellClass) {
                html += `<td class="${cajasCellClass}">${data[i][col.key] ?? ''}</td>`;
            } else {
                html += `<td>${data[i][col.key] ?? ''}</td>`;
            }
        });
        html += '</tr>';
    }
    html += '</tbody></table></div>';
    // Pagination controls
    html += `<div class="pagination-controls d-flex justify-content-center align-items-center gap-2 mt-2">`;
    html += `<button class="btn btn-sm btn-outline-secondary" ${page === 1 ? 'disabled' : ''} data-page="${page - 1}">Anterior</button>`;
    html += `<span>Página ${page} de ${totalPages}</span>`;
    html += `<button class="btn btn-sm btn-outline-secondary" ${page === totalPages ? 'disabled' : ''} data-page="${page + 1}">Siguiente</button>`;
    html += `</div>`;
    container.innerHTML = html;
    // Pagination event listeners
    const btns = container.querySelectorAll('.pagination-controls button');
    btns.forEach(btn => {
        btn.addEventListener('click', function() {
            const newPage = parseInt(this.getAttribute('data-page'));
            renderPaginatedTable(containerId, data, columns, newPage);
        });
    });
}
