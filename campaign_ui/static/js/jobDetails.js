/**
 * Job Details page specific functionality
 */

// Constants
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
const ALLOWED_FILE_TYPES = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
const ALLOWED_FILE_EXTENSIONS = ['.pdf', '.docx'];

document.addEventListener('DOMContentLoaded', () => {
    // Handle notes form submission with validation and loading state
    const commentForm = document.querySelector('.comment-form');
    if (commentForm) {
        const formAction = commentForm.getAttribute('action') || '';
        const isNotesForm = formAction.includes('application-documents');
        
        if (isNotesForm) {
            commentForm.addEventListener('submit', function(e) {
                const textarea = this.querySelector('textarea[name="user_notes"]');
                const submitBtn = this.querySelector('button[type="submit"]');
                
                if (!textarea || !submitBtn) return;
                
                // Remove previous error states
                textarea.classList.remove('error', 'success');
                
                // Add loading state
                Utils.setButtonLoading(submitBtn, true);
                
                // Form will submit normally - let it proceed
                // The loading state will be cleared on page reload or error
            });
            
            // Add real-time validation feedback
            const textarea = commentForm.querySelector('textarea[name="user_notes"]');
            if (textarea) {
                textarea.addEventListener('input', function() {
                    this.classList.remove('error', 'success');
                    if (this.value.trim().length > 0) {
                        this.classList.add('success');
                    }
                });
                
                // Add focus/blur handlers for better UX
                textarea.addEventListener('focus', function() {
                    this.classList.remove('error');
                });
            }
        } else {
            // Old comment system (if still exists)
            commentForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const textarea = commentForm.querySelector('textarea');
                const comment = textarea.value.trim();
                
                if (comment) {
                    addCommentToUI(comment);
                    textarea.value = '';
                    Utils.showNotification('Comment added successfully', 'success');
                }
            });
        }
    }

    // Handle status change
    const statusSelect = document.getElementById('jobStatus');
    if (statusSelect) {
        statusSelect.addEventListener('change', (e) => {
            const newStatus = e.target.value;
            // In a real app, this would update the status on the server
            Utils.showNotification(`Status updated to: ${newStatus}`, 'success');
            addStatusHistory(newStatus);
        });
    }

    // Handle resume selection
    const resumeSelect = document.getElementById('resumeSelect');
    if (resumeSelect) {
        resumeSelect.addEventListener('change', (e) => {
            const linkBtn = document.getElementById('linkResumeBtn');
            if (linkBtn) {
                linkBtn.disabled = !e.target.value;
            }
        });
    }

    // Handle cover letter selection
    const coverLetterSelect = document.getElementById('coverLetterSelect');
    if (coverLetterSelect) {
        coverLetterSelect.addEventListener('change', (e) => {
            const linkBtn = document.getElementById('linkCoverLetterBtn');
            if (linkBtn) {
                linkBtn.disabled = !e.target.value;
            }
        });
    }
});

function addCommentToUI(commentText) {
    const commentsList = document.querySelector('.comments-list');
    if (!commentsList) return;

    const commentItem = document.createElement('li');
    commentItem.className = 'comment-item';
    
    const now = new Date();
    const dateStr = Utils.formatDateTime(now);
    
    commentItem.innerHTML = `
        <div class="comment-header">
            <span class="comment-author">john_doe</span>
            <span class="comment-date">${dateStr}</span>
        </div>
        <div class="comment-text">${commentText}</div>
    `;
    
    commentsList.appendChild(commentItem);
}

function addStatusHistory(statusName) {
    const statusHistory = document.querySelector('.status-history');
    if (!statusHistory) return;

    const statusItem = document.createElement('li');
    statusItem.className = 'status-history-item';
    
    const now = new Date();
    const dateStr = Utils.formatDateTime(now);
    
    statusItem.innerHTML = `
        <div class="status-info">
            <div class="status-name">${statusName.charAt(0).toUpperCase() + statusName.slice(1)}</div>
            <div class="status-date">${dateStr}</div>
        </div>
    `;
    
    statusHistory.insertBefore(statusItem, statusHistory.firstChild);
}

// ============================================================
// Document Management Functions
// ============================================================

function showResumeUploadModal() {
    const modal = document.getElementById('resumeUploadModal');
    if (modal) {
        modal.style.display = 'flex';
        modal.classList.add('active');
        // Reset to upload tab
        switchResumeTab('upload');
    }
}

function closeResumeUploadModal() {
    const modal = document.getElementById('resumeUploadModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('active');
        const form = document.getElementById('resumeUploadForm');
        if (form) {
            form.reset();
        }
        const select = document.getElementById('resumeSelectModal');
        if (select) {
            select.value = '';
        }
        // Reset to upload tab
        switchResumeTab('upload');
    }
}

