// Authentication and login logic
export function setupAuth() {
    const loginForm = document.getElementById('loginForm');
    const loginMessage = document.getElementById('loginMessage');
    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            loginMessage.textContent = '';
            const formData = new FormData(loginForm);
            try {
                console.info('[Inventario] Enviando credenciales al servidor.');
                const response = await fetch('/login', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                if (response.ok && result.success) {
                    sessionStorage.setItem('inventoryScrapeStarted', 'true');
                    console.info('[Inventario] Login correcto. Scraper iniciado en segundo plano.');
                    loginMessage.textContent = '¡Inicio de sesión exitoso! Redirigiendo...';
                    loginMessage.classList.remove('error');
                    loginMessage.classList.add('success');
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 1200);
                } else {
                    console.warn('[Inventario] Login rechazado.');
                    loginMessage.textContent = result.message || 'Error al iniciar sesión.';
                    loginMessage.classList.remove('success');
                    loginMessage.classList.add('error');
                }
            } catch (err) {
                console.error('[Inventario] Error de red durante el login.', err);
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
    // Logout
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
}
