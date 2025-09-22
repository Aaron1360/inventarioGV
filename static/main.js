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
            hideScraperNotification(); // Hide notification and unblock UI
        });
    }
});