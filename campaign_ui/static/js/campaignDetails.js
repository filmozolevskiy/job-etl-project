/**
 * Campaign Details page specific functionality
 * 
 * BUG FIX NOTE: The "Find Jobs" button text was not visible during Starting/Running states.
 * Root cause: common.js adds 'btn-loading' class to all form submit buttons on submit,
 * which applies 'color: transparent !important' hiding the text.
 * Solution: Added 'data-no-auto-loading' attribute to Find Jobs button to skip auto-loading,
 * allowing our custom button state handling to work correctly.
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
let statusPollInterval = null;
let pollingErrorCount = 0;  // Track consecutive polling errors
const MAX_POLLING_ERRORS = 3;  // Stop polling after this many consecutive errors
// Use Font Awesome spinner with fa-spin animation
const SPINNER_HTML = '<i class="fas fa-spinner fa-spin"></i>';
const COOLDOWN_HOURS = 1;  // 1 hour cooldown after DAG completion
const STATUS_POLL_INTERVAL = 2000;  // Poll status every 2 seconds
const PENDING_STATE_EXPIRY_MS = 5 * 60 * 1000;  // 5 minutes
const PENDING_STATE_RECENT_MS = 30 * 1000;  // 30 seconds - consider "recent" for double-trigger prevention
let isDagRunning = false;  // Track if DAG is currently running
// Track if last DAG was force-started (to skip cooldown)
if (typeof window.lastDagWasForced === 'undefined') {
    window.lastDagWasForced = false;
}

/**
 * Safely set pending state in localStorage with error handling
 */
function setPendingState(campaignId, isForceStart) {
    try {
        localStorage.setItem(`dag_pending_${campaignId}`, JSON.stringify({
            timestamp: Date.now(),
            forced: isForceStart
        }));
        return true;
    } catch (e) {
        // Continue without localStorage - UI will still update
        return false;
    }
}

/**
 * Safely get pending state from localStorage with error handling
 */
function getPendingState(campaignId) {
    try {
        const pendingState = localStorage.getItem(`dag_pending_${campaignId}`);
        if (!pendingState) {
            return null;
        }
        return JSON.parse(pendingState);
    } catch (e) {
        // Clear invalid state
        try {
            localStorage.removeItem(`dag_pending_${campaignId}`);
        } catch (clearError) {
        }
        return null;
    }
}

/**
 * Safely remove pending state from localStorage with error handling
 */
function removePendingState(campaignId) {
    try {
        localStorage.removeItem(`dag_pending_${campaignId}`);
        return true;
    } catch (e) {
        return false;
    }
}

/**
 * Start polling for campaign status with defensive cleanup
 */
function startPollingForCampaign(campaignId, dagRunId = null) {
    // Defensive cleanup: clear any existing interval first
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
        statusPollInterval = null;
    }
    
    // Start new polling interval
    statusPollInterval = setInterval(() => {
        pollCampaignStatus(campaignId, dagRunId);
    }, STATUS_POLL_INTERVAL);
    
    // Do immediate poll
    pollCampaignStatus(campaignId, dagRunId);
}

function updateCooldownTimer() {
    if (cooldownSeconds > 0) {
        // Safety check: cap cooldown at maximum (1 hour)
        const maxCooldownSeconds = COOLDOWN_HOURS * 3600;
        if (cooldownSeconds > maxCooldownSeconds) {
            cooldownSeconds = maxCooldownSeconds;
        }
        
        cooldownSeconds--;
        
        // Update localStorage with remaining cooldown time
        const campaignIdMatch = document.querySelector('form[action*="trigger-dag"]')?.action.match(/\/campaign\/(\d+)\/trigger-dag/);
        if (campaignIdMatch && cooldownSeconds > 0) {
            const campaignId = campaignIdMatch[1];
            const cooldownEndTime = Date.now() + (cooldownSeconds * 1000);
            localStorage.setItem(`cooldown_end_${campaignId}`, cooldownEndTime.toString());
        }
        
        const btn = document.getElementById('findJobsBtn');
        if (btn) {
            const timerSpan = btn.querySelector('.button-timer');
            if (timerSpan) {
                timerSpan.textContent = formatTime(cooldownSeconds);
            } else {
                // Create timer span if it doesn't exist
                const timerSpan = document.createElement('span');
                timerSpan.className = 'button-timer';
                timerSpan.textContent = formatTime(cooldownSeconds);
                btn.innerHTML = '<i class="fas fa-clock"></i> Cooldown: <span class="button-timer"></span>';
                btn.querySelector('.button-timer').textContent = formatTime(cooldownSeconds);
            }
        }
    } else {
        if (cooldownTimerInterval) {
            clearInterval(cooldownTimerInterval);
            cooldownTimerInterval = null;
        }
        const btn = document.getElementById('findJobsBtn');
        if (btn && !isDagRunning) {
            btn.disabled = false;
            btn.style.pointerEvents = '';
            btn.style.cursor = '';
            btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs';
            
            // Clear localStorage cooldown when it expires
            const campaignIdMatch = document.querySelector('form[action*="trigger-dag"]')?.action.match(/\/campaign\/(\d+)\/trigger-dag/);
            if (campaignIdMatch) {
                const campaignId = campaignIdMatch[1];
                localStorage.removeItem(`cooldown_end_${campaignId}`);
            }
            
            // Hide force start button when cooldown ends
            const forceBtn = document.getElementById('forceStartBtn');
            if (forceBtn) {
                forceBtn.style.display = 'none';
            }
        }
    }
}