function showCoverLetterModal() {
    const modal = document.getElementById('coverLetterModal');
    if (modal) {
        modal.style.display = 'flex';
        modal.classList.add('active');
        // Reset to create tab
        switchCoverLetterTab('create');
        toggleCoverLetterType(); // Ensure correct form fields are shown
    }
}

function closeCoverLetterModal() {
    const modal = document.getElementById('coverLetterModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('active');
        const form = document.getElementById('coverLetterForm');
        if (form) {
            form.reset();
            toggleCoverLetterType(); // Reset to text mode
        }
        const select = document.getElementById('coverLetterSelectModal');
        if (select) {
            select.value = '';
        }
        // Reset to create tab
        switchCoverLetterTab('create');
    }
}

function toggleCoverLetterType() {
    const textGroup = document.getElementById('coverLetterTextGroup');
    const fileGroup = document.getElementById('coverLetterFileGroup');
    const textInput = document.getElementById('cover_letter_text');
    const fileInput = document.getElementById('cover_letter_file');
    const typeRadios = document.querySelectorAll('input[name="cover_letter_type"]');
    
    if (!typeRadios.length) return;
    
    const selectedType = Array.from(typeRadios).find(r => r.checked)?.value || 'text';
    
    if (selectedType === 'text') {
        if (textGroup) textGroup.style.display = 'block';
        if (fileGroup) fileGroup.style.display = 'none';
        if (textInput) textInput.required = true;
        if (fileInput) fileInput.required = false;
    } else {
        if (textGroup) textGroup.style.display = 'none';
        if (fileGroup) fileGroup.style.display = 'block';
        if (textInput) textInput.required = false;
        if (fileInput) fileInput.required = true;
    }
}

function uploadResume(event) {
    const form = event.target;
    const fileInput = form.querySelector('input[type="file"]');
    const file = fileInput?.files[0];
    
    if (!file) {
        alert('Please select a file');
        return false;
    }
    
    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
        alert(`File size exceeds ${MAX_FILE_SIZE / (1024 * 1024)}MB limit`);
        return false;
    }
    
    // Validate file type
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!ALLOWED_FILE_EXTENSIONS.includes(fileExtension) && !ALLOWED_FILE_TYPES.includes(file.type)) {
        alert('Only PDF and DOCX files are allowed');
        return false;
    }
    
    // Show loading indicator
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Uploading...';
    }
    
    // Form will submit normally
    return true;
}

function createCoverLetter(event) {
    const form = event.target;
    const typeRadios = document.querySelectorAll('input[name="cover_letter_type"]');
    const selectedType = Array.from(typeRadios).find(r => r.checked)?.value || 'text';
    
    if (selectedType === 'text') {
        const textInput = document.getElementById('cover_letter_text');
        if (!textInput || !textInput.value.trim()) {
            alert('Please enter cover letter text');
            return false;
        }
    } else {
        const fileInput = document.getElementById('cover_letter_file');
        const file = fileInput?.files[0];
        
        if (!file) {
            alert('Please select a file');
            return false;
        }
        
        // Validate file size
        if (file.size > MAX_FILE_SIZE) {
            alert(`File size exceeds ${MAX_FILE_SIZE / (1024 * 1024)}MB limit`);
            return false;
        }
        
        // Validate file type
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!ALLOWED_FILE_EXTENSIONS.includes(fileExtension) && !ALLOWED_FILE_TYPES.includes(file.type)) {
            alert('Only PDF and DOCX files are allowed');
            return false;
        }
    }
    
    // Show loading indicator
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating...';
    }
    
    // Form will submit normally
    return true;
}

function linkResumeToJob(resumeId) {
    if (!resumeId) {
        return; // Don't do anything if empty selection
    }
    
    // Get job_id from URL
    const pathParts = window.location.pathname.split('/');
    const jobId = pathParts[pathParts.indexOf('job') + 1] || pathParts[pathParts.length - 1];
    
    const actionUrl = `/jobs/${jobId}/resume/${resumeId}/link`;
    
    fetch(actionUrl, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (response.ok) {
            window.location.reload();
        } else {
            alert('Failed to link resume');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error linking resume');
    });
}

