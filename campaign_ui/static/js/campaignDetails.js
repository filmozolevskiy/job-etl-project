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
let statusPollInterval = null;
let pollingErrorCount = 0;  // Track consecutive polling errors
const MAX_POLLING_ERRORS = 3;  // Stop polling after this many consecutive errors
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
        console.log(`Stored pending state for campaign ${campaignId}`);
        return true;
    } catch (e) {
        console.warn('Failed to store pending state in localStorage:', e);
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
        console.warn('Failed to read pending state from localStorage:', e);
        // Clear invalid state
        try {
            localStorage.removeItem(`dag_pending_${campaignId}`);
        } catch (clearError) {
            console.warn('Failed to clear invalid pending state:', clearError);
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
        console.warn('Failed to remove pending state from localStorage:', e);
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
            console.warn('Cooldown exceeded maximum, resetting to 1 hour');
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
        console.warn('lastRunAt is in the future, skipping cooldown');
        return 0;  // Future timestamp - no cooldown
    }
    
    if (diffSeconds >= cooldownTotalSeconds) {
        return 0;  // Cooldown period has passed
    }
    
    // Cap the remaining cooldown at the maximum (1 hour) to prevent issues
    const remainingCooldown = cooldownTotalSeconds - diffSeconds;
    if (remainingCooldown > cooldownTotalSeconds) {
        console.warn('Calculated cooldown exceeds maximum, capping at 1 hour');
        return cooldownTotalSeconds;
    }
    
    return remainingCooldown;  // Remaining cooldown seconds
}

function initializeButtonState() {
    const btn = document.getElementById('findJobsBtn');
    if (!btn) return;
    
    // Check if we have campaign data from the page
    const campaignData = window.campaignData;
    console.log('lastRunAt:', campaignData.lastRunAt);
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
    console.log('derivedStatus:', derivedStatus);
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
                console.warn('Failed to parse dag_run_id date:', e);
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
                    console.warn('Failed to parse lastRunAt date:', e);
                    isRecent = false; // If can't parse, assume stale
                }
            } else {
                // No dag_run_id and no lastRunAt - DAG never run, not truly pending
                isRecent = false;
            }
        }

        console.log('isRecent:', isRecent, 'dag_run_id:', derivedStatus.dag_run_id, 'status:', derivedStatus.status);

        if (isRecent) {
            // Server says DAG is running - clear any pending state (server is authoritative)
            removePendingState(campaignId);

            // DAG is running - disable button and show status
            isDagRunning = true;
            btn.disabled = true;
            if (derivedStatus.status === 'running') {
                btn.innerHTML = '<span class="btn-spinner-wrapper"><i class="fas fa-spinner"></i></span> Running...';
            } else {
                btn.innerHTML = '<i class="fas fa-clock"></i> Pending...';
            }

            // Show force start button for admins
            const forceBtn = document.getElementById('forceStartBtn');
            if (forceBtn) {
                forceBtn.style.display = 'inline-block';
            }
            
            // Start polling if not already polling
            if (!statusPollInterval) {
                const dagRunId = derivedStatus.dag_run_id || null;
                startPollingForCampaign(campaignId, dagRunId);
            }
            return;
        } else {
            console.log('DAG run is old or stale pending status, not disabling button');
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
        console.log('DAG is not running - resetting isDagRunning to false');
    }

    // Only check localStorage for pending state if server has no status info
    // (user may have refreshed after clicking but before server updated)
    if (!derivedStatus) {
        const pending = getPendingState(campaignId);
        console.log('pending:', pending);
        
        if (pending) {
            const pendingAge = Date.now() - pending.timestamp;
            
            // Only restore if pending state is recent (less than expiry time)
            // This prevents stale pending states from persisting indefinitely
            if (pendingAge < PENDING_STATE_EXPIRY_MS) {
                console.log(`Restoring pending state for campaign ${campaignId} (age: ${Math.round(pendingAge / 1000)}s, forced: ${pending.forced || false})`);
                isDagRunning = true;
                btn.disabled = true;
                btn.innerHTML = '<span class="btn-spinner-wrapper"><i class="fas fa-spinner"></i></span> Starting...';
                
                // Restore force start flag if this was a force start
                if (pending.forced) {
                    window.lastDagWasForced = true;
                    console.log('Restored force start flag from pending state');
                }
                
                const status = document.getElementById('campaignStatus');
                if (status) {
                    status.innerHTML = '<i class="fas fa-clock"></i> Starting...';
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
                console.log(`Removing stale pending state for campaign ${campaignId}`);
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
    console.log('remainingCooldown initial:', remainingCooldown);
    
    if (campaignIdMatch) {
        const campaignId = campaignIdMatch[1];
        const storedCooldownEnd = localStorage.getItem(`cooldown_end_${campaignId}`);
        if (storedCooldownEnd) {
            const cooldownEndTime = parseInt(storedCooldownEnd, 10);
            const now = Date.now();
            if (cooldownEndTime > now) {
                // Still in cooldown from localStorage
                remainingCooldown = Math.floor((cooldownEndTime - now) / 1000);
                console.log(`Cooldown from localStorage for campaign ${campaignId}:`, remainingCooldown, 'seconds');
            } else {
                // Cooldown expired, remove from localStorage
                localStorage.removeItem(`cooldown_end_${campaignId}`);
            }
        }
    }

    console.log('remainingCooldown after localStorage:', remainingCooldown);

    // If no cooldown from localStorage, check lastRunAt from database
    if (remainingCooldown === 0) {
        const lastRunAt = campaignData.lastRunAt;
        if (lastRunAt) {
            remainingCooldown = calculateCooldownSeconds(lastRunAt);
            console.log('remainingCooldown after calculate:', remainingCooldown);
        }
    }
    
    if (remainingCooldown > 0) {
        // Still in cooldown period
        cooldownSeconds = remainingCooldown;
        btn.disabled = true;
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
        return;
    }
    
    // No cooldown, enable button
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs';
    console.log('Button enabled - isDagRunning:', isDagRunning, 'btn.disabled:', btn.disabled, 'cooldown:', remainingCooldown);
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
    
    // #region agent log
    const errorMsgRect = errorMsg.getBoundingClientRect();
    const containerRect = statusContainer.getBoundingClientRect();
    fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:407',message:'Error message displayed',data:{errorMsgRect:JSON.stringify(errorMsgRect),containerRect:JSON.stringify(containerRect),relativeLeft:errorMsgRect.left-containerRect.left,relativeTop:errorMsgRect.top-containerRect.top},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H11'})}).catch(()=>{});
    // #endregion
}

