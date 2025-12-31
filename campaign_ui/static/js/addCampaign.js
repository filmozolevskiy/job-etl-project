/**
 * Add Campaign page specific functionality
 */

document.addEventListener('DOMContentLoaded', () => {
    // Check if user is admin (in real app, this would come from server/session)
    // For mockup purposes, set to true to show the section, false to hide it
    const isAdmin = true; // Change to false to hide ranking weights section for non-admins
    
    // Show/hide ranking weights section based on admin status
    const rankingSection = document.getElementById('ranking-weights-section');
    if (isAdmin && rankingSection) {
        rankingSection.classList.remove('hidden');
    }
    
    // Calculate weight sum (only if section is visible)
    if (isAdmin) {
        const weightInputs = document.querySelectorAll('input[id^="ranking_weight"]');
        const weightSum = document.getElementById('weight-sum');
        
        function updateWeightSum() {
            let sum = 0;
            weightInputs.forEach(input => {
                sum += parseFloat(input.value) || 0;
            });
            if (weightSum) {
                weightSum.textContent = sum.toFixed(1);
                
                if (sum === 100) {
                    weightSum.parentElement.classList.add('weight-valid');
                    weightSum.parentElement.classList.remove('weight-invalid');
                } else {
                    weightSum.parentElement.classList.add('weight-invalid');
                    weightSum.parentElement.classList.remove('weight-valid');
                }
            }
        }
        
        weightInputs.forEach(input => {
            input.addEventListener('input', updateWeightSum);
        });
    }
    
    // Modal functions
    function openRankingModal() {
        document.getElementById('rankingModal').classList.add('active');
    }
    
    function closeRankingModal() {
        document.getElementById('rankingModal').classList.remove('active');
    }
    
    // Modal event listeners
    const rankingInfoIcon = document.getElementById('rankingInfoIcon');
    if (rankingInfoIcon) {
        rankingInfoIcon.addEventListener('click', openRankingModal);
    }
    
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

