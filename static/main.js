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
});