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
    const generateTab = document.getElementById('coverLetterGenerateTab');
    const tabs = document.querySelectorAll('#coverLetterModal .modal-tab');
    
    tabs.forEach(t => {
        t.classList.remove('active');
        if ((tab === 'create' && t.textContent.includes('Create')) || 
            (tab === 'select' && t.textContent.includes('Select')) ||
            (tab === 'generate' && t.textContent.includes('Generate'))) {
            t.classList.add('active');
        }
    });
    
    if (tab === 'create') {
        createTab.style.display = 'block';
        selectTab.style.display = 'none';
        if (generateTab) generateTab.style.display = 'none';
    } else if (tab === 'select') {
        createTab.style.display = 'none';
        selectTab.style.display = 'block';
        if (generateTab) generateTab.style.display = 'none';
    } else if (tab === 'generate') {
        createTab.style.display = 'none';
        selectTab.style.display = 'none';
        if (generateTab) generateTab.style.display = 'block';
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

// Cover Letter Generation Functions
function showCoverLetterGenerateModal() {
    const modal = document.getElementById('coverLetterGenerateModal');
    if (modal) {
        modal.style.display = 'flex';
        modal.classList.add('active');
        // Reset form
        const form = document.getElementById('coverLetterGenerateForm');
        if (form) {
            form.reset();
            // Show all form fields
            const formFields = form.querySelectorAll('.form-group');
            formFields.forEach(field => {
                field.style.display = '';
            });
        }
        document.getElementById('generatePreviewArea').style.display = 'none';
        document.getElementById('generateErrorArea').style.display = 'none';
        document.getElementById('generateFormActions').style.display = 'flex';
        document.getElementById('generatePreviewActions').style.display = 'none';
        document.getElementById('generateLoadingSpinner').style.display = 'none';
    }
}

function closeCoverLetterGenerateModal() {
    const modal = document.getElementById('coverLetterGenerateModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('active');
    }
}

function generateCoverLetterWithAI(event) {
    event.preventDefault();
    
    const form = document.getElementById('coverLetterGenerateForm');
    const resumeSelect = document.getElementById('generate_resume_select');
    const userComments = document.getElementById('generate_user_comments');
    const loadingSpinner = document.getElementById('generateLoadingSpinner');
    const previewArea = document.getElementById('generatePreviewArea');
    const errorArea = document.getElementById('generateErrorArea');
    const errorMessage = document.getElementById('generateErrorMessage');
    const formActions = document.getElementById('generateFormActions');
    const previewActions = document.getElementById('generatePreviewActions');
    const generateButton = document.getElementById('generateButton');
    
    // Validate resume selection
    if (!resumeSelect.value) {
        alert('Please select a resume');
        return false;
    }
    
    // Get job ID from current page
    const pathParts = window.location.pathname.split('/');
    const jobId = pathParts[pathParts.indexOf('jobs') + 1] || (typeof currentJobId !== 'undefined' ? currentJobId : null);
    
    if (!jobId) {
        alert('Unable to determine job ID');
        return false;
    }
    
    // Show loading state - hide form fields and show spinner
    const formFields = form.querySelectorAll('.form-group');
    formFields.forEach(field => {
        field.style.display = 'none';
    });
    loadingSpinner.style.display = 'block';
    previewArea.style.display = 'none';
    errorArea.style.display = 'none';
    formActions.style.display = 'none';
    generateButton.disabled = true;
    
    // Prepare request data
    const requestData = {
        resume_id: parseInt(resumeSelect.value),
    };
    
    if (userComments && userComments.value.trim()) {
        requestData.user_comments = userComments.value.trim();
    }
    
    // Make API call
    fetch(`/api/jobs/${encodeURIComponent(jobId)}/cover-letter/generate`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
    })
    .then(response => response.json())
    .then(data => {
        loadingSpinner.style.display = 'none';
        generateButton.disabled = false;
        
        if (data.error) {
            // Show error - restore form fields
            const formFields = form.querySelectorAll('.form-group');
            formFields.forEach(field => {
                field.style.display = '';
            });
            errorMessage.textContent = data.error;
            errorArea.style.display = 'block';
            formActions.style.display = 'flex';
        } else {
            // Show preview - keep form fields hidden
            const generatedText = document.getElementById('generated_cover_letter_text');
            if (generatedText) {
                generatedText.value = data.cover_letter_text || '';
            }
            
            // Store cover letter ID for saving
            if (data.cover_letter_id) {
                form.dataset.coverLetterId = data.cover_letter_id;
            }
            
            previewArea.style.display = 'block';
            formActions.style.display = 'none';
            previewActions.style.display = 'flex';
            
            // Scroll to preview
            previewArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    })
    .catch(error => {
        console.error('Error generating cover letter:', error);
        // Restore form fields on error
        const formFields = form.querySelectorAll('.form-group');
        formFields.forEach(field => {
            field.style.display = '';
        });
        loadingSpinner.style.display = 'none';
        generateButton.disabled = false;
        errorMessage.textContent = 'Network error. Please check your connection and try again.';
        errorArea.style.display = 'block';
        formActions.style.display = 'flex';
    });
    
    return false;
}

function saveGeneratedCoverLetter() {
    const form = document.getElementById('coverLetterGenerateForm');
    const generatedText = document.getElementById('generated_cover_letter_text');
    const coverLetterId = form.dataset.coverLetterId;
    
    if (!generatedText || !generatedText.value.trim()) {
        alert('Please enter cover letter text');
        return;
    }
    
    // Get job ID
    const pathParts = window.location.pathname.split('/');
    const jobId = pathParts[pathParts.indexOf('jobs') + 1] || (typeof currentJobId !== 'undefined' ? currentJobId : null);
    
    if (!jobId) {
        alert('Unable to determine job ID');
        return;
    }
    
    // Create a form to submit the cover letter
    const submitForm = document.createElement('form');
    submitForm.method = 'POST';
    submitForm.action = `/jobs/${encodeURIComponent(jobId)}/cover-letter/create`;
    
    // Add cover letter text
    const textInput = document.createElement('input');
    textInput.type = 'hidden';
    textInput.name = 'cover_letter_text';
    textInput.value = generatedText.value.trim();
    submitForm.appendChild(textInput);
    
    // Add cover letter name
    const nameInput = document.createElement('input');
    nameInput.type = 'hidden';
    nameInput.name = 'cover_letter_name';
    nameInput.value = `Generated Cover Letter - ${new Date().toLocaleDateString()}`;
    submitForm.appendChild(nameInput);
    
    // Link to job
    const linkInput = document.createElement('input');
    linkInput.type = 'hidden';
    linkInput.name = 'link_to_job';
    linkInput.value = 'true';
    submitForm.appendChild(linkInput);
    
    // If we have a cover letter ID, we need to update it instead
    if (coverLetterId) {
        // The cover letter was already created, just update it
        // For now, we'll submit the form which will create a new one
        // In Step 3, we'll add update functionality
    }
    
    document.body.appendChild(submitForm);
    submitForm.submit();
}

// Helper functions for cover letter generation modal
function getCoverLetterModalElements() {
    return {
        form: document.getElementById('coverLetterGenerateFormInModal'),
        resumeSelect: document.getElementById('generate_resume_select_modal'),
        userComments: document.getElementById('generate_user_comments_modal'),
        loadingSpinner: document.getElementById('generateLoadingSpinnerModal'),
        previewArea: document.getElementById('generatePreviewAreaModal'),
        errorArea: document.getElementById('generateErrorAreaModal'),
        errorMessage: document.getElementById('generateErrorMessageModal'),
        formActions: document.getElementById('generateFormActionsModal'),
        previewActions: document.getElementById('generatePreviewActionsModal'),
        generateButton: document.getElementById('generateButtonModal'),
    };
}

function showCoverLetterLoadingState(elements) {
    const resumeSelectGroup = elements.resumeSelect.closest('.form-group');
    const instructionsGroup = elements.userComments ? elements.userComments.closest('.form-group') : null;
    
    if (resumeSelectGroup) resumeSelectGroup.style.display = 'none';
    if (instructionsGroup) instructionsGroup.style.display = 'none';
    
    elements.loadingSpinner.style.display = 'block';
    elements.previewArea.style.display = 'none';
    elements.errorArea.style.display = 'none';
    elements.formActions.style.display = 'none';
    if (elements.generateButton) elements.generateButton.disabled = true;
}

function showCoverLetterErrorState(elements, errorText) {
    const resumeSelectGroup = elements.resumeSelect.closest('.form-group');
    const instructionsGroup = elements.userComments ? elements.userComments.closest('.form-group') : null;
    
    if (resumeSelectGroup) resumeSelectGroup.style.display = '';
    if (instructionsGroup) instructionsGroup.style.display = '';
    
    elements.loadingSpinner.style.display = 'none';
    if (elements.generateButton) elements.generateButton.disabled = false;
    elements.errorMessage.textContent = errorText;
    elements.errorArea.style.display = 'block';
    elements.formActions.style.display = 'flex';
}

function showCoverLetterPreviewState(elements, data) {
    const generatedText = document.getElementById('generated_cover_letter_text_modal');
    if (generatedText) {
        generatedText.value = data.cover_letter_text || '';
    }
    
    if (data.cover_letter_id && elements.form) {
        elements.form.dataset.coverLetterId = data.cover_letter_id;
    }
    
    elements.loadingSpinner.style.display = 'none';
    if (elements.generateButton) elements.generateButton.disabled = false;
    
    elements.previewArea.style.display = 'block';
    const previewFormGroup = elements.previewArea.querySelector('.form-group');
    if (previewFormGroup) {
        previewFormGroup.style.display = '';
    }
    
    elements.formActions.style.display = 'none';
    elements.previewActions.style.display = 'flex';
    elements.previewArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function getJobIdFromURL() {
    const pathParts = window.location.pathname.split('/');
    return pathParts[pathParts.indexOf('jobs') + 1] || (typeof currentJobId !== 'undefined' ? currentJobId : null);
}

async function callCoverLetterGenerationAPI(jobId, resumeId, userComments) {
    const requestData = { resume_id: parseInt(resumeId) };
    if (userComments && userComments.trim()) {
        requestData.user_comments = userComments.trim();
    }
    
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/cover-letter/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData),
    });
    
    return response.json();
}

