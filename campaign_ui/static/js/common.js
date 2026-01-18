/**
 * Common JavaScript utilities and functions
 */

// Utility functions
const Utils = {
    /**
     * Set button loading state
     */
    setButtonLoading(button, isLoading) {
        if (!button) return;
        if (isLoading) {
            button.classList.add('btn-loading');
            button.disabled = true;
            const btnText = button.querySelector('.btn-text');
            if (btnText) {
                button.setAttribute('data-original-text', btnText.textContent);
                const loadingText = button.getAttribute('data-loading-text') || 'Processing...';
                btnText.textContent = loadingText;
            } else {
                button.setAttribute('data-original-text', button.innerHTML);
                const loadingText = button.getAttribute('data-loading-text') || 'Processing...';
                // Keep icon if it exists
                const icon = button.querySelector('i');
                if (icon) {
                    button.innerHTML = icon.outerHTML + ' ' + loadingText;
                } else {
                    button.innerHTML = loadingText;
                }
            }
        } else {
            button.classList.remove('btn-loading');
            button.disabled = false;
            const originalText = button.getAttribute('data-original-text');
            if (originalText) {
                const btnText = button.querySelector('.btn-text');
                if (btnText) {
                    btnText.textContent = originalText;
                } else {
                    button.innerHTML = originalText;
                }
                button.removeAttribute('data-original-text');
            }
        }
    },
    
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
    showNotification(message, type = 'info', autoDismiss = true) {
        // Get or create flash messages container
        let container = document.querySelector('.flash-messages');
        if (!container) {
            container = document.createElement('div');
            container.className = 'flash-messages';
            document.body.appendChild(container);
        }
        
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        
        // Create message text
        const messageText = document.createElement('span');
        messageText.textContent = message;
        notification.appendChild(messageText);
        
        // Create close button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'notification-close';
        closeBtn.setAttribute('aria-label', 'Close notification');
        closeBtn.innerHTML = '×';
        closeBtn.onclick = () => {
            notification.classList.add('notification-hiding');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 300);
        };
        notification.appendChild(closeBtn);
        
        container.appendChild(notification);

        // Auto-dismiss for success and info messages
        // Error messages stay until manually dismissed
        if (autoDismiss && (type === 'success' || type === 'info')) {
            const dismissTime = type === 'success' ? 5000 : 3000;
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.classList.add('notification-hiding');
                    setTimeout(() => {
                        if (notification.parentNode) {
                            notification.remove();
                        }
                    }, 300);
                }
            }, dismissTime);
        }
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
    },

    /**
     * Parse an ISO-ish date string into a timestamp.
     * Returns null for missing/invalid values.
     */
    parseDateToTimestamp(value) {
        if (!value) return null;
        const time = Date.parse(value);
        return Number.isNaN(time) ? null : time;
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
                this.removeSuccess(formGroup);
                // Only show success if field has value and was previously validated
                if (value && (field.classList.contains('error') || field.classList.contains('success'))) {
                    this.showSuccess(formGroup);
                }
            } else {
                formGroup.classList.remove('success');
                formGroup.classList.add('error');
                this.removeSuccess(formGroup);
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
     * Show success message
     */
    showSuccess(formGroup) {
        this.removeSuccess(formGroup);
        // Success is shown via CSS background image, but we can add a message if needed
        // For now, just the visual indicator is enough
    },
    
    /**
     * Remove success message
     */
    removeSuccess(formGroup) {
        const success = formGroup.querySelector('.form-success');
        if (success) {
            success.remove();
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

// Table Sorting functionality
const TableSorter = {
    /**
     * Initialize table sorting for all sortable tables
     */
    init() {
        document.querySelectorAll('th.sortable').forEach(header => {
            // Make sortable headers keyboard accessible
            header.setAttribute('tabindex', '0');
            header.setAttribute('role', 'button');
            header.setAttribute('aria-sort', 'none');
            
            const handleSort = () => {
                const table = header.closest('table');
                const tbody = table.querySelector('tbody');
                if (!tbody) return;
                
                const columnIndex = Array.from(header.parentElement.children).indexOf(header);
                const dataSort = header.getAttribute('data-sort');
                const currentSort = header.classList.contains('sort-asc') ? 'asc' : 
                                   header.classList.contains('sort-desc') ? 'desc' : null;
                
                // Remove sort classes from all headers
                table.querySelectorAll('th.sortable').forEach(h => {
                    h.classList.remove('sort-asc', 'sort-desc');
                });
                
                // Determine new sort direction
                const newSort = currentSort === 'asc' ? 'desc' : 'asc';
                header.classList.add(`sort-${newSort}`);
                header.setAttribute('aria-sort', newSort === 'asc' ? 'ascending' : 'descending');
                
                // Sort rows
                const rows = Array.from(tbody.querySelectorAll('tr'));
                rows.sort((a, b) => {
                    const aCell = a.children[columnIndex];
                    const bCell = b.children[columnIndex];
                    
                    // Check if this is a date column (by data-sort attribute)
                    if (dataSort === 'date') {
                        // Prefer explicit data attribute values over text (e.g. "Today")
                        const dateA =
                            a.getAttribute('data-posted-date') ||
                            aCell?.getAttribute('data-sort-value') ||
                            aCell?.dataset?.sortValue ||
                            '';
                        const dateB =
                            b.getAttribute('data-posted-date') ||
                            bCell?.getAttribute('data-sort-value') ||
                            bCell?.dataset?.sortValue ||
                            '';

                        const timeA = Utils.parseDateToTimestamp(dateA);
                        const timeB = Utils.parseDateToTimestamp(dateB);

                        if (timeA === null && timeB === null) return 0;
                        if (timeA === null) return 1; // Missing/invalid dates go to end
                        if (timeB === null) return -1;
                        return newSort === 'asc' ? timeA - timeB : timeB - timeA;
                    }
                    
                    let aValue = aCell ? aCell.textContent.trim() : '';
                    let bValue = bCell ? bCell.textContent.trim() : '';
                    
                    // Try to parse as number
                    const aNum = parseFloat(aValue.replace(/[^0-9.-]/g, ''));
                    const bNum = parseFloat(bValue.replace(/[^0-9.-]/g, ''));
                    
                    if (!isNaN(aNum) && !isNaN(bNum)) {
                        return newSort === 'asc' ? aNum - bNum : bNum - aNum;
                    }
                    
                    // String comparison
                    if (newSort === 'asc') {
                        return aValue.localeCompare(bValue);
                    } else {
                        return bValue.localeCompare(aValue);
                    }
                });
                
                // Re-append sorted rows
                rows.forEach(row => tbody.appendChild(row));

                // If the page implements pagination (e.g. view_campaign), refresh it after sorting
                if (typeof currentPage !== 'undefined') {
                    currentPage = 1;
                }
                if (typeof updatePagination === 'function') {
                    setTimeout(updatePagination, 10);
                }
            };
            
            header.addEventListener('click', handleSort);
            header.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleSort();
                }
            });
        });
    }
};

