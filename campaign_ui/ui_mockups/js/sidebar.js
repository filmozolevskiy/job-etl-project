/**
 * Sidebar component and navigation functionality
 */

const Sidebar = {
    /**
     * Initialize sidebar
     */
    init() {
        this.setActiveNavItem();
        this.initUserProfile();
    },

    /**
     * Set active navigation item based on current page
     */
    setActiveNavItem() {
        const currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';
        const navLinks = document.querySelectorAll('.nav-link');

        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (href === currentPage || (currentPage === '' && href === 'dashboard.html')) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    },

    /**
     * Initialize user profile click handler
     */
    initUserProfile() {
        const userProfile = document.querySelector('.user-profile');
        if (userProfile) {
            userProfile.addEventListener('click', () => {
                window.location.href = 'account_management.html';
            });
        }
    },

    /**
     * Toggle mobile sidebar (for responsive design)
     */
    toggle() {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.toggle('open');
        }
    }
};

// Initialize sidebar when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    Sidebar.init();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Sidebar;
}