function generateCoverLetterWithAIFromModal(event) {
    event.preventDefault();
    
    const elements = getCoverLetterModalElements();
    
    // Validate resume selection
    if (!elements.resumeSelect || !elements.resumeSelect.value) {
        alert('Please select a resume');
        return false;
    }
    
    const jobId = getJobIdFromURL();
    if (!jobId) {
        alert('Unable to determine job ID');
        return false;
    }
    
    showCoverLetterLoadingState(elements);
    
    callCoverLetterGenerationAPI(
        jobId,
        elements.resumeSelect.value,
        elements.userComments ? elements.userComments.value : ''
    )
    .then(data => {
        if (data.error) {
            showCoverLetterErrorState(elements, data.error);
        } else {
            showCoverLetterPreviewState(elements, data);
        }
    })
    .catch(error => {
        console.error('Error generating cover letter:', error);
        showCoverLetterErrorState(elements, 'Network error. Please check your connection and try again.');
    });
    
    return false;
}

function saveGeneratedCoverLetterFromModal() {
    const form = document.getElementById('coverLetterGenerateFormInModal');
    const generatedText = document.getElementById('generated_cover_letter_text_modal');
    const coverLetterId = form.dataset.coverLetterId;
    
    if (!generatedText || !generatedText.value.trim()) {
        alert('Please enter cover letter text');
        return;
    }
    
    // Get job ID
    const pathParts = window.location.pathname.split('/');
    const jobId = pathParts[pathParts.indexOf('jobs') + 1] || (typeof currentJobId !== 'undefined' ? currentJobId : null);
    
    if (!jobId) {
        alert('Unable to determine job ID');
        return;
    }
    
    // Create a form to submit the cover letter
    const submitForm = document.createElement('form');
    submitForm.method = 'POST';
    submitForm.action = `/jobs/${encodeURIComponent(jobId)}/cover-letter/create`;
    
    // Add cover letter text
    const textInput = document.createElement('input');
    textInput.type = 'hidden';
    textInput.name = 'cover_letter_text';
    textInput.value = generatedText.value.trim();
    submitForm.appendChild(textInput);
    
    // Add cover letter name
    const nameInput = document.createElement('input');
    nameInput.type = 'hidden';
    nameInput.name = 'cover_letter_name';
    nameInput.value = `Generated Cover Letter - ${new Date().toLocaleDateString()}`;
    submitForm.appendChild(nameInput);
    
    // Link to job
    const linkInput = document.createElement('input');
    linkInput.type = 'hidden';
    linkInput.name = 'link_to_job';
    linkInput.value = 'true';
    submitForm.appendChild(linkInput);
    
    // If we have a cover letter ID, we need to update it instead
    if (coverLetterId) {
        // The cover letter was already created, just update it
        // For now, we'll submit the form which will create a new one
        // In Step 3, we'll add update functionality
    }
    
    document.body.appendChild(submitForm);
    submitForm.submit();
}