function calculateCooldownSeconds(lastRunAt) {
    if (!lastRunAt) {
        return 0;  // No previous run, no cooldown
    }
    
    const lastRun = new Date(lastRunAt);
    const now = new Date();
    const diffMs = now - lastRun;
    const diffSeconds = Math.floor(diffMs / 1000);
    const cooldownTotalSeconds = COOLDOWN_HOURS * 3600;  // 1 hour in seconds
    
    // Handle edge cases:
    // 1. If lastRunAt is in the future (timezone issue), return 0 (no cooldown)
    // 2. If cooldown period has passed, return 0
    if (diffSeconds < 0) {
        return 0;  // Future timestamp - no cooldown
    }
    
    if (diffSeconds >= cooldownTotalSeconds) {
        return 0;  // Cooldown period has passed
    }
    
    // Cap the remaining cooldown at the maximum (1 hour) to prevent issues
    const remainingCooldown = cooldownTotalSeconds - diffSeconds;
    if (remainingCooldown > cooldownTotalSeconds) {
        return cooldownTotalSeconds;
    }
    
    return remainingCooldown;  // Remaining cooldown seconds
}

function initializeButtonState() {
    const btn = document.getElementById('findJobsBtn');
    if (!btn) return;
    
    // Check if we have campaign data from the page
    const campaignData = window.campaignData;
    if (!campaignData) {
        return;  // No campaign data available
    }
    
    const campaignIdMatch = document.querySelector('form[action*="trigger-dag"]')?.action.match(/\/campaign\/(\d+)\/trigger-dag/);
    if (!campaignIdMatch) {
        return;  // No campaign ID found
    }
    const campaignId = campaignIdMatch[1];
    
    // Check server state FIRST (most authoritative)
    // If server says DAG is running, clear any pending state and use server state
    const derivedStatus = campaignData.derivedRunStatus;
    if (derivedStatus && (derivedStatus.status === 'running' || derivedStatus.status === 'pending')) {
        // Check if the DAG run is recent (within last hour)
        let isRecent = false;
        if (derivedStatus.dag_run_id) {
            try {
                // Parse dag_run_id as date (format: YYYY-MM-DDTHH:mm:ss+ZZ:ZZ)
                const dateStr = derivedStatus.dag_run_id.replace('manual__', '').split('+')[0];
                const runDate = new Date(dateStr + 'Z'); // Assume UTC
                const now = new Date();
                const diffMs = now - runDate;
                const oneHourMs = 60 * 60 * 1000;
                isRecent = diffMs < oneHourMs;
            } catch (e) {
                isRecent = true; // If can't parse, assume recent
            }
        } else {
            // No dag_run_id means DAG has never been run or there's no active run
            // Check if there's a recent lastRunAt to determine if this is truly pending
            const lastRunAt = campaignData.lastRunAt;
            if (lastRunAt) {
                try {
                    const lastRun = new Date(lastRunAt);
                    const now = new Date();
                    const diffMs = now - lastRun;
                    const oneHourMs = 60 * 60 * 1000;
                    // If lastRunAt is recent, treat as potentially pending
                    // Otherwise, treat as stale (campaign reactivated after old run)
                    isRecent = diffMs < oneHourMs;
                } catch (e) {
                    isRecent = false; // If can't parse, assume stale
                }
            } else {
                // No dag_run_id and no lastRunAt - DAG never run, not truly pending
                isRecent = false;
            }
        }

        if (isRecent) {
            // Server says DAG is running - clear any pending state (server is authoritative)
            removePendingState(campaignId);

            // DAG is running - disable button and show status
            isDagRunning = true;
            btn.disabled = true;
            btn.style.pointerEvents = 'none';
            btn.style.cursor = 'not-allowed';
            if (derivedStatus.status === 'running') {
                btn.innerHTML = `${SPINNER_HTML} Running...`;
            } else {
                btn.innerHTML = `${SPINNER_HTML} Pending...`;
            }

            // Update status badge to reflect DAG state
            const status = document.getElementById('campaignStatus');
            if (status && derivedStatus) {
                if (derivedStatus.status === 'running') {
                    status.innerHTML = '<i class="fas fa-cog fa-spin"></i> Running';
                    status.className = 'status-badge processing';
                } else if (derivedStatus.status === 'pending') {
                    status.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Pending';
                    status.className = 'status-badge processing';
                }
            }

            // Hide force start button when DAG is running (force start only during cooldown)
            const forceBtn = document.getElementById('forceStartBtn');
            if (forceBtn) {
                forceBtn.style.display = 'none';
            }
            
            // Start polling if not already polling
            if (!statusPollInterval) {
                const dagRunId = derivedStatus.dag_run_id || null;
                startPollingForCampaign(campaignId, dagRunId);
            }
            return;
        } else {
            // DAG run is old or stale pending status - clear any stale pending state
            removePendingState(campaignId);
            // Reset isDagRunning since DAG is not currently running
            isDagRunning = false;
            
            // Update status card to show Active/Inactive instead of stale "Pending"
            const status = document.getElementById('campaignStatus');
            if (status) {
                const isActive = campaignData.isActive;
                if (isActive) {
                    status.innerHTML = '<i class="fas fa-play"></i> Active';
                    status.className = 'status-badge processing';
                } else {
                    status.innerHTML = '<i class="fas fa-pause"></i> Paused';
                    status.className = 'status-badge paused';
                }
            }
        }
    }

    // If server says no DAG running (or DAG completed/failed), clear any pending state
    // Only restore pending state if server has no status info at all (DAG never run)
    const shouldRestorePending = !derivedStatus || (derivedStatus.status !== 'running' && derivedStatus.status !== 'pending');
    
    if (shouldRestorePending) {
        // Clear pending state if server says DAG is not running
        removePendingState(campaignId);
        // IMPORTANT: Reset isDagRunning to false when server says DAG is not running
        // This prevents stale state from blocking new DAG starts
        isDagRunning = false;
    }

    // Only check localStorage for pending state if server has no status info
    // (user may have refreshed after clicking but before server updated)
    if (!derivedStatus) {
        const pending = getPendingState(campaignId);
        
        if (pending) {
            const pendingAge = Date.now() - pending.timestamp;
            
            // Only restore if pending state is recent (less than expiry time)
            // This prevents stale pending states from persisting indefinitely
            if (pendingAge < PENDING_STATE_EXPIRY_MS) {
                isDagRunning = true;
                btn.disabled = true;
                btn.innerHTML = `${SPINNER_HTML} Starting...`;
                
                // Restore force start flag if this was a force start
                if (pending.forced) {
                    window.lastDagWasForced = true;
                }
                
                const status = document.getElementById('campaignStatus');
                if (status) {
                    status.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
                    status.className = 'status-badge processing';
                }
                
                // Hide force start button (it's already hidden, but ensure it stays hidden)
                const forceBtn = document.getElementById('forceStartBtn');
                if (forceBtn) {
                    forceBtn.style.display = 'none';
                }
                
                // Start polling immediately
                if (!statusPollInterval) {
                    startPollingForCampaign(campaignId, null);
                }
            } else {
                // Stale pending state - remove it
                removePendingState(campaignId);
                // Also reset isDagRunning since pending state is stale
                isDagRunning = false;
            }
        } else {
            // No pending state - ensure isDagRunning is false
            isDagRunning = false;
        }
    }
    
    // DAG is not running - check cooldown
    // First check localStorage for cooldown (set before page reload)
    // (campaignIdMatch already defined above)
    let remainingCooldown = 0;
    
    if (campaignIdMatch) {
        const campaignId = campaignIdMatch[1];
        const storedCooldownEnd = localStorage.getItem(`cooldown_end_${campaignId}`);
        if (storedCooldownEnd) {
            const cooldownEndTime = parseInt(storedCooldownEnd, 10);
            const now = Date.now();
            if (cooldownEndTime > now) {
                // Still in cooldown from localStorage
                remainingCooldown = Math.floor((cooldownEndTime - now) / 1000);
            } else {
                // Cooldown expired, remove from localStorage
                localStorage.removeItem(`cooldown_end_${campaignId}`);
            }
        }
    }

    // If no cooldown from localStorage, check lastRunAt from database
    if (remainingCooldown === 0) {
        const lastRunAt = campaignData.lastRunAt;
        if (lastRunAt) {
            remainingCooldown = calculateCooldownSeconds(lastRunAt);
        }
    }
    
    if (remainingCooldown > 0) {
        // Still in cooldown period
        cooldownSeconds = remainingCooldown;
        btn.disabled = true;
        btn.style.pointerEvents = 'none';
        btn.style.cursor = 'not-allowed';
        btn.innerHTML = '<i class="fas fa-clock"></i> Cooldown: <span class="button-timer"></span>';
        btn.querySelector('.button-timer').textContent = formatTime(cooldownSeconds);
        
        // Show force start button for admins if in cooldown
        const forceBtn = document.getElementById('forceStartBtn');
        if (forceBtn) {
            // Only show if user is admin (check if button exists in DOM - it's only rendered for admins)
            forceBtn.style.display = 'inline-block';
        }
        
        // Start cooldown timer
        if (!cooldownTimerInterval) {
            cooldownTimerInterval = setInterval(updateCooldownTimer, 1000);
        }
        return;
    }
    
    // No cooldown, enable button
    btn.disabled = false;
    btn.style.pointerEvents = '';
    btn.style.cursor = '';
    btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs';
}

