/**
 * Load sidebar component into pages
 */

async function loadSidebar() {
    try {
        const response = await fetch('components/sidebar.html');
        const sidebarHTML = await response.text();
        const sidebarContainer = document.querySelector('.sidebar-container');
        
        if (sidebarContainer) {
            sidebarContainer.innerHTML = sidebarHTML;
            // Re-initialize sidebar after loading
            if (typeof Sidebar !== 'undefined') {
                Sidebar.init();
            }
            // Initialize mobile menu after sidebar loads
            if (typeof MobileMenu !== 'undefined') {
                MobileMenu.init();
            }
        }
    } catch (error) {
        console.error('Error loading sidebar:', error);
        // Fallback: create sidebar inline if fetch fails
        createSidebarFallback();
    }
}

function createSidebarFallback() {
    const sidebarContainer = document.querySelector('.sidebar-container');
    if (!sidebarContainer) return;
    
    sidebarContainer.innerHTML = `
        <aside class="sidebar">
            <div class="sidebar-header">
                <h1>Job Search</h1>
                <p>Campaign Manager</p>
            </div>
            <nav>
                <ul class="nav-menu">
                    <li class="nav-item">
                        <a href="dashboard.html" class="nav-link">
                            <i class="fas fa-chart-line"></i>
                            <span>Dashboard</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="campaigns.html" class="nav-link">
                            <i class="fas fa-folder-open"></i>
                            <span>Campaigns</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="resumes.html" class="nav-link">
                            <i class="fas fa-file-alt"></i>
                            <span>Resumes</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="cover_letters.html" class="nav-link">
                            <i class="fas fa-envelope"></i>
                            <span>Cover Letters</span>
                        </a>
                    </li>
                </ul>
            </nav>
            <div class="sidebar-footer">
                <div class="user-profile">
                    <div class="user-avatar">
                        <i class="fas fa-user"></i>
                    </div>
                    <div class="user-info">
                        <div class="user-name">
                            <span>John Doe</span>
                            <span class="user-badge">Free</span>
                        </div>
                        <div class="user-email">john.doe@example.com</div>
                    </div>
                </div>
            </div>
        </aside>
    `;
    
    if (typeof Sidebar !== 'undefined') {
        Sidebar.init();
    }
    // Initialize mobile menu after sidebar loads
    if (typeof MobileMenu !== 'undefined') {
        MobileMenu.init();
    }
}

// Load sidebar when DOM is ready
document.addEventListener('DOMContentLoaded', loadSidebar);

