/**
 * Mobile menu toggle functionality
 */

const MobileMenu = {
    init() {
        this.createMobileToggle();
        this.attachEventListeners();
    },

    createMobileToggle() {
        // Check if toggle already exists
        if (document.getElementById('mobileMenuToggle')) return;

        // Check if we're on a page with sidebar (wait a bit for sidebar to load)
        const sidebarContainer = document.querySelector('.sidebar-container');
        const sidebar = document.querySelector('.sidebar');
        
        if (!sidebarContainer && !sidebar) {
            // Retry after a short delay in case sidebar is still loading
            setTimeout(() => {
                const retrySidebar = document.querySelector('.sidebar-container') || document.querySelector('.sidebar');
                if (retrySidebar) {
                    this.createMobileToggle();
                }
            }, 100);
            return;
        }

        // Create mobile menu toggle button
        const toggle = document.createElement('button');
        toggle.className = 'mobile-menu-toggle';
        toggle.setAttribute('aria-label', 'Toggle menu');
        toggle.innerHTML = '<i class="fas fa-bars"></i>';
        toggle.id = 'mobileMenuToggle';
        
        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'mobile-overlay';
        overlay.id = 'mobileOverlay';
        
        document.body.insertBefore(overlay, document.body.firstChild);
        document.body.insertBefore(toggle, document.body.firstChild);
    },

    attachEventListeners() {
        const toggle = document.getElementById('mobileMenuToggle');
        const overlay = document.getElementById('mobileOverlay');
        
        if (!toggle) return;

        // Wait for sidebar to be available
        const getSidebar = () => {
            return document.querySelector('.sidebar') || 
                   document.querySelector('.sidebar-container .sidebar');
        };

        let sidebar = getSidebar();
        if (!sidebar) {
            // Retry after sidebar loads
            setTimeout(() => {
                sidebar = getSidebar();
                if (sidebar) {
                    this.setupEventListeners(toggle, overlay, sidebar);
                }
            }, 200);
            return;
        }

        this.setupEventListeners(toggle, overlay, sidebar);
    },

    setupEventListeners(toggle, overlay, sidebar) {
        if (!toggle || !sidebar) return;

        // Toggle sidebar
        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleSidebar();
        });

        // Close sidebar when clicking overlay
        if (overlay) {
            overlay.addEventListener('click', () => {
                this.closeSidebar();
            });
        }

        // Close sidebar when clicking outside on mobile
        const clickHandler = (e) => {
            if (window.innerWidth <= 767) {
                if (sidebar && sidebar.classList.contains('open')) {
                    if (!sidebar.contains(e.target) && !toggle.contains(e.target)) {
                        this.closeSidebar();
                    }
                }
            }
        };
        document.addEventListener('click', clickHandler);

        // Close sidebar on window resize if switching to desktop
        const resizeHandler = () => {
            if (window.innerWidth >= 1024) {
                this.closeSidebar();
            }
        };
        window.addEventListener('resize', resizeHandler);

        // Close sidebar on Escape key
        const keyHandler = (e) => {
            if (e.key === 'Escape' && sidebar && sidebar.classList.contains('open')) {
                this.closeSidebar();
            }
        };
        document.addEventListener('keydown', keyHandler);
    },

    toggleSidebar() {
        const sidebar = document.querySelector('.sidebar') || 
                       document.querySelector('.sidebar-container .sidebar');
        const overlay = document.getElementById('mobileOverlay');
        const toggle = document.getElementById('mobileMenuToggle');

        if (!sidebar) return;

        sidebar.classList.toggle('open');
        
        if (overlay) {
            overlay.classList.toggle('active');
        }

        if (toggle) {
            const icon = toggle.querySelector('i');
            if (sidebar.classList.contains('open')) {
                if (icon) icon.className = 'fas fa-times';
                toggle.setAttribute('aria-label', 'Close menu');
            } else {
                if (icon) icon.className = 'fas fa-bars';
                toggle.setAttribute('aria-label', 'Toggle menu');
            }
        }

        // Prevent body scroll when menu is open
        if (sidebar.classList.contains('open')) {
            document.body.classList.add('menu-open');
        } else {
            document.body.classList.remove('menu-open');
        }
    },

    closeSidebar() {
        const sidebar = document.querySelector('.sidebar') || 
                       document.querySelector('.sidebar-container .sidebar');
        const overlay = document.getElementById('mobileOverlay');
        const toggle = document.getElementById('mobileMenuToggle');

        if (sidebar) {
            sidebar.classList.remove('open');
        }

        if (overlay) {
            overlay.classList.remove('active');
        }

        if (toggle) {
            const icon = toggle.querySelector('i');
            if (icon) icon.className = 'fas fa-bars';
            toggle.setAttribute('aria-label', 'Toggle menu');
        }

        document.body.classList.remove('menu-open');
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    MobileMenu.init();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MobileMenu;
}

