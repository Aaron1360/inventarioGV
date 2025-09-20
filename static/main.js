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
                    loginMessage.textContent = 'Login successful! Redirecting...';
                    loginMessage.classList.remove('error');
                    loginMessage.classList.add('success');
                    setTimeout(() => {
                        window.location.href = '/'; // Redirect to main page after login
                    }, 1200);
                } else {
                    loginMessage.textContent = result.message || 'Login failed.';
                    loginMessage.classList.remove('success');
                    loginMessage.classList.add('error');
                }
            } catch (err) {
                loginMessage.textContent = 'Network error.';
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

    // Restore icons for reload and download buttons
    const reloadBtn = document.getElementById('reloadBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    if (reloadBtn) reloadBtn.innerHTML = '<span class="icon-reload"></span>';
    if (downloadBtn) downloadBtn.innerHTML = '<span class="icon-download"></span>';

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

    // Update table header to include row number
    const tableHeader = document.querySelector('#inventoryTable thead tr');
    if (tableHeader) {
        tableHeader.innerHTML = '<th>#</th><th>Línea</th><th>Nombre</th><th>Presentación</th><th>Stock</th>';
    }

    function renderTablePage(page) {
        const tableBody = document.getElementById('tableBody');
        const statusMessage = document.getElementById('statusMessage');
        if (!paginatedData.length) {
            tableBody.innerHTML = '';
            statusMessage.textContent = 'No hay datos para mostrar.';
            return;
        }
        const startIdx = (page - 1) * rowsPerPage;
        const endIdx = Math.min(startIdx + rowsPerPage, paginatedData.length);
        let html = '';
        for (let i = startIdx; i < endIdx; i++) {
            const row = paginatedData[i];
            html += `<tr>`;
            html += `<td>${i + 1}</td>`; // Row number
            html += `<td>${row.line}</td>`;
            html += `<td>${row.name}</td>`;
            html += `<td>${row.presentation}</td>`;
            html += `<td>${row.stock.join('<br>')}</td>`;
            html += `</tr>`;
        }
        tableBody.innerHTML = html;
        statusMessage.textContent = `Mostrando ${startIdx + 1} - ${endIdx} de ${paginatedData.length} filas`;
        renderPaginationControls();
    }

    function renderPaginationControls() {
        let pagination = document.getElementById('paginationControls');
        if (!pagination) {
            pagination = document.createElement('div');
            pagination.id = 'paginationControls';
            pagination.style.display = 'flex';
            pagination.style.justifyContent = 'center';
            pagination.style.gap = '8px';
            pagination.style.margin = '1rem 0';
            document.getElementById('tableContainer').appendChild(pagination);
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
            try {
                const res = await fetch(`/scrape?store_name=${encodeURIComponent(storeSelect.value)}`);
                const rawData = await res.json();
                if (Array.isArray(rawData) && rawData.length > 0) {
                    // Clean and sort data using clean_data.js
                    paginatedData = window.groupAndSortInventory(rawData);
                    currentPage = 1;
                    renderTablePage(currentPage);
                    downloadBtn.disabled = false;
                } else {
                    paginatedData = [];
                    renderTablePage(1);
                    downloadBtn.disabled = true;
                }
            } catch (err) {
                paginatedData = [];
                renderTablePage(1);
                downloadBtn.disabled = true;
            }
        });
    }
});