function updateStatusCard(statusData) {
    const status = document.getElementById('campaignStatus');
    if (!status) {
        console.warn('Status element not found');
        return;
    }
    
    const statusValue = statusData.status;
    const completedTasks = statusData.completed_tasks || [];
    const failedTasks = statusData.failed_tasks || [];
    
    console.log('Updating status card:', statusValue, { completedTasks, failedTasks });
    
    // Remove any existing error message
    const statusContainer = status.parentElement;
    if (!statusContainer) {
        console.warn('Status container not found');
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
            status.innerHTML = '<i class="fas fa-hourglass-half"></i> Waiting for tasks...';
        } else {
            status.innerHTML = '<i class="fas fa-clock"></i> Starting...';
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
        // Restore button dimensions to auto
        btn.style.width = '';
        btn.style.minWidth = '';
        btn.style.height = '';
        btn.style.minHeight = '';
        
        // Restore button dimensions to auto
        btn.style.width = '';
        btn.style.minWidth = '';
        btn.style.height = '';
        btn.style.minHeight = '';
        
        if (!isDagRunning) {
            // Only reset if DAG is not running
        const campaignData = window.campaignData;
        if (campaignData && campaignData.lastRunAt) {
            const remainingCooldown = calculateCooldownSeconds(campaignData.lastRunAt);
            if (remainingCooldown > 0) {
                // Still in cooldown, don't enable button
                cooldownSeconds = remainingCooldown;
                btn.disabled = true;
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
            btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs';
        }
    }
}

function pollCampaignStatus(campaignId, dagRunId = null) {
    const url = `/campaign/${campaignId}/status${dagRunId ? `?dag_run_id=${dagRunId}` : ''}`;
    
    console.log('Polling status:', url);
    
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
            console.log('Status response:', data);
            
            // Reset error count on successful response
            pollingErrorCount = 0;
            
            // Clear pending state if we got any valid status response (DAG is no longer "pending")
            // This handles all statuses including any future ones
            if (data.status) {
                removePendingState(campaignId);
            }
            
            // Update status card only if not complete (or if error)
            // If complete and successful, don't update - let page refresh show Active
            if (data.is_complete && data.status === 'success') {
                // Show brief "Complete" message, then refresh
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
                            console.log(`Stored cooldown end time for campaign ${campaignId}:`, new Date(cooldownEndTime));
                        } catch (e) {
                            console.warn('Failed to store cooldown end time in localStorage:', e);
                        }
                    }
                    
                    const btn = document.getElementById('findJobsBtn');
                    if (btn) {
                        btn.disabled = true;
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
                        btn.disabled = false;
                        btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs';
                    }
                    // Hide force button
                    const forceBtn = document.getElementById('forceStartBtn');
                    if (forceBtn) {
                        forceBtn.style.display = 'none';
                    }
                }
                
                // Wait longer for jobs and data to be fully written to database
                setTimeout(() => {
                    // Refresh current campaign page to show updated jobs and Active status
                    window.location.reload();
                }, 3000); // Increased to 3 seconds to ensure data is written
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
                        console.log(`Stored cooldown end time for campaign ${campaignId} (error):`, new Date(cooldownEndTime));
                    }
                    
                    const btn = document.getElementById('findJobsBtn');
                    if (btn) {
                        btn.disabled = true;
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
        btn.disabled = false;
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
                console.log('DAG not started yet or no metrics, waiting... (keeping "Running..." status)');
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
                    console.warn(`Polling error ${pollingErrorCount}/${MAX_POLLING_ERRORS}. Will retry...`);
                }
            }
        });
}

