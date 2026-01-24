/**
 * Campaign active status toggle (AJAX).
 *
 * - Uses existing /campaign/<id>/toggle-active route (JSON for XHR)
 * - Updates status badge immediately (when not in a DAG run)
 * - Disables toggle while a DAG run is starting/pending/running
 */

function getCampaignIdFromToggle(toggleEl) {
    if (!toggleEl) return null;
    const id = toggleEl.getAttribute('data-campaign-id');
    if (id) return id;

    // Fallback: infer from current URL (/campaign/<id>)
    const match = window.location.pathname.match(/\/campaign\/(\d+)/);
    return match ? match[1] : null;
}

function shouldDisableToggleForDag() {
    const findJobsBtn = document.getElementById('findJobsBtn');
    if (!findJobsBtn) return false;
    const text = (findJobsBtn.textContent || '').toLowerCase();
    return text.includes('starting') || text.includes('pending') || text.includes('running');
}

function updateStatusBadgeForActiveState(isActive) {
    const badge = document.getElementById('campaignStatus');
    if (!badge) return;

    // Only update if we're not currently showing a derived DAG state
    const derived = (window.campaignData && window.campaignData.derivedRunStatus) || null;
    if (derived && (derived.status === 'running' || derived.status === 'pending')) {
        return;
    }

    if (isActive) {
        badge.innerHTML = '<i class="fas fa-play"></i> Active';
        badge.className = 'status-badge processing';
    } else {
        badge.innerHTML = '<i class="fas fa-pause"></i> Paused';
        badge.className = 'status-badge paused';
    }
}

function updateToggleText(isActive) {
    const text = document.getElementById('campaignActiveStateText');
    if (text) {
        text.textContent = isActive ? 'Active' : 'Paused';
    }
}

function updateToggleDisabledState(toggleEl) {
    const hint = document.getElementById('campaignActiveHelp');
    const shouldDisable = shouldDisableToggleForDag();

    toggleEl.disabled = shouldDisable;

    if (hint) {
        hint.textContent = shouldDisable
            ? 'You can’t change this while jobs are being processed.'
            : 'When paused, this campaign won’t be used for job extraction.';
    }
}

async function toggleCampaignActive(campaignId) {
    const response = await fetch(`/campaign/${campaignId}/toggle-active`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json'
        },
        credentials: 'same-origin'
    });

    const contentType = response.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    const data = isJson ? await response.json() : null;

    if (!response.ok) {
        const message =
            (data && (data.error || data.message)) ||
            (response.status === 409
                ? 'Cannot change status while jobs are being processed.'
                : 'Failed to update campaign status.');
        const err = new Error(message);
        err.status = response.status;
        throw err;
    }

    if (!data || data.success !== true) {
        throw new Error((data && data.error) || 'Failed to update campaign status.');
    }

    return data;
}

document.addEventListener('DOMContentLoaded', () => {
    const toggleEl = document.getElementById('campaignActiveToggle');
    if (!toggleEl) return;

    const campaignId = getCampaignIdFromToggle(toggleEl);
    if (!campaignId) return;

    // Initialize UI based on server-rendered state
    updateToggleText(toggleEl.checked);
    updateToggleDisabledState(toggleEl);

    // Keep toggle disabled state in sync with Find Jobs button state
    const findJobsBtn = document.getElementById('findJobsBtn');
    if (findJobsBtn && typeof MutationObserver !== 'undefined') {
        const observer = new MutationObserver(() => updateToggleDisabledState(toggleEl));
        observer.observe(findJobsBtn, { childList: true, subtree: true, characterData: true });
        observer.observe(findJobsBtn, { attributes: true });
    }

    let inFlight = false;
    toggleEl.addEventListener('change', async () => {
        if (inFlight) return;

        const previousChecked = !toggleEl.checked;
        inFlight = true;
        toggleEl.disabled = true;

        try {
            const data = await toggleCampaignActive(campaignId);
            const newActive = !!data.is_active;

            toggleEl.checked = newActive;
            updateToggleText(newActive);

            if (!window.campaignData) window.campaignData = {};
            window.campaignData.isActive = newActive;

            updateStatusBadgeForActiveState(newActive);

            if (typeof Utils !== 'undefined' && Utils.showNotification) {
                Utils.showNotification(data.message || 'Campaign status updated', 'success');
            }
        } catch (e) {
            // Revert UI on error
            toggleEl.checked = previousChecked;
            updateToggleText(previousChecked);

            const message = e && e.message ? e.message : 'Failed to update campaign status.';
            if (typeof Utils !== 'undefined' && Utils.showNotification) {
                Utils.showNotification(message, 'error', false);
            }
        } finally {
            inFlight = false;
            updateToggleDisabledState(toggleEl);
        }
    });
});

