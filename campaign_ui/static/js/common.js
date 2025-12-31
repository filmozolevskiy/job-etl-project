/**
 * Common JavaScript utilities and functions
 */

// Utility functions
const Utils = {
    /**
     * Format date to readable string
     */
    formatDate(date) {
        if (!date) return '';
        const d = new Date(date);
        return d.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    },

    /**
     * Format datetime to readable string
     */
    formatDateTime(date) {
        if (!date) return '';
        const d = new Date(date);
        return d.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    /**
     * Show notification/toast message
     */
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;

        document.body.appendChild(notification);

        // Remove after 3 seconds
        setTimeout(() => {
            notification.classList.add('notification-hiding');
            setTimeout(() => {
                if (notification.parentNode) {
                    document.body.removeChild(notification);
                }
            }, 300);
        }, 3000);
    },

    /**
     * Debounce function
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * Validate email
     */
    validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },

    /**
     * Validate URL
     */
    validateURL(url) {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    }
};

// Form validation
const FormValidator = {
    /**
     * Validate form field
     */
    validateField(field) {
        const value = field.value.trim();
        const fieldType = field.type || field.tagName.toLowerCase();
        let isValid = true;
        let errorMessage = '';

        // Required validation
        if (field.hasAttribute('required') && !value) {
            isValid = false;
            errorMessage = 'This field is required';
        }

        // Email validation
        if (fieldType === 'email' && value && !Utils.validateEmail(value)) {
            isValid = false;
            errorMessage = 'Please enter a valid email address';
        }

        // URL validation
        if (fieldType === 'url' && value && !Utils.validateURL(value)) {
            isValid = false;
            errorMessage = 'Please enter a valid URL';
        }

        // Password validation
        if (fieldType === 'password' && value && value.length < 8) {
            isValid = false;
            errorMessage = 'Password must be at least 8 characters';
        }

        // Update UI
        const formGroup = field.closest('.form-group');
        if (formGroup) {
            if (isValid) {
                formGroup.classList.remove('error');
                formGroup.classList.add('success');
                this.removeError(formGroup);
            } else {
                formGroup.classList.remove('success');
                formGroup.classList.add('error');
                this.showError(formGroup, errorMessage);
            }
        }

        return isValid;
    },

    /**
     * Show error message
     */
    showError(formGroup, message) {
        this.removeError(formGroup);
        const error = document.createElement('div');
        error.className = 'form-error';
        error.textContent = message;
        formGroup.appendChild(error);
    },

    /**
     * Remove error message
     */
    removeError(formGroup) {
        const error = formGroup.querySelector('.form-error');
        if (error) {
            error.remove();
        }
    },

    /**
     * Validate entire form
     */
    validateForm(form) {
        const fields = form.querySelectorAll('input[required], select[required], textarea[required]');
        let isValid = true;

        fields.forEach(field => {
            if (!this.validateField(field)) {
                isValid = false;
            }
        });

        return isValid;
    }
};

// Initialize form validation on page load
document.addEventListener('DOMContentLoaded', () => {
    // Add real-time validation to form fields
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        const fields = form.querySelectorAll('input, select, textarea');
        fields.forEach(field => {
            field.addEventListener('blur', () => {
                FormValidator.validateField(field);
            });

            field.addEventListener('input', Utils.debounce(() => {
                if (field.classList.contains('error') || field.classList.contains('success')) {
                    FormValidator.validateField(field);
                }
            }, 300));
        });

        form.addEventListener('submit', (e) => {
            if (!FormValidator.validateForm(form)) {
                e.preventDefault();
                Utils.showNotification('Please fix the errors in the form', 'error');
            }
        });
    });
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Utils, FormValidator };
}