function linkCoverLetterToJob(coverLetterId) {
    if (!coverLetterId) {
        return; // Don't do anything if empty selection
    }
    
    // Get job_id from URL
    const pathParts = window.location.pathname.split('/');
    const jobId = pathParts[pathParts.indexOf('job') + 1] || pathParts[pathParts.length - 1];
    
    const actionUrl = `/jobs/${jobId}/cover-letter/${coverLetterId}/link`;
    const linkBtn = document.querySelector(`#coverLetterSelectModal + .form-actions button[onclick*="linkCoverLetter"]`) || 
                    document.querySelector('button[onclick*="linkCoverLetterFromModal"]');
    
    // Show loading state
    const originalText = linkBtn?.textContent || 'Link Cover Letter';
    if (linkBtn) {
        linkBtn.disabled = true;
        linkBtn.textContent = 'Linking...';
    }
    
    fetch(actionUrl, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (linkBtn) {
            linkBtn.disabled = false;
            linkBtn.textContent = originalText;
        }
        if (response.ok) {
            window.location.reload();
        } else {
            return response.text().then(text => {
                throw new Error(text || 'Failed to link cover letter');
            });
        }
    })
    .catch(error => {
        console.error('Error linking cover letter:', error);
        alert(`Error linking cover letter: ${error.message || 'Unknown error'}`);
        if (linkBtn) {
            linkBtn.disabled = false;
            linkBtn.textContent = originalText;
        }
    });
}


function switchResumeTab(tab) {
    const uploadTab = document.getElementById('resumeUploadTab');
    const selectTab = document.getElementById('resumeSelectTab');
    const tabs = document.querySelectorAll('#resumeUploadModal .modal-tab');
    
    tabs.forEach(t => {
        t.classList.remove('active');
        if ((tab === 'upload' && t.textContent.includes('Upload')) || 
            (tab === 'select' && t.textContent.includes('Select'))) {
            t.classList.add('active');
        }
    });
    
    if (tab === 'upload') {
        uploadTab.style.display = 'block';
        selectTab.style.display = 'none';
    } else {
        uploadTab.style.display = 'none';
        selectTab.style.display = 'block';
    }
}

function switchCoverLetterTab(tab) {
    const createTab = document.getElementById('coverLetterCreateTab');
    const selectTab = document.getElementById('coverLetterSelectTab');
    const tabs = document.querySelectorAll('#coverLetterModal .modal-tab');
    
    tabs.forEach(t => {
        t.classList.remove('active');
        if ((tab === 'create' && t.textContent.includes('Create')) || 
            (tab === 'select' && t.textContent.includes('Select'))) {
            t.classList.add('active');
        }
    });
    
    if (tab === 'create') {
        createTab.style.display = 'block';
        selectTab.style.display = 'none';
    } else {
        createTab.style.display = 'none';
        selectTab.style.display = 'block';
    }
}

function linkResumeFromModal() {
    const select = document.getElementById('resumeSelectModal');
    const resumeId = select?.value;
    
    if (!resumeId) {
        alert('Please select a resume');
        return;
    }
    
    linkResumeToJob(resumeId);
}

function linkCoverLetterFromModal() {
    const select = document.getElementById('coverLetterSelectModal');
    const coverLetterId = select?.value;
    
    if (!coverLetterId) {
        alert('Please select a cover letter');
        return;
    }
    
    linkCoverLetterToJob(coverLetterId);
}

document.addEventListener('DOMContentLoaded', () => {
    // Prevent modal content clicks from closing the modal
    document.querySelectorAll('#resumeUploadModal .modal, #coverLetterModal .modal').forEach(modalContent => {
        modalContent.addEventListener('click', function(event) {
            event.stopPropagation();
        });
    });
    
    // Close modals when clicking outside (on the overlay)
    const resumeModal = document.getElementById('resumeUploadModal');
    const coverLetterModal = document.getElementById('coverLetterModal');
    
    if (resumeModal) {
        resumeModal.addEventListener('click', function(event) {
            if (event.target === resumeModal && resumeModal.classList.contains('active')) {
                closeResumeUploadModal();
            }
        });
    }
    
    if (coverLetterModal) {
        coverLetterModal.addEventListener('click', function(event) {
            if (event.target === coverLetterModal && coverLetterModal.classList.contains('active')) {
                closeCoverLetterModal();
            }
        });
    }
    
    // Close modals on Escape key
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            if (resumeModal && resumeModal.classList.contains('active')) {
                closeResumeUploadModal();
            } else if (coverLetterModal && coverLetterModal.classList.contains('active')) {
                closeCoverLetterModal();
            }
        }
    });
    
    // Ensure modals are hidden on page load
    if (resumeModal) {
        resumeModal.style.display = 'none';
        resumeModal.classList.remove('active');
    }
    if (coverLetterModal) {
        coverLetterModal.style.display = 'none';
        coverLetterModal.classList.remove('active');
    }
    
    // Initialize ranking modal event listeners (uses shared rankingModal.js)
    if (typeof initializeRankingModal === 'function') {
        initializeRankingModal('rankingModal');
    } else {
        console.warn('Ranking modal: initializeRankingModal function not found. Ensure rankingModal.js is loaded.');
    }
});

// Ranking modal functionality is now in shared module rankingModal.js
// Functions are loaded via script tag and available globally

