/**
 * Documents page functionality
 */

// Constants
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
const ALLOWED_FILE_TYPES = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
const ALLOWED_FILE_EXTENSIONS = ['.pdf', '.docx'];

document.addEventListener('DOMContentLoaded', () => {
    // Close modals when clicking outside (same as jobDetails.js)
    window.onclick = function(event) {
        const modals = document.querySelectorAll('[id$="Modal"]');
        modals.forEach(modal => {
            if (event.target === modal) {
                if (modal.id === 'resumeUploadModal') {
                    closeResumeUploadModal();
                } else if (modal.id === 'coverLetterModal') {
                    closeCoverLetterModal();
                } else if (modal.id === 'deleteConfirmModal') {
                    closeDeleteConfirmModal();
                } else if (modal.id === 'coverLetterTextViewModal') {
                    closeCoverLetterTextViewModal();
                }
            }
        });
    };
});

// ============================================================
// Resume Upload Modal Functions
// ============================================================

function showResumeUploadModal() {
    const modal = document.getElementById('resumeUploadModal');
    if (modal) {
        modal.style.display = 'flex';
        modal.classList.add('modal-active');
    }
}

function closeResumeUploadModal() {
    const modal = document.getElementById('resumeUploadModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('modal-active');
        const form = document.getElementById('resumeUploadForm');
        if (form) {
            form.reset();
        }
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

// ============================================================
// Cover Letter Modal Functions
// ============================================================

function showCoverLetterModal() {
    const modal = document.getElementById('coverLetterModal');
    if (modal) {
        modal.style.display = 'flex';
        modal.classList.add('modal-active');
        toggleCoverLetterType(); // Ensure correct form fields are shown
    }
}

function closeCoverLetterModal() {
    const modal = document.getElementById('coverLetterModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('modal-active');
        const form = document.getElementById('coverLetterForm');
        if (form) {
            form.reset();
            toggleCoverLetterType(); // Reset to text mode
        }
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

// ============================================================
// Delete Confirmation Functions
// ============================================================

function confirmDeleteResume(resumeId, resumeName) {
    const modal = document.getElementById('deleteConfirmModal');
    const message = document.getElementById('deleteConfirmMessage');
    const form = document.getElementById('deleteForm');
    
    if (modal && message && form) {
        message.textContent = `Are you sure you want to delete "${resumeName}"? This action cannot be undone.`;
        form.action = `/documents/resume/${resumeId}/delete`;
        modal.style.display = 'flex';
        modal.classList.add('modal-active');
    }
}

function confirmDeleteCoverLetter(coverLetterId, coverLetterName) {
    const modal = document.getElementById('deleteConfirmModal');
    const message = document.getElementById('deleteConfirmMessage');
    const form = document.getElementById('deleteForm');
    
    if (modal && message && form) {
        message.textContent = `Are you sure you want to delete "${coverLetterName}"? This action cannot be undone.`;
        form.action = `/documents/cover-letter/${coverLetterId}/delete`;
        modal.style.display = 'flex';
        modal.classList.add('modal-active');
    }
}

function closeDeleteConfirmModal() {
    const modal = document.getElementById('deleteConfirmModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('modal-active');
    }
}

// ============================================================
// Cover Letter Text View Functions
// ============================================================

function viewCoverLetterText(coverLetterId) {
    // Fetch cover letter text via API
    fetch(`/api/user/cover-letters`)
        .then(response => response.json())
        .then(data => {
            const coverLetter = data.cover_letters.find(cl => cl.cover_letter_id === coverLetterId);
            if (coverLetter && coverLetter.cover_letter_text) {
                const modal = document.getElementById('coverLetterTextViewModal');
                const title = document.getElementById('coverLetterTextViewTitle');
                const content = document.getElementById('coverLetterTextViewContent');
                
                if (modal && title && content) {
                    title.textContent = coverLetter.cover_letter_name || 'Cover Letter';
                    content.textContent = coverLetter.cover_letter_text;
                    modal.style.display = 'flex';
                    modal.classList.add('modal-active');
                }
            } else {
                alert('Cover letter text not found');
            }
        })
        .catch(error => {
            console.error('Error fetching cover letter:', error);
            alert('Error loading cover letter text');
        });
}

function closeCoverLetterTextViewModal() {
    const modal = document.getElementById('coverLetterTextViewModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('modal-active');
    }
}