function findJobs(event) {
    console.log('findJobs called, event:', event);
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:747',message:'findJobs function called',data:{eventType:event?.type,eventTarget:event?.target?.id,hasEvent:!!event},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
    // #endregion
    // Prevent default form submission if event is provided
    if (event) {
        event.preventDefault();
    }
    
    const form = document.querySelector('form[action*="trigger-dag"]');
    const btn = document.getElementById('findJobsBtn');
    const status = document.getElementById('campaignStatus');
    
    if (!form || !btn || !status) {
        console.error('Required elements not found');
        return;
    }
    
    // Check if this is a force start FIRST (before other checks)
    const isForceStart = event && event.target && event.target.id === 'forceStartBtn';
    
    if (isForceStart) {
        console.log('Force start triggered - bypassing cooldown');
    }
    
    // Check if DAG is running (even for force start)
    if (isDagRunning) {
        console.log('DAG is already running');
        return;
    }
    
    // Check cooldown (unless this is a force start) - do this BEFORE checking button disabled state
    const campaignData = window.campaignData;
    let remainingCooldown = 0;
    if (!isForceStart && campaignData && campaignData.lastRunAt) {
        remainingCooldown = calculateCooldownSeconds(campaignData.lastRunAt);
        if (remainingCooldown > 0) {
            console.log('Still in cooldown period:', remainingCooldown, 'seconds');
            return;
        }
    }
    
    // Check if button is disabled - but allow if DAG is not running and no cooldown
    if (btn.disabled && !isForceStart) {
        // If button is disabled but DAG is not running and no cooldown, re-enable it
        if (!isDagRunning && remainingCooldown === 0) {
            console.log('Button was disabled but DAG is not running and no cooldown - re-enabling button');
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-search"></i> Find Jobs';
        } else {
            console.log('Button is disabled. isDagRunning:', isDagRunning, 'btn.disabled:', btn.disabled, 'cooldown:', remainingCooldown);
            return;
        }
    }
    
    // Double-check: prevent if DAG is running (even for force start)
    if (isDagRunning) {
        console.log('DAG is already running');
        return;
    }
    
    // Get campaign ID from form action
    const campaignIdMatch = form.action.match(/\/campaign\/(\d+)\/trigger-dag/);
    if (!campaignIdMatch) {
        console.error('Could not extract campaign ID from form');
        return;
    }
    const campaignId = campaignIdMatch[1];
    
    // Check if there's already a recent pending state (prevent double-trigger)
    // This handles rapid clicks before isDagRunning is set
    const existingPending = getPendingState(campaignId);
    if (existingPending) {
        const pendingAge = Date.now() - existingPending.timestamp;
        if (pendingAge < PENDING_STATE_RECENT_MS) {
            console.log('DAG trigger already in progress (recent pending state found)');
            return;
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
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:849',message:'findJobs function entry',data:{buttonId:btn.id,buttonDisabled:btn.disabled,hasPressedClass:btn.classList.contains('btn-pressed'),computedTransform:window.getComputedStyle(btn).transform},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
    
    // Temporarily enable button if disabled to allow animation
    const wasDisabled = btn.disabled;
    if (wasDisabled) {
        btn.disabled = false;
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:855',message:'Button was disabled, re-enabled',data:{wasDisabled:true,nowDisabled:btn.disabled},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
        // #endregion
    }
    
    // CRITICAL: Preserve button dimensions BEFORE any changes to prevent layout shifts
    const currentWidth = btn.offsetWidth;
    const currentHeight = btn.offsetHeight;
    
    // #region agent log
    const computedBefore = window.getComputedStyle(btn);
    const btnRectBefore = btn.getBoundingClientRect();
    fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:867',message:'BEFORE any changes - initial state',data:{transform:computedBefore.transform,transition:computedBefore.transition,isActive:btn.matches(':active'),offsetWidth:btn.offsetWidth,offsetHeight:btn.offsetHeight,getBoundingClientRect:JSON.stringify(btnRectBefore)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H12'})}).catch(()=>{});
    // #endregion
    
    // Stop all transforms and transitions immediately
    btn.style.transition = 'none';
    btn.style.transform = 'none';
    
    // Preserve button dimensions to prevent flex container reflow
    btn.style.width = currentWidth + 'px';
    btn.style.minWidth = currentWidth + 'px';
    btn.style.height = currentHeight + 'px';
    btn.style.minHeight = currentHeight + 'px';
    
    // Force immediate reflow to apply all styles
    void btn.offsetHeight;
    
    // #region agent log
    const computedAfterReflow = window.getComputedStyle(btn);
    fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:895',message:'AFTER reflow - before disabling',data:{computedTransform:computedAfterReflow.transform,computedTransition:computedAfterReflow.transition,isActive:btn.matches(':active'),getBoundingClientRect:JSON.stringify(btn.getBoundingClientRect())},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H12'})}).catch(()=>{});
    // #endregion
    
    // Now disable - this will apply .btn:disabled and .find-jobs-btn:disabled styles
    btn.disabled = true;
    
    // Force another reflow to ensure disabled state is applied
    void btn.offsetHeight;
    
    // #region agent log
    const computedAfterDisabled = window.getComputedStyle(btn);
    fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:910',message:'AFTER disabling button',data:{disabled:btn.disabled,computedTransform:computedAfterDisabled.transform,computedTransition:computedAfterDisabled.transition,inlineTransition:btn.style.transition,inlineTransform:btn.style.transform,getBoundingClientRect:JSON.stringify(btn.getBoundingClientRect())},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H1'})}).catch(()=>{});
    // #endregion
    
    // #region agent log - Set up MutationObserver to track ALL button HTML changes
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'childList' || mutation.type === 'attributes') {
                const stackTrace = new Error().stack || 'No stack trace';
                const btnRect = btn.getBoundingClientRect();
                const btnHTML = btn.innerHTML.substring(0, 200); // Truncate long HTML
                fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:934-MutationObserver',message:'Button HTML changed via MutationObserver',data:{mutationType:mutation.type,mutationTarget:mutation.target.tagName,btnHTML:btnHTML,btnRect:JSON.stringify(btnRect),hasFaSpin:btnHTML.includes('fa-spin'),hasWrapper:btnHTML.includes('btn-spinner-wrapper'),stackTrace:stackTrace.split('\n').slice(1,5).join('\n')},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H17'})}).catch(()=>{});
            }
        });
    });
    
    // Start observing button for ALL changes (children, attributes, character data)
    observer.observe(btn, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class', 'style'],
        characterData: false
    });
    
    // Store observer so we can disconnect it later
    window.btnMutationObserver = observer;
    // #endregion
    
    // Change content - use Font Awesome spinner WITHOUT fa-spin class to avoid Font Awesome animation override
    // We use our own CSS animation instead
    btn.innerHTML = '<span class="btn-spinner-wrapper"><i class="fas fa-spinner"></i></span> Starting...';
    
    // Force reflow after innerHTML change
    void btn.offsetHeight;
    
    // #region agent log - Check font loading state
    if (document.fonts && document.fonts.check) {
        const fontLoaded = document.fonts.check('1em "Font Awesome 6 Free"');
        const fontStatus = document.fonts.status;
        fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:937',message:'Font loading state after innerHTML',data:{fontLoaded:fontLoaded,fontStatus:fontStatus,readyState:document.readyState},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H15'})}).catch(()=>{});
    }
    // #endregion
    
    // #region agent log - Wrap innerHTML setter to track all changes
    const originalInnerHTML = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML');
    if (!window.btnInnerHTMLTracker) {
        window.btnInnerHTMLTracker = true;
        Object.defineProperty(btn, 'innerHTML', {
            set: function(value) {
                const stackTrace = new Error().stack || 'No stack trace';
                const caller = stackTrace.split('\n')[1] || 'Unknown caller';
                fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:934-innerHTML-setter',message:'Button innerHTML being set',data:{newValue:value.substring(0,200),hasFaSpin:value.includes('fa-spin'),hasWrapper:value.includes('btn-spinner-wrapper'),caller:caller,stackTrace:stackTrace.split('\n').slice(1,6).join('\n')},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H18'})}).catch(()=>{});
                originalInnerHTML.set.call(this, value);
            },
            get: function() {
                return originalInnerHTML.get.call(this);
            },
            configurable: true
        });
    }
    // #endregion
    
    // #region agent log
    const computedAfterInnerHTML = window.getComputedStyle(btn);
    const spinner = btn.querySelector('.fa-spinner');
    const spinnerWrapper = btn.querySelector('.btn-spinner-wrapper');
    const spinnerComputed = spinner ? window.getComputedStyle(spinner) : null;
    const wrapperComputed = spinnerWrapper ? window.getComputedStyle(spinnerWrapper) : null;
    fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:925',message:'AFTER innerHTML change',data:{computedTransform:computedAfterInnerHTML.transform,computedTransition:computedAfterInnerHTML.transition,width:btn.offsetWidth,height:btn.offsetHeight,getBoundingClientRect:JSON.stringify(btn.getBoundingClientRect()),spinnerFound:!!spinner,spinnerClasses:spinner?.className,spinnerAnimation:spinnerComputed?.animation,spinnerAnimationName:spinnerComputed?.animationName,spinnerTransform:spinnerComputed?.transform,spinnerTransformOrigin:spinnerComputed?.transformOrigin,spinnerDisplay:spinnerComputed?.display,spinnerVisibility:spinnerComputed?.visibility,spinnerWillChange:spinnerComputed?.willChange,spinnerAnimationPlayState:spinnerComputed?.animationPlayState,wrapperFound:!!spinnerWrapper,wrapperTransform:wrapperComputed?.transform,wrapperPosition:wrapperComputed?.position,wrapperIsolation:wrapperComputed?.isolation},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H13'})}).catch(()=>{});
    // #endregion
    
    // #region agent log - Track which CSS rules are actually applied to spinner
    const logMatchedCSSRules = (element, label) => {
        if (!element) return;
        try {
            // Try to get matched CSS rules (works in Chrome/Edge)
            const rules = [];
            if (window.getMatchedCSSRules) {
                const matchedRules = window.getMatchedCSSRules(element);
                for (let i = 0; i < matchedRules.length; i++) {
                    const rule = matchedRules[i];
                    if (rule.style.animation || rule.style.animationName || rule.selectorText.includes('spinner') || rule.selectorText.includes('fa-spin')) {
                        rules.push({
                            selector: rule.selectorText,
                            animation: rule.style.animation,
                            animationName: rule.style.animationName,
                            animationDuration: rule.style.animationDuration,
                            position: rule.style.position,
                            isolation: rule.style.isolation,
                            display: rule.style.display,
                            cssText: rule.cssText.substring(0, 200) // Truncate long CSS
                        });
                    }
                }
            }
            
            // Also check stylesheet order and sources
            const stylesheets = [];
            for (let i = 0; i < document.styleSheets.length; i++) {
                try {
                    const sheet = document.styleSheets[i];
                    const href = sheet.href || (sheet.ownerNode ? sheet.ownerNode.href || sheet.ownerNode.getAttribute('href') : 'inline');
                    if (href && (href.includes('font-awesome') || href.includes('all.min.css') || href.includes('main.css') || href.includes('components.css'))) {
                        stylesheets.push({
                            index: i,
                            href: href,
                            disabled: sheet.disabled,
                            rulesCount: sheet.cssRules ? sheet.cssRules.length : 0
                        });
                    }
                } catch (e) {
                    // Cross-origin stylesheet, skip
                }
            }
            
            fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:`campaignDetails.js:945-${label}`,message:`CSS rules analysis - ${label}`,data:{matchedRules:rules,stylesheets:stylesheets,label:label},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H14'})}).catch(()=>{});
        } catch (e) {
            fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:`campaignDetails.js:945-${label}`,message:`Error getting CSS rules - ${label}`,data:{error:e.message,label:label},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H14'})}).catch(()=>{});
        }
    };
    // #endregion
    
    // #region agent log - Track spinner animation state over time with CSS rule analysis
    const trackSpinnerAnimation = (delay, label) => {
        setTimeout(() => {
            const spinnerEl = btn.querySelector('.fa-spinner');
            const spinnerWrapperEl = btn.querySelector('.btn-spinner-wrapper');
            const spinnerComputed = spinnerEl ? window.getComputedStyle(spinnerEl) : null;
            const wrapperComputed = spinnerWrapperEl ? window.getComputedStyle(spinnerWrapperEl) : null;
            const spinnerRect = spinnerEl ? spinnerEl.getBoundingClientRect() : null;
            const wrapperRect = spinnerWrapperEl ? spinnerWrapperEl.getBoundingClientRect() : null;
            
            // Get computed styles for all relevant properties
            const animationState = {
                spinnerAnimation: spinnerComputed?.animation || 'none',
                spinnerAnimationName: spinnerComputed?.animationName || 'none',
                spinnerAnimationDuration: spinnerComputed?.animationDuration || '0s',
                spinnerAnimationPlayState: spinnerComputed?.animationPlayState || 'none',
                spinnerTransform: spinnerComputed?.transform || 'none',
                spinnerTransformOrigin: spinnerComputed?.transformOrigin || 'none',
                spinnerDisplay: spinnerComputed?.display || 'none',
                spinnerVisibility: spinnerComputed?.visibility || 'none',
                spinnerOpacity: spinnerComputed?.opacity || '1',
                spinnerWillChange: spinnerComputed?.willChange || 'auto',
                wrapperTransform: wrapperComputed?.transform || 'none',
                wrapperPosition: wrapperComputed?.position || 'static',
                wrapperIsolation: wrapperComputed?.isolation || 'auto',
                wrapperDisplay: wrapperComputed?.display || 'none',
                spinnerRect: spinnerRect ? JSON.stringify(spinnerRect) : null,
                wrapperRect: wrapperRect ? JSON.stringify(wrapperRect) : null,
                spinnerClasses: spinnerEl?.className || '',
                hasFaSpin: spinnerEl?.classList.contains('fa-spin') || false,
                inlineAnimation: spinnerEl?.style.animation || 'none',
                inlineAnimationName: spinnerEl?.style.animationName || 'none'
            };
            
            fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:`campaignDetails.js:945-${label}`,message:`AFTER ${delay}ms delay - spinner animation state`,data:Object.assign({delay:delay,label:label},animationState),timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H13'})}).catch(()=>{});
            
            // Log matched CSS rules to see which styles are actually winning
            logMatchedCSSRules(spinnerEl, label);
            logMatchedCSSRules(spinnerWrapperEl, `${label}-wrapper`);
            
            // #region agent log - Track button position changes (for layout shift detection)
            const btnRect = btn.getBoundingClientRect();
            const btnComputed = window.getComputedStyle(btn);
            const parent = btn.parentElement;
            const parentRect = parent ? parent.getBoundingClientRect() : null;
            const parentComputed = parent ? window.getComputedStyle(parent) : null;
            const statusBadgeContainer = status ? status.parentElement : null;
            const statusContainerRect = statusBadgeContainer ? statusBadgeContainer.getBoundingClientRect() : null;
            if (label === '100ms' || label === '1600ms') {
                fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:`campaignDetails.js:945-${label}-button`,message:`Button position at ${delay}ms`,data:{delay:delay,label:label,btnRect:JSON.stringify(btnRect),btnPosition:btnComputed.position,btnDisplay:btnComputed.display,btnWidth:btn.offsetWidth,btnHeight:btn.offsetHeight,parentRect:parentRect?JSON.stringify(parentRect):null,parentDisplay:parentComputed?.display,parentPosition:parentComputed?.position,statusContainerRect:statusContainerRect?JSON.stringify(statusContainerRect):null,statusContainerWidth:statusBadgeContainer?.offsetWidth,statusContainerDisplay:statusBadgeContainer?window.getComputedStyle(statusBadgeContainer).display:null},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H16'})}).catch(()=>{});
            }
            // #endregion
        }, delay);
    };
    
    // Track at multiple intervals to see if transform changes (proving rotation)
    trackSpinnerAnimation(100, '100ms');
    trackSpinnerAnimation(300, '300ms');
    trackSpinnerAnimation(500, '500ms');
    trackSpinnerAnimation(800, '800ms'); // One full rotation cycle
    trackSpinnerAnimation(1600, '1600ms'); // Two full rotation cycles
    // #endregion
    
    status.innerHTML = '<i class="fas fa-clock"></i> Starting...';
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
        console.log('DAG trigger response:', data);
        
        // Track if this was a forced start (already set above, but confirm from response)
        if (data.forced) {
            window.lastDagWasForced = true;
        }
        
        const dagRunId = data.dag_run_id || null;
        
        // Clear pending state from localStorage since we got confirmation
        removePendingState(campaignId);
        console.log(`Cleared pending state for campaign ${campaignId} - DAG confirmed started`);
        
        // Update UI immediately to show "Running" instead of "Starting"
        // This prevents the weird pending animation after DAG is confirmed started
        // Use wrapper structure without fa-spin class to avoid Font Awesome animation override
        // #region agent log - Track when DAG response updates button
        const btnRectBeforeUpdate = btn.getBoundingClientRect();
        fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:1190',message:'BEFORE updating button from DAG response',data:{btnRect:JSON.stringify(btnRectBeforeUpdate),currentHTML:btn.innerHTML.substring(0,200)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H19'})}).catch(()=>{});
        // #endregion
        btn.innerHTML = '<span class="btn-spinner-wrapper"><i class="fas fa-spinner"></i></span> Running...';
        // #region agent log - Track after DAG response updates button
        setTimeout(() => {
            const btnRectAfterUpdate = btn.getBoundingClientRect();
            const spinner = btn.querySelector('.fa-spinner');
            fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:1195',message:'AFTER updating button from DAG response',data:{btnRect:JSON.stringify(btnRectAfterUpdate),btnRectBefore:JSON.stringify(btnRectBeforeUpdate),deltaX:btnRectAfterUpdate.x-btnRectBeforeUpdate.x,deltaY:btnRectAfterUpdate.y-btnRectBeforeUpdate.y,spinnerFound:!!spinner,spinnerClasses:spinner?.className},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H19'})}).catch(()=>{});
        }, 10);
        // #endregion
        status.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        status.className = 'status-badge processing';
        
        // Start polling immediately (no delay - we want immediate feedback)
        console.log('Starting status polling for campaign:', campaignId, 'dag_run_id:', dagRunId);
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
    console.log('campaignDetails.js DOMContentLoaded fired');
    // Initialize button state first (checks for DAG running, cooldown, etc.)
    initializeButtonState();
    
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
    console.log('findJobsForm:', findJobsForm);
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/cf81280e-f64b-48c4-b57b-bff525b03e2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'campaignDetails.js:1161',message:'Form lookup result',data:{formFound:!!findJobsForm},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    if (findJobsForm) {
        findJobsForm.addEventListener('submit', findJobs);
        
        // No mousedown listener needed - native :active will handle press animation
    }
    
    // Add event listener for force start button (admin only)
    const forceStartBtn = document.getElementById('forceStartBtn');
    if (forceStartBtn) {
        forceStartBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Force start button clicked');
            findJobs(e); // Call findJobs with the event so it knows it's a force start
        });
    }
    
    // Find Jobs button (backup - in case form is not found)
    const findJobsBtn = document.getElementById('findJobsBtn');
    if (findJobsBtn && !findJobsForm) {
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