function resetCoverLetterFormState(elements) {
    const formFields = elements.form ? elements.form.querySelectorAll('.form-group') : [];
    formFields.forEach(field => {
        field.style.display = '';
    });
    
    elements.previewArea.style.display = 'none';
    elements.previewActions.style.display = 'none';
    elements.formActions.style.display = 'flex';
    elements.errorArea.style.display = 'none';
    elements.loadingSpinner.style.display = 'none';
    if (elements.generateButton) {
        elements.generateButton.disabled = false;
    }
}

function regenerateCoverLetterFromModal() {
    const elements = getCoverLetterModalElements();
    
    if (!elements.form) {
        console.error('Cover letter generate form not found');
        return;
    }
    
    // Check if we have a resume selected
    if (!elements.resumeSelect || !elements.resumeSelect.value) {
        // No resume selected, just reset the form
        resetCoverLetterFormState(elements);
        return;
    }
    
    const jobId = getJobIdFromURL();
    if (!jobId) {
        alert('Unable to determine job ID');
        resetCoverLetterFormState(elements);
        return;
    }
    
    showCoverLetterLoadingState(elements);
    
    callCoverLetterGenerationAPI(
        jobId,
        elements.resumeSelect.value,
        elements.userComments ? elements.userComments.value : ''
    )
    .then(data => {
        if (data.error) {
            showCoverLetterErrorState(elements, data.error);
        } else {
            showCoverLetterPreviewState(elements, data);
        }
    })
    .catch(error => {
        console.error('Error regenerating cover letter:', error);
        showCoverLetterErrorState(elements, `An unexpected error occurred: ${error.message}. Please try again.`);
    });
}