function showError(message) {
    const status = document.getElementById('campaignStatus');
    const statusContainer = status.parentElement;
    let errorMsg = statusContainer.querySelector('.error-message');
    
    if (!errorMsg) {
        errorMsg = document.createElement('div');
        errorMsg.className = 'error-message';
        // Insert error message after the form (not just append) to maintain proper order
        const form = statusContainer.querySelector('form');
        if (form && form.nextSibling) {
            statusContainer.insertBefore(errorMsg, form.nextSibling);
        } else {
            statusContainer.appendChild(errorMsg);
        }
    }
    
    status.innerHTML = '<i class="fas fa-exclamation-circle"></i> Error';
    status.className = 'status-badge error';
    errorMsg.textContent = message;
    
}

function updateStatusCard(statusData) {
    const status = document.getElementById('campaignStatus');
    if (!status) {
        return;
    }
    
    const statusValue = statusData.status;
    const completedTasks = statusData.completed_tasks || [];
    const failedTasks = statusData.failed_tasks || [];
    
    // Remove any existing error message
    const statusContainer = status.parentElement;
    if (!statusContainer) {
        return;
    }
    const errorMsg = statusContainer.querySelector('.error-message');
    if (errorMsg) {
        errorMsg.remove();
    }
    
    // Map task names to user-friendly stage names
    const taskStageMap = {
        'extract_job_postings': 'Looking for jobs...',
        'normalize_jobs': 'Processing jobs...',
        'rank_jobs': 'Ranking jobs...',
        'send_notifications': 'Preparing results...'
    };
    
    // Update button state to match status
    const btn = document.getElementById('findJobsBtn');
    if (statusValue === 'running' || statusValue === 'pending') {
        isDagRunning = true;
        if (btn) {
            btn.disabled = true;
            btn.style.pointerEvents = 'none';
            btn.style.cursor = 'not-allowed';
            if (statusValue === 'running') {
                btn.innerHTML = `${SPINNER_HTML} Running...`;
            } else {
                btn.innerHTML = `${SPINNER_HTML} Pending...`;
            }
        }
        // Hide force start button when DAG is running/pending (force start only during cooldown)
        const forceBtn = document.getElementById('forceStartBtn');
        if (forceBtn) {
            forceBtn.style.display = 'none';
        }
    }
    
    if (statusValue === 'success') {
        // Don't show "Done" - let it revert to Active/Inactive after refresh
        // Just show a brief success indicator, then the page will refresh
        status.innerHTML = '<i class="fas fa-check-circle"></i> Complete';
        status.className = 'status-badge done';
    } else if (statusValue === 'error') {
        status.innerHTML = '<i class="fas fa-exclamation-circle"></i> Error';
        status.className = 'status-badge error';
        if (failedTasks.length > 0) {
            const errorMsg = document.createElement('div');
            errorMsg.className = 'error-message';
            errorMsg.textContent = `Failed: ${failedTasks.join(', ')}`;
            statusContainer.appendChild(errorMsg);
        }
    } else if (statusValue === 'running') {
        // Show current stage based on last completed task
        let currentStage = 'Starting...';
        if (completedTasks.length > 0) {
            const lastTask = completedTasks[completedTasks.length - 1];
            currentStage = taskStageMap[lastTask] || 'Processing...';
        }
        
        if (completedTasks.includes('extract_job_postings') && !completedTasks.includes('normalize_jobs')) {
            status.innerHTML = '<i class="fas fa-search"></i> ' + currentStage;
        } else if (completedTasks.includes('normalize_jobs') && !completedTasks.includes('rank_jobs')) {
            status.innerHTML = '<i class="fas fa-cog fa-spin"></i> ' + currentStage;
        } else if (completedTasks.includes('rank_jobs') && !completedTasks.includes('send_notifications')) {
            status.innerHTML = '<i class="fas fa-sort-amount-down"></i> ' + currentStage;
        } else {
            status.innerHTML = '<i class="fas fa-tasks"></i> ' + currentStage;
        }
        status.className = 'status-badge processing';
    } else { // pending
        // If pending with no dag_run_id, show "Starting..."
        // If pending with dag_run_id, show "Waiting for tasks..."
        if (statusData.dag_run_id) {
            status.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Waiting for tasks...';
        } else {
            status.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
        }
        status.className = 'status-badge processing';
    }
}

