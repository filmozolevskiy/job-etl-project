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
        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll('.nav-link');

        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            const dataPage = link.getAttribute('data-page');
            
            // Remove active class first
            link.classList.remove('active');
            
            // Check if current path matches the link's href
            let isActive = false;
            
            if (href) {
                // Normalize paths for comparison
                const linkPath = href.split('?')[0]; // Remove query params
                const currentPathClean = currentPath.split('?')[0]; // Remove query params
                
                // Exact match
                if (currentPathClean === linkPath) {
                    isActive = true;
                }
                // Special case for root/index - only match if path is exactly "/"
                else if (linkPath === '/' || linkPath === '') {
                    isActive = (currentPathClean === '/' || currentPathClean === '');
                }
                // Check if current path starts with the link path (for nested routes)
                else if (currentPathClean.startsWith(linkPath) && linkPath !== '/') {
                    // Make sure it's not a partial match (e.g., /dashboard shouldn't match /dashboard-something)
                    const nextChar = currentPathClean[linkPath.length];
                    if (!nextChar || nextChar === '/') {
                        isActive = true;
                    }
                }
            }
            
            // If no href match, try data-page attribute
            if (!isActive && dataPage) {
                const pathParts = currentPath.split('/').filter(p => p);
                
                if (dataPage === 'dashboard') {
                    isActive = pathParts.includes('dashboard') || currentPath === '/dashboard';
                } else if (dataPage === 'index') {
                    // Index should only match root or empty path
                    isActive = (pathParts.length === 0 || currentPath === '/');
                } else if (dataPage === 'jobs') {
                    isActive = pathParts.includes('jobs') && !pathParts.includes('dashboard');
                } else {
                    isActive = pathParts.includes(dataPage);
                }
            }
            
            if (isActive) {
                link.classList.add('active');
            }
        });
    },

    /**
     * Initialize user profile click handler
     */
    initUserProfile() {
        const userProfile = document.querySelector('.user-profile');
        if (userProfile) {
            // User profile is clickable but doesn't navigate anywhere specific
            // Can be extended later for account management
            userProfile.style.cursor = 'pointer';
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