function regenerateCoverLetter() {
    // Reset preview and show form again
    const form = document.getElementById('coverLetterGenerateForm');
    if (!form) {
        console.error('Cover letter generate form not found');
        return;
    }
    
    // Check if we have a resume selected before resetting
    const resumeSelect = document.getElementById('generate_resume_select');
    const userComments = document.getElementById('generate_user_comments');
    
    if (!resumeSelect || !resumeSelect.value) {
        // No resume selected, just reset the form
        const formFields = form.querySelectorAll('.form-group');
        formFields.forEach(field => {
            field.style.display = '';
        });
        document.getElementById('generatePreviewArea').style.display = 'none';
        document.getElementById('generatePreviewActions').style.display = 'none';
        document.getElementById('generateFormActions').style.display = 'flex';
        document.getElementById('generateErrorArea').style.display = 'none';
        document.getElementById('generateLoadingSpinner').style.display = 'none';
        
        const generateButton = document.getElementById('generateButton');
        if (generateButton) {
            generateButton.disabled = false;
        }
        return;
    }
    
    // Hide form fields and show loading spinner immediately
    const formFields = form.querySelectorAll('.form-group');
    formFields.forEach(field => {
        field.style.display = 'none';
    });
    
    document.getElementById('generatePreviewArea').style.display = 'none';
    document.getElementById('generatePreviewActions').style.display = 'none';
    document.getElementById('generateFormActions').style.display = 'none';
    document.getElementById('generateErrorArea').style.display = 'none';
    document.getElementById('generateLoadingSpinner').style.display = 'block';
    
    // Clear any stored cover letter ID
    if (form.dataset.coverLetterId) {
        delete form.dataset.coverLetterId;
    }
    
    // Get job ID from current page
    const pathParts = window.location.pathname.split('/');
    const jobId = pathParts[pathParts.indexOf('jobs') + 1] || (typeof currentJobId !== 'undefined' ? currentJobId : null);
    
    if (!jobId) {
        alert('Unable to determine job ID');
        // Reset form on error
        formFields.forEach(field => {
            field.style.display = '';
        });
        document.getElementById('generateFormActions').style.display = 'flex';
        document.getElementById('generateLoadingSpinner').style.display = 'none';
        return;
    }
    
    // Prepare request data
    const requestData = {
        resume_id: parseInt(resumeSelect.value),
    };
    
    if (userComments && userComments.value.trim()) {
        requestData.user_comments = userComments.value.trim();
    }
    
    // Make API call directly
    fetch(`/api/jobs/${encodeURIComponent(jobId)}/cover-letter/generate`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
    })
    .then(response => response.json())
    .then(data => {
        const loadingSpinner = document.getElementById('generateLoadingSpinner');
        const previewArea = document.getElementById('generatePreviewArea');
        const errorArea = document.getElementById('generateErrorArea');
        const errorMessage = document.getElementById('generateErrorMessage');
        const formActions = document.getElementById('generateFormActions');
        const previewActions = document.getElementById('generatePreviewActions');
        const generateButton = document.getElementById('generateButton');
        
        loadingSpinner.style.display = 'none';
        if (generateButton) {
            generateButton.disabled = false;
        }
        
        if (data.error) {
            // Show error - restore form fields
            formFields.forEach(field => {
                field.style.display = '';
            });
            errorMessage.textContent = data.error;
            errorArea.style.display = 'block';
            formActions.style.display = 'flex';
        } else {
            // Show preview - keep form fields hidden
            const generatedText = document.getElementById('generated_cover_letter_text');
            if (generatedText) {
                generatedText.value = data.cover_letter_text || '';
            }
            
            // Store cover letter ID for saving
            if (data.cover_letter_id) {
                form.dataset.coverLetterId = data.cover_letter_id;
            }
            
            previewArea.style.display = 'block';
            formActions.style.display = 'none';
            previewActions.style.display = 'flex';
            
            // Scroll to preview
            previewArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    })
    .catch(error => {
        console.error('Error regenerating cover letter:', error);
        // Restore form fields on error
        formFields.forEach(field => {
            field.style.display = '';
        });
        const loadingSpinner = document.getElementById('generateLoadingSpinner');
        const errorArea = document.getElementById('generateErrorArea');
        const errorMessage = document.getElementById('generateErrorMessage');
        const formActions = document.getElementById('generateFormActions');
        const generateButton = document.getElementById('generateButton');
        
        loadingSpinner.style.display = 'none';
        if (generateButton) {
            generateButton.disabled = false;
        }
        errorMessage.textContent = 'Network error. Please check your connection and try again.';
        errorArea.style.display = 'block';
        formActions.style.display = 'flex';
    });
}