function stopStatusPolling() {
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
        statusPollInterval = null;
    }
    pollingErrorCount = 0;  // Reset error count when stopping polling
}

function resetButtonState() {
    const btn = document.getElementById('findJobsBtn');
    const status = document.getElementById('campaignStatus');
    if (btn) {
        // Restore button dimensions and transitions to auto
        btn.style.width = '';
        btn.style.minWidth = '';
        btn.style.height = '';
        btn.style.minHeight = '';
        btn.style.transition = '';
        btn.style.transform = '';
        
        if (!isDagRunning) {
            // Only reset if DAG is not running
            const campaignData = window.campaignData;
            if (campaignData && campaignData.lastRunAt) {
                const remainingCooldown = calculateCooldownSeconds(campaignData.lastRunAt);
                if (remainingCooldown > 0) {
                    // Still in cooldown, don't enable button
                    cooldownSeconds = remainingCooldown;
                    btn.disabled = true;
                    btn.style.pointerEvents = 'none';
                    btn.style.cursor = 'not-allowed';
                    btn.innerHTML = '<i class="fas fa-clock"></i> Cooldown: <span class="button-timer"></span>';
                    btn.querySelector('.button-timer').textContent = formatTime(cooldownSeconds);
                    
                    // Show force start button for admins if in cooldown
                    const forceBtn = document.getElementById('forceStartBtn');
                    if (forceBtn) {
                        forceBtn.style.display = 'inline-block';
                    }
                    
                    if (!cooldownTimerInterval) {
                        cooldownTimerInterval = setInterval(updateCooldownTimer, 1000);
                    }
                    return;
                }
            }
            btn.disabled = false;
            btn.style.pointerEvents = '';
            btn.style.cursor = '';
            btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs';
        }
    }
}

