/**
 * Login page specific functionality
 */

document.addEventListener('DOMContentLoaded', () => {
    const showSignupLink = document.getElementById('showSignup');
    const showLoginLink = document.getElementById('showLogin');
    const loginCard = document.querySelector('#loginForm').closest('.login-card');
    const signupCard = document.getElementById('signupCard');
    const signupForm = document.getElementById('signupForm');

    // Toggle between login and signup forms
    if (showSignupLink) {
        showSignupLink.addEventListener('click', (e) => {
            e.preventDefault();
            loginCard.classList.add('hidden');
            signupCard.classList.remove('hidden');
            signupCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }

    if (showLoginLink) {
        showLoginLink.addEventListener('click', (e) => {
            e.preventDefault();
            signupCard.classList.add('hidden');
            loginCard.classList.remove('hidden');
            loginCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }

    // Validate password confirmation
    if (signupForm) {
        const passwordField = document.getElementById('signup_password');
        const confirmPasswordField = document.getElementById('confirm_password');

        const validatePasswordMatch = () => {
            if (confirmPasswordField.value && passwordField.value !== confirmPasswordField.value) {
                const formGroup = confirmPasswordField.closest('.form-group');
                if (formGroup && !formGroup.querySelector('.form-error')) {
                    const error = document.createElement('div');
                    error.className = 'form-error';
                    error.textContent = 'Passwords do not match';
                    formGroup.appendChild(error);
                    formGroup.classList.add('error');
                }
            } else if (confirmPasswordField.value && passwordField.value === confirmPasswordField.value) {
                const formGroup = confirmPasswordField.closest('.form-group');
                if (formGroup) {
                    const error = formGroup.querySelector('.form-error');
                    if (error) error.remove();
                    formGroup.classList.remove('error');
                    formGroup.classList.add('success');
                }
            }
        };

        if (confirmPasswordField) {
            confirmPasswordField.addEventListener('blur', validatePasswordMatch);
            confirmPasswordField.addEventListener('input', Utils.debounce(validatePasswordMatch, 300));
        }

        signupForm.addEventListener('submit', (e) => {
            if (passwordField.value !== confirmPasswordField.value) {
                e.preventDefault();
                Utils.showNotification('Passwords do not match', 'error');
            }
        });
    }

    // Handle form submissions
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            // In a real app, this would send the data to the server
            Utils.showNotification('Login functionality will be implemented', 'info');
        });
    }

    if (signupForm) {
        signupForm.addEventListener('submit', (e) => {
            e.preventDefault();
            // In a real app, this would send the data to the server
            Utils.showNotification('Signup functionality will be implemented', 'info');
        });
    }
});