function regenerateFromExisting(coverLetterId) {
    // Open the generate modal and automatically trigger regeneration
    showCoverLetterGenerateModal();
    
    // Wait a bit for modal to open, then trigger regeneration
    setTimeout(() => {
        // Check if we have a resume selected
        const resumeSelect = document.getElementById('generate_resume_select');
        if (resumeSelect && resumeSelect.value) {
            // Automatically trigger regeneration
            regenerateCoverLetter();
        } else {
            // No resume selected, just show the form
            const form = document.getElementById('coverLetterGenerateForm');
            if (form) {
                form.reset();
            }
            
            const previewArea = document.getElementById('generatePreviewArea');
            const errorArea = document.getElementById('generateErrorArea');
            const formActions = document.getElementById('generateFormActions');
            const previewActions = document.getElementById('generatePreviewActions');
            const loadingSpinner = document.getElementById('generateLoadingSpinner');
            
            if (previewArea) previewArea.style.display = 'none';
            if (errorArea) errorArea.style.display = 'none';
            if (formActions) formActions.style.display = 'flex';
            if (previewActions) previewActions.style.display = 'none';
            if (loadingSpinner) loadingSpinner.style.display = 'none';
        }
    }, 100);
    
    // Store the cover letter ID for potential future use
    const form = document.getElementById('coverLetterGenerateForm');
    if (form && coverLetterId) {
        form.dataset.originalCoverLetterId = coverLetterId;
    }
    
    // Note: We can't pre-fill the resume because the cover letter doesn't store
    // which resume was used. The user will need to select a resume and click Generate.
    // This is a limitation of the current design - we could enhance it later by
    // storing the resume_id in the cover letter record.
}