// Delete Modal functionality
const DeleteModal = {
    /**
     * Open delete confirmation modal
     */
    open(itemName, formAction, itemType = 'item') {
        const modal = document.getElementById('deleteModal');
        const message = document.getElementById('deleteModalMessage');
        const form = document.getElementById('deleteModalForm');
        
        if (!modal || !message || !form) {
            console.error('Delete modal elements not found');
            return;
        }
        
        message.textContent = `Are you sure you want to delete ${itemType} "${itemName}"? This action cannot be undone.`;
        form.action = formAction;
        modal.classList.add('active');
        
        // Focus trap - focus on cancel button
        setTimeout(() => {
            const cancelBtn = modal.querySelector('.btn-secondary');
            if (cancelBtn) {
                cancelBtn.focus();
            }
        }, 100);
    },
    
    /**
     * Close delete confirmation modal
     */
    close() {
        const modal = document.getElementById('deleteModal');
        if (modal && modal.classList.contains('active')) {
            // Add closing class for exit animation
            modal.classList.add('closing');
            setTimeout(() => {
                modal.classList.remove('active', 'closing');
            }, 200); // Match animation duration
        }
    },
    
    /**
     * Initialize delete modal
     */
    init() {
        const modal = document.getElementById('deleteModal');
        if (!modal) return;
        
        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.close();
            }
        });
        
        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                this.close();
            }
        });
        
        // Handle form submission
        const form = document.getElementById('deleteModalForm');
        if (form) {
            form.addEventListener('submit', (e) => {
                // Form will submit normally, modal will close on page reload
                // But we can add loading state if needed
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn) {
                    Utils.setButtonLoading(submitBtn, true);
                    submitBtn.setAttribute('data-loading-text', 'Deleting...');
                }
            });
        }
    }
};

// Action Dropdown functionality
const ActionDropdown = {
    /**
     * Initialize all action dropdowns on the page
     */
    init() {
        document.addEventListener('click', (e) => {
            // Close all dropdowns when clicking outside
            if (!e.target.closest('.action-dropdown-wrapper')) {
                document.querySelectorAll('.action-dropdown-wrapper.open').forEach(wrapper => {
                    wrapper.classList.remove('open');
                });
            }
        });

        // Handle dropdown toggle clicks
        document.querySelectorAll('.action-dropdown-toggle').forEach(toggle => {
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                const wrapper = toggle.closest('.action-dropdown-wrapper');
                const isOpen = wrapper.classList.contains('open');
                
                // Close all other dropdowns
                document.querySelectorAll('.action-dropdown-wrapper.open').forEach(w => {
                    if (w !== wrapper) {
                        w.classList.remove('open');
                    }
                });
                
                // Toggle current dropdown
                wrapper.classList.toggle('open', !isOpen);
            });
        });

        // Close dropdown when clicking an item
        document.querySelectorAll('.action-dropdown-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const wrapper = item.closest('.action-dropdown-wrapper');
                if (wrapper) {
                    wrapper.classList.remove('open');
                }
            });
        });
    }
};

// Initialize form validation on page load
document.addEventListener('DOMContentLoaded', () => {
    // Initialize table sorting
    TableSorter.init();
    
    // Initialize delete modal
    DeleteModal.init();
    
    // Initialize action dropdowns
    ActionDropdown.init();
    
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
                return;
            }
            
            // Add loading state to submit button (skip if button has custom loading handling)
            const submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitButton && !submitButton.hasAttribute('data-no-auto-loading')) {
                Utils.setButtonLoading(submitButton, true);
                submitButton.setAttribute('data-loading-text', submitButton.getAttribute('data-loading-text') || 'Processing...');
            }
        });
    });
});

// Global functions for templates
function openDeleteModal(itemName, formAction, itemType) {
    DeleteModal.open(itemName, formAction, itemType);
}

function closeDeleteModal() {
    DeleteModal.close();
}

// Enhanced modal close function with animation
function closeModalWithAnimation(modalId) {
    const modal = document.getElementById(modalId);
    if (modal && modal.classList.contains('active')) {
        modal.classList.add('closing');
        setTimeout(() => {
            modal.classList.remove('active', 'closing');
        }, 200);
    }
}

// Enhanced modal open function
function openModalWithAnimation(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('closing');
        modal.classList.add('active');
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Utils, FormValidator, DeleteModal, TableSorter, ActionDropdown };
}