function pollCampaignStatus(campaignId, dagRunId = null) {
    const url = `/campaign/${campaignId}/status${dagRunId ? `?dag_run_id=${dagRunId}` : ''}`;
    
    fetch(url, {
        credentials: 'include',  // Include cookies for authentication
        headers: {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            // Check if response is actually JSON (not HTML redirect)
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new Error('Response is not JSON');
            }
            return response.json();
        })
        .then(data => {
            
            // Reset error count on successful response
            pollingErrorCount = 0;
            
            // Clear pending state if we got any valid status response (DAG is no longer "pending")
            // This handles all statuses including any future ones
            if (data.status) {
                removePendingState(campaignId);
            }
            
            // Check if jobs are available (rank_jobs completed) - refresh page immediately
            // Don't wait for full DAG completion (dbt_tests, notify_daily can run in background)
            if (data.jobs_available && !window.jobsAlreadyRefreshed) {
                // Mark that we've triggered a refresh to avoid multiple refreshes
                window.jobsAlreadyRefreshed = true;
                
                // Show brief "Jobs Available" message, then refresh
                const status = document.getElementById('campaignStatus');
                if (status) {
                    status.innerHTML = '<i class="fas fa-check-circle"></i> Jobs Available';
                    status.className = 'status-badge done';
                }
                
                // Stop polling for jobs availability (but DAG may still be running)
                // We'll continue polling for final DAG status in the background
                // Wait a moment for jobs to be fully written to database
                setTimeout(() => {
                    // Refresh current campaign page to show updated jobs
                    window.location.reload();
                }, 2000); // 2 seconds should be enough for rank_jobs to write data
                return;
            }
            
            // Update status card only if not complete (or if error)
            // If complete and successful, don't update - let page refresh show Active
            if (data.is_complete && data.status === 'success') {
                // Show brief "Complete" message
                const status = document.getElementById('campaignStatus');
                if (status) {
                    status.innerHTML = '<i class="fas fa-check-circle"></i> Complete';
                    status.className = 'status-badge done';
                }
                
                stopStatusPolling();
                isDagRunning = false;
                
                // Only start cooldown if DAG was not force-started
                // Use window variable to track forced starts across page reloads
                if (!window.lastDagWasForced) {
                    // Start 1-hour cooldown timer (only after DAG completes, not during)
                    cooldownSeconds = COOLDOWN_HOURS * 3600;  // 1 hour in seconds
                    
                    // Store cooldown end time in localStorage before reloading
                    // This ensures cooldown persists across page reloads even if lastRunAt isn't updated yet
                    const cooldownEndTime = Date.now() + (cooldownSeconds * 1000);
                    const campaignIdMatch = document.querySelector('form[action*="trigger-dag"]')?.action.match(/\/campaign\/(\d+)\/trigger-dag/);
                    if (campaignIdMatch) {
                        const campaignId = campaignIdMatch[1];
                        try {
                            localStorage.setItem(`cooldown_end_${campaignId}`, cooldownEndTime.toString());
                        } catch (e) {
                        }
                    }
                    
                    const btn = document.getElementById('findJobsBtn');
                    if (btn) {
                        // Reset inline styles before applying cooldown state
                        btn.style.width = '';
                        btn.style.minWidth = '';
                        btn.style.height = '';
                        btn.style.minHeight = '';
                        btn.style.transition = '';
                        btn.style.transform = '';
                        
                        btn.disabled = true;
                        btn.style.pointerEvents = 'none';
                        btn.style.cursor = 'not-allowed';
                        btn.innerHTML = '<i class="fas fa-clock"></i> Cooldown: <span class="button-timer"></span>';
                        btn.querySelector('.button-timer').textContent = formatTime(cooldownSeconds);
                        
                        // Show force start button for admins if in cooldown
                        const forceBtn = document.getElementById('forceStartBtn');
                        if (forceBtn) {
                            forceBtn.style.display = 'inline-block';
                        }
                        
                        // Start cooldown timer immediately so user can see it counting down
                        if (!cooldownTimerInterval) {
                            cooldownTimerInterval = setInterval(updateCooldownTimer, 1000);
                        }
                    }
                    
                    // Wait longer for jobs and data to be fully written to database
                    // Show cooldown for at least 2 seconds before reloading so user can see it
                    setTimeout(() => {
                        // Refresh current campaign page to show updated jobs and Active status
                        window.location.reload();
                    }, 5000); // Increased to 5 seconds to ensure data is written AND user sees cooldown
                } else {
                    // Force start - no cooldown, just reset button
                    window.lastDagWasForced = false; // Reset flag
                    
                    // Clear any stored cooldown for this campaign
                    const campaignIdMatch = document.querySelector('form[action*="trigger-dag"]')?.action.match(/\/campaign\/(\d+)\/trigger-dag/);
                    if (campaignIdMatch) {
                        const campaignId = campaignIdMatch[1];
                        localStorage.removeItem(`cooldown_end_${campaignId}`);
                    }
                    
                    const btn = document.getElementById('findJobsBtn');
                    if (btn) {
                        // Reset inline styles before enabling
                        btn.style.width = '';
                        btn.style.minWidth = '';
                        btn.style.height = '';
                        btn.style.minHeight = '';
                        btn.style.transition = '';
                        btn.style.transform = '';
                        
                        btn.disabled = false;
                        btn.style.pointerEvents = '';
                        btn.style.cursor = '';
                        btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs';
                    }
                    // Hide force button
                    const forceBtn = document.getElementById('forceStartBtn');
                    if (forceBtn) {
                        forceBtn.style.display = 'none';
                    }
                    
                    // Wait longer for jobs and data to be fully written to database
                    setTimeout(() => {
                        // Refresh current campaign page to show updated jobs and Active status
                        window.location.reload();
                    }, 3000); // 3 seconds for force start (no cooldown to show)
                }
                return;
            } else if (data.is_complete && data.status === 'error') {
                // Update status card for errors
                updateStatusCard(data);
                stopStatusPolling();
                isDagRunning = false;
                
                // Only start cooldown if DAG was not force-started
                const wasForced = data.forced || false;
                
                if (!wasForced) {
                    // Start 1-hour cooldown timer even on error (only after DAG completes)
                    cooldownSeconds = COOLDOWN_HOURS * 3600;  // 1 hour in seconds
                    
                    // Store cooldown end time in localStorage
                    const cooldownEndTime = Date.now() + (cooldownSeconds * 1000);
                    const campaignIdMatch = document.querySelector('form[action*="trigger-dag"]')?.action.match(/\/campaign\/(\d+)\/trigger-dag/);
                    if (campaignIdMatch) {
                        const campaignId = campaignIdMatch[1];
                        localStorage.setItem(`cooldown_end_${campaignId}`, cooldownEndTime.toString());
                    }
                    
                    const btn = document.getElementById('findJobsBtn');
                    if (btn) {
                        // Reset inline styles before applying cooldown state
                        btn.style.width = '';
                        btn.style.minWidth = '';
                        btn.style.height = '';
                        btn.style.minHeight = '';
                        btn.style.transition = '';
                        btn.style.transform = '';
                        
                        btn.disabled = true;
                        btn.style.pointerEvents = 'none';
                        btn.style.cursor = 'not-allowed';
                        btn.innerHTML = '<i class="fas fa-clock"></i> Cooldown: <span class="button-timer"></span>';
                        btn.querySelector('.button-timer').textContent = formatTime(cooldownSeconds);
                        
                        // Show force start button for admins if in cooldown
                        const forceBtn = document.getElementById('forceStartBtn');
                        if (forceBtn) {
                            forceBtn.style.display = 'inline-block';
                        }
                        
                        // Start cooldown timer
                        if (!cooldownTimerInterval) {
                            cooldownTimerInterval = setInterval(updateCooldownTimer, 1000);
                        }
                    }
                } else {
                    // Force start - no cooldown, just reset button
                    window.lastDagWasForced = false; // Reset flag
                    
                    // Clear any stored cooldown for this campaign
                    const campaignIdMatch = document.querySelector('form[action*="trigger-dag"]')?.action.match(/\/campaign\/(\d+)\/trigger-dag/);
                    if (campaignIdMatch) {
                        const campaignId = campaignIdMatch[1];
                        localStorage.removeItem(`cooldown_end_${campaignId}`);
                    }
                    
                    const btn = document.getElementById('findJobsBtn');
                    if (btn) {
                        // Reset inline styles before enabling
                        btn.style.width = '';
                        btn.style.minWidth = '';
                        btn.style.height = '';
                        btn.style.minHeight = '';
                        btn.style.transition = '';
                        btn.style.transform = '';
                        
                        btn.disabled = false;
                        btn.style.pointerEvents = '';
                        btn.style.cursor = '';
                        btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs';
                    }
                    const forceBtn = document.getElementById('forceStartBtn');
                    if (forceBtn) {
                        forceBtn.style.display = 'none';
                    }
                }
                return;
            }
            
            // Update status card for running/pending states
            // But if status is "pending" without dag_run_id, don't change UI back to "Starting..."
            // since we already confirmed the DAG started and set it to "Running..."
            if (data.status === 'pending' && !data.dag_run_id) {
                // DAG hasn't started yet or no metrics created, keep polling
                // Don't update status card - keep showing "Running..." until we get real status
                return; // Continue polling
            }
            
            // Update status card for running states or pending with dag_run_id
            updateStatusCard(data);
            
            // If status is running or pending with dag_run_id, continue polling (already set up)
        })
        .catch(error => {
            console.error('Error polling campaign status:', error);
            pollingErrorCount++;
            
            // If too many consecutive errors, stop polling and reset
            if (pollingErrorCount >= MAX_POLLING_ERRORS) {
                console.error(`Stopped polling after ${MAX_POLLING_ERRORS} consecutive errors`);
                stopStatusPolling();
                resetButtonState();
                
                // Show error message to user
                showError('Failed to check campaign status. Please refresh the page and try again.');
                
                // Update status card to show error
                const status = document.getElementById('campaignStatus');
                if (status) {
                    status.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Status check failed';
                    status.className = 'status-badge error';
                }
            } else {
                // Update status to show there's an issue, but continue polling
                const status = document.getElementById('campaignStatus');
                if (status && pollingErrorCount === 1) {
                    // Only show error on first failure, don't spam the UI
                }
            }
        });
}

