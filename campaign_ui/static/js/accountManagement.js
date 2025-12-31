/**
 * Account Management page specific functionality
 */

const AccountManagement = {
    init() {
        this.initPasswordForm();
        this.initLogoutButton();
    },

    initPasswordForm() {
        const passwordForm = document.getElementById('passwordForm');
        if (passwordForm) {
            passwordForm.addEventListener('submit', (event) => {
                event.preventDefault();
                this.handlePasswordChange(event);
            });
        }
    },

    initLogoutButton() {
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                this.handleLogout();
            });
        }
    },

    handlePasswordChange(event) {
        const currentPassword = document.getElementById('currentPassword').value;
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        
        // Validate passwords match
        if (newPassword !== confirmPassword) {
            Utils.showNotification('New passwords do not match. Please try again.', 'error');
            return;
        }
        
        // Validate password length
        if (newPassword.length < 8) {
            Utils.showNotification('Password must be at least 8 characters long.', 'error');
            return;
        }
        
        // Simulate password change (in real app, this would make an API call)
        Utils.showNotification('Password updated successfully!', 'success');
        
        // Reset form
        document.getElementById('passwordForm').reset();
    },

    handleLogout() {
        if (confirm('Are you sure you want to logout?')) {
            // In real app, this would clear session/tokens and redirect
            Utils.showNotification('You have been logged out successfully.', 'success');
            setTimeout(() => {
                window.location.href = 'login.html';
            }, 1000);
        }
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    AccountManagement.init();
});

