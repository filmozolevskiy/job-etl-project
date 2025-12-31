/**
 * Job Details page specific functionality
 */

document.addEventListener('DOMContentLoaded', () => {
    // Handle comment form submission
    const commentForm = document.querySelector('.comment-form');
    if (commentForm) {
        commentForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const textarea = commentForm.querySelector('textarea');
            const comment = textarea.value.trim();
            
            if (comment) {
                // In a real app, this would send the comment to the server
                addCommentToUI(comment);
                textarea.value = '';
                Utils.showNotification('Comment added successfully', 'success');
            }
        });
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

    // Handle document selection
    const documentSelects = document.querySelectorAll('.document-select');
    documentSelects.forEach(select => {
        select.addEventListener('change', (e) => {
            // In a real app, this would load the selected document
            const documentPreview = select.closest('.document-selector').nextElementSibling;
            if (documentPreview && documentPreview.classList.contains('document-preview')) {
                documentPreview.textContent = `Preview of ${e.target.value}...`;
            }
        });
    });
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