function findJobs(event) {
    // Prevent default form submission if event is provided
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    
    const form = document.querySelector('form[action*="trigger-dag"]');
    const btn = document.getElementById('findJobsBtn');
    const status = document.getElementById('campaignStatus');
    
    if (!form || !btn || !status) {
        console.error('Required elements not found');
        return false; // Return false to prevent default if event is not available
    }
    
    // Check if this is a force start FIRST (before other checks)
    const isForceStart = event && event.target && event.target.id === 'forceStartBtn';
    
    if (isForceStart) {
    }
    
    // Check if DAG is running (even for force start)
    if (isDagRunning) {
        return false;
    }
    
    // Check cooldown (unless this is a force start) - do this BEFORE checking button disabled state
    const campaignData = window.campaignData;
    let remainingCooldown = 0;
    if (!isForceStart && campaignData && campaignData.lastRunAt) {
        remainingCooldown = calculateCooldownSeconds(campaignData.lastRunAt);
        if (remainingCooldown > 0) {
            return false;
        }
    }
    
    // Check if button is disabled - but allow if DAG is not running and no cooldown
    if (btn.disabled && !isForceStart) {
        // If button is disabled but DAG is not running and no cooldown, re-enable it
        if (!isDagRunning && remainingCooldown === 0) {
            btn.disabled = false;
            btn.style.pointerEvents = '';
            btn.style.cursor = '';
            btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs';
        } else {
            return false;
        }
    }
    
    // Double-check: prevent if DAG is running (even for force start)
    if (isDagRunning) {
        return false;
    }
    
    // Get campaign ID from form action
    const campaignIdMatch = form.action.match(/\/campaign\/(\d+)\/trigger-dag/);
    if (!campaignIdMatch) {
        console.error('Could not extract campaign ID from form');
        return false;
    }
    const campaignId = campaignIdMatch[1];
    
    // Check if there's already a recent pending state (prevent double-trigger)
    // This handles rapid clicks before isDagRunning is set
    const existingPending = getPendingState(campaignId);
    if (existingPending) {
        const pendingAge = Date.now() - existingPending.timestamp;
        if (pendingAge < PENDING_STATE_RECENT_MS) {
            return false;
        }
    }
    
    // Remove any existing error message
    const statusContainer = status.parentElement;
    const errorMsg = statusContainer.querySelector('.error-message');
    if (errorMsg) {
        errorMsg.remove();
    }
    
    // Clear any existing timers
    if (cooldownTimerInterval) {
        clearInterval(cooldownTimerInterval);
        cooldownTimerInterval = null;
    }
    if (processingTimeout) {
        clearTimeout(processingTimeout);
        processingTimeout = null;
    }
    stopStatusPolling();
    
    // Set force flag if this is a force start
    if (isForceStart) {
        window.lastDagWasForced = true;
    }
    
    // Set running state immediately to prevent double-clicks
    isDagRunning = true;
    
    // Disable button immediately to prevent clicks
    btn.disabled = true;
    btn.style.pointerEvents = 'none';
    btn.style.cursor = 'not-allowed';
    
    // Preserve button dimensions before changing content to minimize layout shift
    const currentWidth = btn.offsetWidth;
    const currentHeight = btn.offsetHeight;
    
    // Apply all changes in one batch to prevent visual flicker:
    // 1. Remove transitions so dimension lock is instant
    // 2. Lock dimensions
    // 3. Update content with animation
    // 4. Apply disabled state
    btn.style.transition = 'none';
    btn.style.transform = 'none';
    btn.style.width = `${currentWidth}px`;
    btn.style.minWidth = `${currentWidth}px`;
    btn.style.height = `${currentHeight}px`;
    btn.style.minHeight = `${currentHeight}px`;
    
    // Use FA spinner with animation - set content before disabling
    btn.innerHTML = `${SPINNER_HTML} Starting...`;
    
    // Force reflow to ensure content is rendered
    void btn.offsetHeight;
    
    status.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
    status.className = 'status-badge processing';
    
    // Store pending state in localStorage immediately (before API call completes)
    // This ensures the state persists if user refreshes the page
    setPendingState(campaignId, isForceStart);
    
    // Hide force start button if it exists
    const forceBtn = document.getElementById('forceStartBtn');
    if (forceBtn) {
        forceBtn.style.display = 'none';
    }
    
    // Submit form via AJAX
    const formData = new FormData(form);
    if (isForceStart) {
        formData.append('force', 'true');
    }
    
    // Set a timeout for the fetch request (30 seconds)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
    
    fetch(form.action, {
        method: 'POST',
        body: formData,
        credentials: 'include',  // Include cookies for authentication
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        },
        signal: controller.signal
    })
    .then(response => {
        clearTimeout(timeoutId); // Clear timeout on successful response
        
        // Check if response is HTML (redirect) or JSON
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            if (!response.ok) {
                // Try to parse error message from JSON response
                return response.json().then(data => {
                    // Handle specific HTTP status codes
                    if (response.status === 409) {
                        // 409 Conflict (DAG already running)
                        const error = new Error(data.error || 'DAG is already running');
                        error.status = 409;
                        throw error;
                    } else if (response.status === 503) {
                        // 503 Service Unavailable (Airflow connection error)
                        const error = new Error(data.error || 'Airflow service is unavailable');
                        error.status = 503;
                        throw error;
                    } else if (response.status === 504) {
                        // 504 Gateway Timeout (Airflow timeout)
                        const error = new Error(data.error || 'Request to Airflow timed out');
                        error.status = 504;
                        throw error;
                    } else if (response.status === 502) {
                        // 502 Bad Gateway (Airflow HTTP error)
                        const error = new Error(data.error || 'Airflow API error');
                        error.status = 502;
                        throw error;
                    }
                    throw new Error(data.error || `HTTP error! status: ${response.status}`);
                }).catch((err) => {
                    // If parsing failed, create error with status code
                    if (err.status) {
                        throw err;
                    }
                    throw new Error(`HTTP error! status: ${response.status}`);
                });
            }
            return response.json();
        }
        // If HTML redirect, check if it's an error
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        // If HTML redirect, that's fine - we'll start polling anyway
        return { success: true };
    })
    .then(data => {
        
        // Track if this was a forced start (already set above, but confirm from response)
        if (data.forced) {
            window.lastDagWasForced = true;
        }
        
        const dagRunId = data.dag_run_id || null;
        
        // Clear pending state from localStorage since we got confirmation
        removePendingState(campaignId);
        
        // Update UI immediately to show "Running" instead of "Starting"
        // This prevents the weird pending animation after DAG is confirmed started
        btn.innerHTML = `${SPINNER_HTML} Running...`;
        status.innerHTML = '<i class="fas fa-cog fa-spin"></i> Running...';
        status.className = 'status-badge processing';
        
        // Start polling immediately (no delay - we want immediate feedback)
        if (!statusPollInterval) {
            startPollingForCampaign(campaignId, dagRunId);
        }
    })
    .catch(error => {
        clearTimeout(timeoutId); // Clear timeout on error
        console.error('Error triggering DAG:', error);
        
        // Handle specific error cases
        if (error.name === 'AbortError' || error.message.includes('aborted')) {
            // Request timeout
            showError('Request timed out. The DAG may have been triggered. Please check the status or try again.');
            // Don't clear pending state - DAG might have been triggered
            // Keep polling to check if DAG actually started
            if (!statusPollInterval) {
                const campaignIdMatch = form.action.match(/\/campaign\/(\d+)\/trigger-dag/);
                if (campaignIdMatch) {
                    const campaignId = campaignIdMatch[1];
                    startPollingForCampaign(campaignId, null);
                }
            }
            // Don't reset button state - keep it disabled and show "Starting..."
            return;
        }
        
        // Handle 409 Conflict (DAG already running)
        if (error.status === 409 || (error.message && error.message.includes('already in progress'))) {
            showError('A DAG run is already in progress. Please wait for it to complete.');
            // Don't reset button state - keep it disabled since DAG is running
            // Clear pending state (DAG is already running, not pending)
            removePendingState(campaignId);
            // Start polling to track the existing DAG run
            const campaignIdMatch = form.action.match(/\/campaign\/(\d+)\/trigger-dag/);
            if (campaignIdMatch) {
                const campaignId = campaignIdMatch[1];
                // Start polling to track the existing DAG
                if (!statusPollInterval) {
                    startPollingForCampaign(campaignId, null);
                }
            }
            return;
        }
        
        // Handle 503 Service Unavailable (Airflow connection error)
        if (error.status === 503 || (error.message && error.message.includes('unavailable'))) {
            showError('Cannot connect to Airflow. Please check if Airflow is running and try again.');
            // Clear pending state on connection error
            removePendingState(campaignId);
            isDagRunning = false;
            resetButtonState();
            stopStatusPolling();
            return;
        }
        
        // Handle 504 Gateway Timeout
        if (error.status === 504 || (error.message && error.message.includes('timed out'))) {
            showError('Request to Airflow timed out. The DAG may have been triggered. Please check Airflow UI or try again.');
            // Don't clear pending state - DAG might have been triggered
            // Keep polling to check if DAG actually started
            if (!statusPollInterval) {
                const campaignIdMatch = form.action.match(/\/campaign\/(\d+)\/trigger-dag/);
                if (campaignIdMatch) {
                    const campaignId = campaignIdMatch[1];
                    startPollingForCampaign(campaignId, null);
                }
            }
            // Don't reset button state - keep it disabled and show "Starting..."
            return;
        }
        
        // Handle 502 Bad Gateway (Airflow API error)
        if (error.status === 502 || (error.message && error.message.includes('Airflow'))) {
            showError('Airflow API error. Please check Airflow logs and try again.');
            // Clear pending state on API error
            removePendingState(campaignId);
            isDagRunning = false;
            resetButtonState();
            stopStatusPolling();
            return;
        }
        
        // Generic error handling
        const errorMessage = error.message || 'Failed to trigger DAG. Please try again.';
        showError(errorMessage);
        // Clear pending state on error
        removePendingState(campaignId);
        isDagRunning = false;
        resetButtonState();
        stopStatusPolling();
        
        // Reset status card to show Active/Inactive based on campaign state
        const status = document.getElementById('campaignStatus');
        if (status) {
            // Get initial status from the page
            const campaignData = window.campaignData || {};
            const initialStatus = campaignData.derivedRunStatus;
            const isActive = campaignData.isActive;
            
            if (initialStatus && (initialStatus.status === 'running' || initialStatus.status === 'pending')) {
                // If there was a running status, keep it
                updateStatusCard(initialStatus);
            } else if (isActive) {
                status.innerHTML = '<i class="fas fa-play"></i> Active';
                status.className = 'status-badge processing';
            } else {
                status.innerHTML = '<i class="fas fa-pause"></i> Paused';
                status.className = 'status-badge paused';
            }
        }
    });
}

