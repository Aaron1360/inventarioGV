document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const loginMessage = document.getElementById('loginMessage');

    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            loginMessage.textContent = '';
            const formData = new FormData(loginForm);
            try {
                const response = await fetch('/login', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                if (response.ok && result.success) {
                    loginMessage.textContent = '¡Inicio de sesión exitoso! Redirigiendo...';
                    loginMessage.classList.remove('error');
                    loginMessage.classList.add('success');
                    setTimeout(() => {
                        window.location.href = '/'; // Redirige a la página principal después de iniciar sesión
                    }, 1200);
                } else {
                    loginMessage.textContent = result.message || 'Error al iniciar sesión.';
                    loginMessage.classList.remove('success');
                    loginMessage.classList.add('error');
                }
            } catch (err) {
                loginMessage.textContent = 'Error de red.';
                loginMessage.classList.remove('success');
                loginMessage.classList.add('error');
            }
        });
    }

    // Password toggle functionality
    const togglePassword = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('password');
    if (togglePassword && passwordInput) {
        togglePassword.addEventListener('click', function() {
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                togglePassword.querySelector('.icon-eye').style.filter = 'brightness(0.5)';
            } else {
                passwordInput.type = 'password';
                togglePassword.querySelector('.icon-eye').style.filter = '';
            }
        });
    }

    const reloadBtn = document.getElementById('reloadBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    const tableContainer = document.getElementById('tableContainer');
    const preTableMessage = document.getElementById('preTableMessage');

    // Add tab navigation for tables
    let tabNav = null;
    let tabContent = null;
    function createTabs() {
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
        tabNav = document.getElementById('dataTabs');
        tabContent = document.getElementById('dataTabsContent');
    }

    // Pagination and rendering for each table
    function renderPaginatedTable(data, columns, containerId, page, rowsPerPage) {
        const container = document.getElementById(containerId);
        if (!container) return;
        if (!Array.isArray(data) || data.length === 0) {
            container.innerHTML = '<div class="text-center text-muted">No hay datos para mostrar.</div>';
            return;
        }
        const totalPages = Math.ceil(data.length / rowsPerPage);
        const startIdx = (page - 1) * rowsPerPage;
        const endIdx = Math.min(startIdx + rowsPerPage, data.length);
        let html = `<div style="overflow-x:auto; max-height:55vh;">
            <table class="table table-striped table-hover align-middle mb-0">
                <thead class="table-warning">
                    <tr>`;
        columns.forEach(col => {
            html += `<th>${col.header}</th>`;
        });
        html += `</tr></thead><tbody>`;
        for (let i = startIdx; i < endIdx; i++) {
            html += '<tr>';
            columns.forEach(col => {
                html += `<td>${data[i][col.key] ?? ''}</td>`;
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
                renderPaginatedTable(data, columns, containerId, newPage, rowsPerPage);
            });
        });
    }

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async function() {
            try {
                const res = await fetch('/logout', { method: 'POST' });
                const result = await res.json();
                if (result.success) {
                    window.location.href = '/login';
                }
            } catch (err) {
                window.location.href = '/login';
            }
        });
    }

    // Fetch and populate store dropdown
    const storeSelect = document.getElementById('storeSelect');
    async function fetchStores() {
        try {
            const res = await fetch('/stores');
            const stores = await res.json();
            if (Array.isArray(stores) && stores.length > 0) {
                storeSelect.innerHTML = stores.map(s => `<option value="${s.name}">${s.name}</option>`).join('');
            } else {
                storeSelect.innerHTML = '<option value="">No hay sucursales</option>';
            }
        } catch (err) {
            storeSelect.innerHTML = '<option value="">Error al cargar sucursales</option>';
        }
    }
    if (storeSelect) {
        fetchStores();
    }

    // Pagination variables
    let currentPage = 1;
    let paginatedData = [];
    const rowsPerPage = 50;

    // Helper to calculate box count from stock array (allow decimals)
    function getBoxCount(stockArr) {
        let entry = stockArr.find(s => s.startsWith("CAJ"));
        if (!entry) entry = stockArr.find(s => s.startsWith("PAQ"));
        if (!entry) return '';
        const piecesMatch = entry.match(/\((\d+)\)/);
        const existenceMatch = entry.match(/\[(\d+)\]/);
        if (piecesMatch && existenceMatch) {
            const piecesPerPackage = parseInt(piecesMatch[1], 10);
            const existence = parseInt(existenceMatch[1], 10);
            return (existence / piecesPerPackage).toFixed(2);
        }
        return '';
    }

    // Helper to extract price from stock array (add $ sign)
    function getPrice(stockArr) {
        let entry = stockArr.find(s => s.startsWith("CAJ"));
        if (!entry) entry = stockArr.find(s => s.startsWith("PAQ"));
        if (!entry) entry = stockArr[0]; // fallback to first
        if (!entry) return '';
        const priceMatch = entry.match(/\)(\d+\.\d+)/); // matches after )
        return priceMatch ? `$${priceMatch[1]}` : '';
    }

    // Update table header to include price column
    const tableHeader = document.querySelector('#inventoryTable thead tr');
    if (tableHeader) {
        tableHeader.innerHTML = '<th>#</th><th>Línea</th><th>Nombre</th><th>Presentación</th><th>Stock</th><th>Cajas</th><th>Precio</th>';
    }

    function renderTablePage(page) {
        const tableBody = document.getElementById('tableBody');
        const statusMessage = document.getElementById('statusMessage');
        if (!paginatedData.length) {
            tableBody.innerHTML = '';
            statusMessage.textContent = 'No hay datos para mostrar.';
            // Move pagination below statusMessage
            renderPaginationControls();
            return;
        }
        const startIdx = (page - 1) * rowsPerPage;
        const endIdx = Math.min(startIdx + rowsPerPage, paginatedData.length);
        let html = '';
        for (let i = startIdx; i < endIdx; i++) {
            const row = paginatedData[i];
            const boxCount = getBoxCount(row.stock);
            const price = getPrice(row.stock);
            html += `<tr>`;
            html += `<td>${i + 1}</td>`; // Row number
            html += `<td>${row.line}</td>`;
            html += `<td>${row.name}</td>`;
            html += `<td>${row.presentation}</td>`;
            html += `<td>${row.stock.join('<br>')}</td>`;
            html += `<td>${boxCount}</td>`;
            html += `<td>${price}</td>`;
            html += `</tr>`;
        }
        tableBody.innerHTML = html;
        statusMessage.textContent = `Mostrando ${startIdx + 1} - ${endIdx} de ${paginatedData.length} filas`;
        // Move pagination below statusMessage
        renderPaginationControls();
    }

    function renderPaginationControls() {
        let pagination = document.getElementById('paginationControls');
        if (!pagination) {
            pagination = document.createElement('div');
            pagination.id = 'paginationControls';
            pagination.className = 'pagination-controls';
            // Move below statusMessage
            const statusMessage = document.getElementById('statusMessage');
            statusMessage.parentNode.insertBefore(pagination, statusMessage.nextSibling);
        }
        pagination.innerHTML = '';
        const totalPages = Math.ceil(paginatedData.length / rowsPerPage);
        if (totalPages <= 1) {
            pagination.style.display = 'none';
            return;
        }
        pagination.style.display = 'flex';
        const prevBtn = document.createElement('button');
        prevBtn.textContent = 'Anterior';
        prevBtn.disabled = currentPage === 1;
        prevBtn.onclick = () => { currentPage--; renderTablePage(currentPage); };
        const nextBtn = document.createElement('button');
        nextBtn.textContent = 'Siguiente';
        nextBtn.disabled = currentPage === totalPages;
        nextBtn.onclick = () => { currentPage++; renderTablePage(currentPage); };
        const pageInfo = document.createElement('span');
        pageInfo.textContent = `Página ${currentPage} de ${totalPages}`;
        pagination.appendChild(prevBtn);
        pagination.appendChild(pageInfo);
        pagination.appendChild(nextBtn);
    }

    const scraperNotification = document.getElementById('scraperNotification');
    function showScraperNotification() {
        if (scraperNotification) {
            scraperNotification.style.display = 'block';
            document.body.classList.add('scraper-blocked');
        }
    }
    function hideScraperNotification() {
        if (scraperNotification) {
            scraperNotification.style.display = 'none';
            document.body.classList.remove('scraper-blocked');
        }
    }

    // Load and display inventory data when reloadBtn is clicked
    if (reloadBtn) {
        reloadBtn.addEventListener('click', async function() {
            const storeSelect = document.getElementById('storeSelect');
            const tableBody = document.getElementById('tableBody');
            const statusMessage = document.getElementById('statusMessage');
            const downloadBtn = document.getElementById('downloadBtn');
            if (!storeSelect.value) {
                statusMessage.textContent = 'Selecciona una sucursal.';
                return;
            }
            tableBody.innerHTML = '';
            statusMessage.textContent = 'Cargando inventario...';
            showScraperNotification(); // Show notification and block UI
            try {
                const res = await fetch(`/scrape?store_name=${encodeURIComponent(storeSelect.value)}`);
                const rawData = await res.json();
                // Expecting {wholesale, retail, prices} from backend
                if (rawData && rawData.wholesale && Array.isArray(rawData.wholesale) && rawData.wholesale.length > 0) {
                    // Hide pre-table message, show table
                    if (preTableMessage) preTableMessage.classList.add('d-none');
                    if (tableContainer) tableContainer.classList.remove('d-none');
                    createTabs();
                    // Render each table in its tab
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

    // On page load, ensure table is hidden and message is shown
    if (preTableMessage) preTableMessage.classList.remove('d-none');
    if (tableContainer) tableContainer.classList.add('d-none');
});