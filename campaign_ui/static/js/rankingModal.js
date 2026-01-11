/**
 * Shared ranking explanation modal functionality
 * 
 * Provides functions to display job ranking breakdowns in a modal dialog.
 * Used by both campaign details and job details pages.
 */

// Human-readable labels for ranking factors
const RANKING_FACTOR_LABELS = {
    'location_match': 'Location Match',
    'salary_match': 'Salary Match',
    'company_size_match': 'Company Size Match',
    'skills_match': 'Skills Match',
    'keyword_match': 'Title/Keyword Match',
    'employment_type_match': 'Employment Type Match',
    'seniority_match': 'Seniority Level Match',
    'remote_type_match': 'Remote Work Match',
    'recency': 'Posting Recency'
};

// Default max weights for each factor
// Note: These should match backend values in services/ranker/job_ranker.py
const RANKING_MAX_WEIGHTS = {
    'location_match': 15.0,
    'salary_match': 15.0,
    'company_size_match': 10.0,
    'skills_match': 15.0,
    'keyword_match': 15.0,
    'employment_type_match': 5.0,
    'seniority_match': 10.0,
    'remote_type_match': 10.0,
    'recency': 5.0
};

// Color thresholds for progress bars (percentage)
const COLOR_THRESHOLDS = {
    HIGH: 80,    // >= 80% = green (high)
    MEDIUM: 50   // >= 50% = yellow (medium), < 50% = gray (low)
};

/**
 * Opens the ranking explanation modal with job ranking breakdown.
 * 
 * @param {string} companyName - Company name to display
 * @param {string} jobTitle - Job title to display
 * @param {number} score - Overall rank score
 * @param {Object|string} breakdown - Ranking breakdown (object or JSON string)
 * @returns {boolean} True if modal was opened successfully, false otherwise
 */
function openRankingModal(companyName, jobTitle, score, breakdown) {
    const modal = document.getElementById('rankingModal');
    const detailsContainer = document.getElementById('rankingDetails');
    const companyNameEl = document.getElementById('modalCompanyName');
    const jobPositionEl = document.getElementById('modalJobPosition');
    const scoreEl = document.getElementById('modalScore');
    
    // Check if required DOM elements exist
    if (!modal || !detailsContainer || !companyNameEl || !jobPositionEl || !scoreEl) {
        console.error('Ranking modal: Required DOM elements not found');
        return false;
    }
    
    // Update modal header information
    companyNameEl.textContent = companyName;
    jobPositionEl.textContent = jobTitle;
    scoreEl.textContent = score;
    
    // Clear previous content
    detailsContainer.innerHTML = '';
    
    // Parse breakdown data (handle both string and object)
    let breakdownData = breakdown;
    if (typeof breakdown === 'string') {
        try {
            breakdownData = JSON.parse(breakdown);
        } catch (e) {
            console.error('Ranking modal: Error parsing breakdown JSON:', e);
            breakdownData = {};
        }
    }
    
    // Handle empty or missing breakdown
    if (!breakdownData || typeof breakdownData !== 'object' || Object.keys(breakdownData).length === 0) {
        const emptyState = document.createElement('div');
        emptyState.className = 'ranking-empty-state';
        emptyState.textContent = 'Ranking explanation not available';
        detailsContainer.appendChild(emptyState);
        modal.classList.add('active');
        return true;
    }
    
    // Convert factor keys to array, exclude total_score, and sort by contribution (highest first)
    const factors = Object.entries(breakdownData)
        .filter(([key]) => key !== 'total_score')
        .sort(([, valueA], [, valueB]) => {
            const numA = typeof valueA === 'number' ? valueA : parseFloat(valueA) || 0;
            const numB = typeof valueB === 'number' ? valueB : parseFloat(valueB) || 0;
            return numB - numA;
        });
    
    // Calculate actual max weight from breakdown data (accounts for custom campaign weights)
    // If a campaign has custom weights higher than defaults, we adjust the max to show correct percentage
    const actualMaxWeights = {};
    factors.forEach(([factor, value]) => {
        const numValue = typeof value === 'number' ? value : parseFloat(value) || 0;
        const defaultMax = RANKING_MAX_WEIGHTS[factor] || 15.0;
        // The actual max is at least the actual value (handles custom weights > default)
        actualMaxWeights[factor] = Math.max(defaultMax, numValue);
    });
    
    // Create progress bar items for each factor
    factors.forEach(([factor, value]) => {
        const numValue = typeof value === 'number' ? value : parseFloat(value) || 0;
        const maxWeight = actualMaxWeights[factor] || RANKING_MAX_WEIGHTS[factor] || 15.0;
        const percentage = maxWeight > 0 ? (numValue / maxWeight) * 100 : 0;
        
        // Determine color class based on contribution level
        let colorClass = 'low';
        if (percentage >= COLOR_THRESHOLDS.HIGH) {
            colorClass = 'high';
        } else if (percentage >= COLOR_THRESHOLDS.MEDIUM) {
            colorClass = 'medium';
        }
        
        // Get human-readable label
        const label = RANKING_FACTOR_LABELS[factor] || factor.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        
        // Create progress item using safe DOM methods
        const item = createRankingProgressItem(label, numValue, maxWeight, percentage, colorClass);
        detailsContainer.appendChild(item);
    });
    
    modal.classList.add('active');
    return true;
}