// Ranking modal functions
// Ranking modal functionality is now in shared module rankingModal.js
// Functions are loaded via script tag and available globally

// Initialize event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Initialize button state first (checks for DAG running, cooldown, etc.)
    initializeButtonState();
    
    // Initialize status badge from server-side campaign data
    const campaignData = window.campaignData;
    if (campaignData && campaignData.derivedRunStatus) {
        const derivedStatus = campaignData.derivedRunStatus;
        const btn = document.getElementById('findJobsBtn');
        
        // Update status badge based on derived status from server
        if (derivedStatus.status === 'running' || derivedStatus.status === 'pending') {
            // DAG is running - disable button and show spinner
            isDagRunning = true;
            if (btn) {
                btn.disabled = true;
                btn.style.pointerEvents = 'none';
                btn.style.cursor = 'not-allowed';
                if (derivedStatus.status === 'running') {
                    btn.innerHTML = `${SPINNER_HTML} Running...`;
                } else {
                    btn.innerHTML = `${SPINNER_HTML} Pending...`;
                }
            }
            
            // Update status badge
            const status = document.getElementById('campaignStatus');
            if (status) {
                if (derivedStatus.status === 'running') {
                    status.innerHTML = '<i class="fas fa-cog fa-spin"></i> Running';
                    status.className = 'status-badge processing';
                } else {
                    status.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Pending';
                    status.className = 'status-badge processing';
                }
            }
            
            // Hide force start button when DAG is running
            const forceBtn = document.getElementById('forceStartBtn');
            if (forceBtn) {
                forceBtn.style.display = 'none';
            }
            
            // Start polling and update status card
            const campaignIdMatch = window.location.pathname.match(/\/campaign\/(\d+)/);
            if (campaignIdMatch) {
                const campaignId = campaignIdMatch[1];
                const dagRunId = derivedStatus.dag_run_id || null;
                // Start polling to get updated status
                if (!statusPollInterval) {
                    startPollingForCampaign(campaignId, dagRunId);
                }
            }
        } else if (derivedStatus.status === 'error') {
            // Show error status immediately
            const status = document.getElementById('campaignStatus');
            if (status) {
                status.innerHTML = '<i class="fas fa-exclamation-circle"></i> Error';
                status.className = 'status-badge error';
            }
        }
    }
    
    // Initialize status from server-side data if available (legacy support)
    if (window.campaignInitialStatus) {
        const statusData = window.campaignInitialStatus;
        updateStatusCard(statusData);
        
        // If status is running, start polling automatically
        if (statusData.status === 'running' && !statusData.is_complete) {
            const campaignIdMatch = window.location.pathname.match(/\/campaign\/(\d+)/);
            if (campaignIdMatch) {
                const campaignId = campaignIdMatch[1];
                statusPollInterval = setInterval(() => {
                    pollCampaignStatus(campaignId, statusData.dag_run_id || null);
                }, 2500);
            }
        }
    }
    
    // Find Jobs form - intercept form submission
    const findJobsForm = document.querySelector('form[action*="trigger-dag"]');
    if (findJobsForm) {
        findJobsForm.addEventListener('submit', function(e) {
            e.preventDefault();
            e.stopPropagation();
            findJobs(e);
            return false;
        });
        
        // No mousedown listener needed - native :active will handle press animation
    }
    
    // Add event listener for force start button (admin only)
    const forceStartBtn = document.getElementById('forceStartBtn');
    if (forceStartBtn) {
        forceStartBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            findJobs(e); // Call findJobs with the event so it knows it's a force start
        });
    }
    
    // Find Jobs button (backup - in case form is not found)
    const findJobsBtn = document.getElementById('findJobsBtn');
    if (findJobsBtn && !findJobsForm) {
        findJobsBtn.addEventListener('click', findJobs);
    }
    
    // Initialize ranking modal event listeners (uses shared rankingModal.js)
    if (typeof initializeRankingModal === 'function') {
        initializeRankingModal('rankingModal');
    } else {
        console.warn('Ranking modal: initializeRankingModal function not found. Ensure rankingModal.js is loaded.');
    }

    // ========================================
    // Campaign Active Toggle Functionality
    // ========================================
    const campaignToggle = document.getElementById('campaignActiveToggle');
    if (campaignToggle) {
        campaignToggle.addEventListener('change', function() {
            const campaignId = this.getAttribute('data-campaign-id');
            const isActive = this.checked;
            const toggleContainer = this.closest('.toggle-container');
            
            // Disable toggle during request
            this.disabled = true;
            if (toggleContainer) {
                toggleContainer.style.opacity = '0.7';
            }
            
            fetch(`/campaign/${campaignId}/toggle-active`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to toggle campaign status');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Update UI
                    if (typeof Utils !== 'undefined' && Utils.showNotification) {
                        Utils.showNotification(data.message, 'success');
                    }
                    
                    // Update the status badge if it exists
                    const statusBadge = document.getElementById('campaignStatus');
                    if (statusBadge) {
                        if (data.is_active) {
                            statusBadge.innerHTML = '<i class="fas fa-play"></i> Active';
                            statusBadge.className = 'status-badge processing';
                        } else {
                            statusBadge.innerHTML = '<i class="fas fa-pause"></i> Paused';
                            statusBadge.className = 'status-badge paused';
                        }
                    }
                    
                    // Update window.campaignData
                    if (window.campaignData) {
                        window.campaignData.isActive = data.is_active;
                    }
                } else {
                    throw new Error(data.error || 'Failed to toggle campaign status');
                }
            })
            .catch(error => {
                console.error('Error toggling campaign:', error);
                // Revert toggle state on error
                this.checked = !isActive;
                if (typeof Utils !== 'undefined' && Utils.showNotification) {
                    Utils.showNotification(error.message || 'Error updating campaign status', 'error');
                } else {
                    alert(error.message || 'Error updating campaign status');
                }
            })
            .finally(() => {
                // Re-enable toggle
                this.disabled = false;
                if (toggleContainer) {
                    toggleContainer.style.opacity = '1';
                }
            });
        });
    }
});

