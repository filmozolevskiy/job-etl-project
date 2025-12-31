/**
 * Campaign Details page specific functionality
 */

function formatTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

let cooldownTimerInterval = null;
let cooldownSeconds = 0;
let processingTimeout = null;

function updateCooldownTimer() {
    if (cooldownSeconds > 0) {
        cooldownSeconds--;
        const btn = document.getElementById('findJobsBtn');
        if (btn) {
            const timerSpan = btn.querySelector('.button-timer');
            if (timerSpan) {
                timerSpan.textContent = formatTime(cooldownSeconds);
            }
        }
    } else {
        if (cooldownTimerInterval) {
            clearInterval(cooldownTimerInterval);
            cooldownTimerInterval = null;
        }
        const btn = document.getElementById('findJobsBtn');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs';
        }
    }
}

function showError(message) {
    const status = document.getElementById('campaignStatus');
    const statusContainer = status.parentElement;
    let errorMsg = statusContainer.querySelector('.error-message');
    
    if (!errorMsg) {
        errorMsg = document.createElement('div');
        errorMsg.className = 'error-message';
        statusContainer.appendChild(errorMsg);
    }
    
    status.innerHTML = '<i class="fas fa-exclamation-circle"></i> Error';
    status.className = 'status-badge error';
    errorMsg.textContent = message;
}

function findJobs() {
    const btn = document.getElementById('findJobsBtn');
    const status = document.getElementById('campaignStatus');
    const statusContainer = status.parentElement;
    
    // Remove any existing error message
    const errorMsg = statusContainer.querySelector('.error-message');
    if (errorMsg) {
        errorMsg.remove();
    }
    
    // Simulate random error (10% chance for demo purposes)
    if (Math.random() < 0.1) {
        showError('Failed to connect to job search API. Please try again in a few moments.');
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs';
        return;
    }
    
    // Clear any existing cooldown timer
    if (cooldownTimerInterval) {
        clearInterval(cooldownTimerInterval);
    }
    
    // Clear any existing processing timeout
    if (processingTimeout) {
        clearTimeout(processingTimeout);
    }
    
    // Disable button
    btn.disabled = true;
    btn.innerHTML = '<span class="loading-spinner"></span> Starting...';
    
    // Simulate pipeline stages
    setTimeout(() => {
        status.innerHTML = '<i class="fas fa-search"></i> Looking for jobs...';
        status.className = 'status-badge processing';
    }, 1000);
    
    setTimeout(() => {
        status.innerHTML = '<i class="fas fa-cog fa-spin"></i> Processing jobs...';
        status.className = 'status-badge processing';
    }, 3000);
    
    setTimeout(() => {
        status.innerHTML = '<i class="fas fa-sort-amount-down"></i> Ranking jobs...';
        status.className = 'status-badge processing';
    }, 6000);
    
    setTimeout(() => {
        status.innerHTML = '<i class="fas fa-tasks"></i> Preparing results...';
        status.className = 'status-badge processing';
    }, 9000);
    
    // Complete processing after 12 seconds
    processingTimeout = setTimeout(() => {
        status.innerHTML = '<i class="fas fa-check-circle"></i> Done';
        status.className = 'status-badge done';
        
        // Set cooldown timer to 1 hour (3600 seconds)
        cooldownSeconds = 3600;
        btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs<span class="button-timer">' + formatTime(cooldownSeconds) + '</span>';
        
        // Start cooldown timer
        cooldownTimerInterval = setInterval(updateCooldownTimer, 1000);
    }, 12000);
}

// Ranking modal functions
function openRankingModal(companyName, jobTitle, score, breakdown) {
    document.getElementById('modalCompanyName').textContent = companyName;
    document.getElementById('modalJobPosition').textContent = jobTitle;
    document.getElementById('modalScore').textContent = score;
    
    const detailsContainer = document.getElementById('rankingDetails');
    detailsContainer.innerHTML = '';
    
    // Create ranking items
    Object.entries(breakdown).forEach(([factor, value]) => {
        const item = document.createElement('div');
        item.className = 'ranking-item';
        item.innerHTML = `
            <span class="ranking-factor">${factor}</span>
            <span class="ranking-value">${value}</span>
        `;
        detailsContainer.appendChild(item);
    });
    
    document.getElementById('rankingModal').classList.add('active');
}

function closeRankingModal() {
    document.getElementById('rankingModal').classList.remove('active');
}

function closeModalOnOverlay(event) {
    if (event.target === event.currentTarget) {
        closeRankingModal();
    }
}

// Initialize event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Find Jobs button
    const findJobsBtn = document.getElementById('findJobsBtn');
    if (findJobsBtn) {
        findJobsBtn.addEventListener('click', findJobs);
    }
    
    // Fit info icons - attach event listeners to all fit info icons
    const fitInfoIcons = document.querySelectorAll('.fit-info-icon');
    fitInfoIcons.forEach(icon => {
        // Get data from data attributes or parse from onclick (temporary)
        icon.addEventListener('click', function() {
            // Get ranking data from data attributes
            const companyName = this.getAttribute('data-company') || '';
            const jobTitle = this.getAttribute('data-job-title') || '';
            const score = parseInt(this.getAttribute('data-score') || '0');
            const breakdown = JSON.parse(this.getAttribute('data-breakdown') || '{}');
            
            if (companyName && jobTitle) {
                openRankingModal(companyName, jobTitle, score, breakdown);
            }
        });
    });
    
    // Modal overlay and close button
    const rankingModal = document.getElementById('rankingModal');
    if (rankingModal) {
        rankingModal.addEventListener('click', function(event) {
            if (event.target === this) {
                closeRankingModal();
            }
        });
        
        const modal = rankingModal.querySelector('.modal');
        if (modal) {
            modal.addEventListener('click', function(event) {
                event.stopPropagation();
            });
        }
        
        const closeBtn = rankingModal.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', closeRankingModal);
        }
    }
    
    // Close modal on Escape key
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeRankingModal();
        }
    });
});