/**
 * Creates a ranking progress item element using safe DOM methods.
 * 
 * @param {string} label - Human-readable label for the factor
 * @param {number} numValue - Actual score value
 * @param {number} maxWeight - Maximum possible score
 * @param {number} percentage - Percentage value (0-100)
 * @param {string} colorClass - Color class ('high', 'medium', or 'low')
 * @returns {HTMLElement} The created progress item element
 */
function createRankingProgressItem(label, numValue, maxWeight, percentage, colorClass) {
    const item = document.createElement('div');
    item.className = 'ranking-progress-item';
    
    // Header with label and value
    const header = document.createElement('div');
    header.className = 'ranking-progress-header';
    
    const labelSpan = document.createElement('span');
    labelSpan.className = 'ranking-factor-label';
    labelSpan.textContent = label;
    
    const valueSpan = document.createElement('span');
    valueSpan.className = 'ranking-factor-value';
    valueSpan.textContent = `${numValue.toFixed(1)} / ${maxWeight.toFixed(1)}`;
    
    header.appendChild(labelSpan);
    header.appendChild(valueSpan);
    
    // Progress bar
    const progressBar = document.createElement('div');
    progressBar.className = 'ranking-progress-bar';
    progressBar.setAttribute('role', 'progressbar');
    progressBar.setAttribute('aria-valuenow', numValue.toFixed(1));
    progressBar.setAttribute('aria-valuemin', '0');
    progressBar.setAttribute('aria-valuemax', maxWeight.toFixed(1));
    progressBar.setAttribute('aria-label', `${label}: ${numValue.toFixed(1)} out of ${maxWeight.toFixed(1)}`);
    
    const progressFill = document.createElement('div');
    progressFill.className = `ranking-progress-fill ${colorClass}`;
    const clampedPercentage = Math.min(100, Math.max(0, percentage));
    progressFill.style.width = `${clampedPercentage}%`;
    
    progressBar.appendChild(progressFill);
    
    // Assemble item
    item.appendChild(header);
    item.appendChild(progressBar);
    
    return item;
}

/**
 * Closes the ranking explanation modal.
 * 
 * @returns {boolean} True if modal was closed successfully, false otherwise
 */
function closeRankingModal() {
    const modal = document.getElementById('rankingModal');
    if (!modal) {
        console.warn('Ranking modal: Modal element not found');
        return false;
    }
    modal.classList.remove('active');
    return true;
}

/**
 * Initializes event listeners for ranking modal on a page.
 * 
 * This function should be called during page initialization (e.g., in DOMContentLoaded).
 * It attaches click handlers to all .fit-info-icon elements and modal close handlers.
 * 
 * @param {string} modalId - ID of the modal element (default: 'rankingModal')
 */
function initializeRankingModal(modalId = 'rankingModal') {
    // Attach click handlers to all fit info icons
    const fitInfoIcons = document.querySelectorAll('.fit-info-icon');
    fitInfoIcons.forEach(icon => {
        // Check if listener is already attached (avoid duplicates)
        if (icon.dataset.rankingListenerAttached === 'true') {
            return;
        }
        
        icon.addEventListener('click', function() {
            const companyName = this.getAttribute('data-company') || '';
            const jobTitle = this.getAttribute('data-job-title') || '';
            const score = parseInt(this.getAttribute('data-score') || '0', 10);
            let breakdown = {};
            
            try {
                const breakdownStr = this.getAttribute('data-breakdown') || '{}';
                breakdown = JSON.parse(breakdownStr);
            } catch (e) {
                console.error('Ranking modal: Error parsing breakdown JSON:', e);
                breakdown = {};
            }
            
            if (companyName && jobTitle) {
                openRankingModal(companyName, jobTitle, score, breakdown);
            } else {
                console.warn('Ranking modal: Missing required data attributes (company-name, job-title)');
            }
        });
        
        icon.dataset.rankingListenerAttached = 'true';
    });
    
    // Modal overlay click handler (close when clicking outside)
    const rankingModal = document.getElementById(modalId);
    if (rankingModal) {
        rankingModal.addEventListener('click', function(event) {
            if (event.target === this) {
                closeRankingModal();
            }
        });
        
        // Prevent clicks inside modal from closing it
        const modalContent = rankingModal.querySelector('.modal');
        if (modalContent) {
            modalContent.addEventListener('click', function(event) {
                event.stopPropagation();
            });
        }
        
        // Close button handler
        const closeBtn = rankingModal.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', closeRankingModal);
        }
    }
    
    // Close modal on Escape key
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            const modal = document.getElementById(modalId);
            if (modal && modal.classList.contains('active')) {
                closeRankingModal();
            }
        }
    });
}