function showGenerationHistory() {
    const modal = document.getElementById('generationHistoryModal');
    if (!modal) {
        console.error('Generation history modal not found');
        return;
    }
    
    // Show modal - remove the inline style with !important
    modal.removeAttribute('style');
    modal.style.display = 'flex';
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    
    // Load generation history
    loadGenerationHistory();
}

function closeGenerationHistoryModal() {
    const modal = document.getElementById('generationHistoryModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

function loadGenerationHistory() {
    const historyList = document.getElementById('generationHistoryList');
    if (!historyList) return;
    
    // Show loading
    historyList.innerHTML = '<div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i><span>Loading generation history...</span></div>';
    
    // Get current job ID
    const jobId = typeof currentJobId !== 'undefined' ? currentJobId : null;
    if (!jobId) {
        historyList.innerHTML = '<div class="error-message">Unable to determine job ID</div>';
        return;
    }
    
    // Fetch generation history
    fetch(`/api/jobs/${jobId}/cover-letter/generation-history`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            const history = data.history || [];
            if (history.length === 0) {
                historyList.innerHTML = '<div class="empty-state"><p>No generation history found.</p></div>';
                return;
            }
            
            // Render history list
            historyList.innerHTML = history.map((item, index) => {
                const date = new Date(item.created_at).toLocaleString();
                return `
                    <div class="history-item" style="padding: 1rem; border-bottom: 1px solid #eee;">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem;">
                            <div>
                                <strong>${item.cover_letter_name || 'Cover Letter'}</strong>
                                <span style="color: #666; font-size: 0.875rem; margin-left: 0.5rem;">${date}</span>
                            </div>
                            ${index === 0 ? '<span class="badge" style="background-color: #28a745; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem;">Current</span>' : ''}
                        </div>
                        <div style="margin-top: 0.5rem;">
                            <button class="btn btn-sm btn-secondary" onclick="useHistoryItem(${item.cover_letter_id})" style="margin-right: 0.5rem;">
                                <i class="fas fa-check"></i> Use This
                            </button>
                            <a href="/jobs/${jobId}/cover-letter/${item.cover_letter_id}/download" class="btn btn-sm btn-secondary">
                                <i class="fas fa-download"></i> Download
                            </a>
                        </div>
                    </div>
                `;
            }).join('');
        })
        .catch(error => {
            console.error('Error loading generation history:', error);
            historyList.innerHTML = '<div class="error-message">Failed to load generation history. Please try again.</div>';
        });
}

function useHistoryItem(coverLetterId) {
    // Close the history modal
    closeGenerationHistoryModal();
    
    // Reload the page to show the selected cover letter
    // The backend should handle linking this cover letter to the job application
    window.location.reload();
}
