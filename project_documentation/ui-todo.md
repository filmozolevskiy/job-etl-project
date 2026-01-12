# UI/UX Improvements TODO List

This document tracks UI/UX improvements and design consistency tasks for the Campaign Management UI.

**📖 Related Documentation:**
- **[Implementation TODO](implementation-todo.md)** – Core feature implementation tasks
- **[Bugs TODO](bugs-todo.md)** – Bug tracking and fixes

---

## Open UI/UX Tasks

### UI-1: Standardize Jobs Table to Match Campaign Table Style

- **Date Added**: 2026-01-XX
- **Description**: The jobs table should have the same card-like table design as the campaign table. Currently, jobs are displayed in a standard table format, but they should match the campaign page's card-like table with mobile card views.
- **Location**: 
  - `campaign_ui/templates/view_campaign.html` - Jobs table section (lines 148-246)
  - `campaign_ui/templates/jobs.html` - Jobs list page (if still exists)
  - `campaign_ui/static/css/pages.css` - Table and card styles
  - `campaign_ui/static/css/responsive.css` - Mobile card styles
- **Acceptance Criteria:**
  - Jobs table uses the same card-like styling as campaign table
  - Desktop view shows table with card-like appearance (rounded corners, shadows, spacing)
  - Mobile view shows card layout matching campaign page mobile cards
  - Company logos display in table cells (if available)
  - Status badges match campaign page styling
  - Fit score badges match campaign page styling
  - Action buttons styled consistently
  - Responsive breakpoints match campaign page
- **Update Files:**
  - `campaign_ui/templates/view_campaign.html` (update jobs table structure)
  - `campaign_ui/static/css/pages.css` (ensure consistent table/card styles)
  - `campaign_ui/static/css/responsive.css` (ensure mobile cards match)
- **Status**: Open
- **Priority**: Medium

---

### UI-2: Fix Filter Order in Job Details Page

- **Date Added**: 2026-01-XX
- **Description**: The status filter dropdown in the job details page should have the same order as the campaign page. Currently, the order may be different, causing inconsistency in the user experience.
- **Location**: 
  - `campaign_ui/templates/job_details.html` - Status dropdown (line 218-226)
  - `campaign_ui/templates/view_campaign.html` - Status filter order reference
- **Current Order** (job details): waiting → applied → approved → interview → offer → rejected → archived
- **Expected Order** (matching campaign page): waiting → approved → applied → interview → offer → rejected → archived
- **Acceptance Criteria:**
  - Status dropdown in job details page matches campaign page order
  - Order: waiting → approved → applied → interview → offer → rejected → archived
  - Consistent user experience across pages
- **Update Files:**
  - `campaign_ui/templates/job_details.html` (reorder status options)
- **Status**: Open
- **Priority**: Low

---

### UI-3: Remove Duplicate Buttons on Job Details Page

- **Date Added**: 2026-01-XX
- **Description**: The job details page has duplicate "Add" buttons for resume and cover letter. There's an "Add" button in the document item header and another "Add Resume"/"Add Cover Letter" button in the empty state. These should be consolidated to avoid confusion.
- **Location**: 
  - `campaign_ui/templates/job_details.html` - Application Documents section (lines 243-347)
  - Resume section: Button at line 251-254 (header) and line 281-283 (empty state)
  - Cover Letter section: Button at line 291-294 (header) and line 340-342 (empty state)
- **Acceptance Criteria:**
  - Remove duplicate "Add Resume" button from empty state (keep header button)
  - Remove duplicate "Add Cover Letter" button from empty state (keep header button)
  - Empty state should show message but not duplicate button
  - Header button should handle both "Add" and "Change" states
  - User experience is cleaner without redundant buttons
- **Update Files:**
  - `campaign_ui/templates/job_details.html` (remove duplicate buttons from empty states)
- **Status**: Open
- **Priority**: Low

---

### UI-4: Add "Done by: User" Indicators for Document Actions

- **Date Added**: 2026-01-XX
- **Description**: When users add or modify documents (resume, cover letter, notes), the UI should indicate who performed the action. This provides better tracking and transparency, especially in multi-user scenarios or when reviewing application history.
- **Location**: 
  - `campaign_ui/templates/job_details.html` - Application Documents section
  - `campaign_ui/templates/job_details.html` - Notes section
  - Status history section (if applicable)
- **Acceptance Criteria:**
  - When a document is added, show "Done by: [Username]" or "Done by: You" if current user
  - Display user indicator near document upload timestamp
  - Show user indicator in status history when documents are linked/unlinked
  - Show user indicator for notes (who added/edited the note)
  - Format: "Done by: [Username]" or "Done by: You" with appropriate styling
  - User indicator appears in document info section and history
- **Update Files:**
  - `campaign_ui/templates/job_details.html` (add user indicators)
  - `services/documents/document_service.py` (store user_id with document actions if not already)
  - `services/jobs/job_status_service.py` (include user info in status history if not already)
  - `campaign_ui/static/css/pages.css` (style user indicators)
- **Status**: Open
- **Priority**: Medium

---

### UI-5: Convert All Time Displays to Local Timezone

- **Date Added**: 2026-01-XX
- **Description**: Currently, all times displayed on the website are in UTC timezone, not the user's local time. This causes confusion as users see times that don't match their local timezone. All time displays should be converted to the user's local timezone for better user experience.
- **Location**: 
  - `campaign_ui/app.py` - UTC timezone setup (line 58: `timezone_utc=UTC`)
  - `campaign_ui/templates/view_campaign.html` - Job posting dates (lines 179-199, 290-310)
  - `campaign_ui/templates/job_details.html` - Posted dates, status history dates (lines 177-184, 450-463, 1534-1548)
  - `campaign_ui/templates/dashboard.html` - Recent jobs dates (lines 77-97)
  - `campaign_ui/templates/jobs.html` - Updated dates (lines 202-203, 296-298)
  - `campaign_ui/templates/documents.html` - Document created dates (lines 44, 115)
  - `campaign_ui/static/js/common.js` - `formatDateTime()` function (lines 63-73)
  - `campaign_ui/templates/job_details.html` - `formatStatusDate()` JavaScript function (lines 1534-1548)
- **Root Cause**: 
  - Server-side templates use `.strftime()` on UTC datetime objects without timezone conversion
  - JavaScript functions use UTC methods (`getUTCFullYear()`, `getUTCMonth()`, etc.) instead of local time methods
  - No consistent timezone conversion mechanism in place
- **Acceptance Criteria:**
  - All times displayed in templates are converted to user's local timezone
  - JavaScript functions use local time methods instead of UTC methods
  - Date/time displays show correct local time for the user's browser timezone
  - Relative time displays ("Today", "2 days ago") calculate correctly based on local time
  - Status history timestamps show in local time
  - Document creation dates show in local time
  - Job posting dates show in local time
  - Dashboard recent jobs show in local time
- **Implementation Approach:**
  - **Option 1 (Recommended)**: Use JavaScript to convert UTC timestamps to local time on the client side
    - Pass UTC ISO strings from server
    - Use JavaScript `Date` object and `toLocaleString()` or similar methods
    - Update all JavaScript date formatting functions
  - **Option 2**: Convert to local timezone on server-side using user's timezone preference
    - Requires storing user timezone preference
    - More complex but allows server-side rendering with correct timezone
- **Update Files:**
  - `campaign_ui/app.py` (update timezone handling, pass UTC ISO strings to templates)
  - `campaign_ui/templates/view_campaign.html` (use JavaScript for local time conversion)
  - `campaign_ui/templates/job_details.html` (update `formatStatusDate()` to use local time, update template date displays)
  - `campaign_ui/templates/dashboard.html` (convert dates to local time)
  - `campaign_ui/templates/jobs.html` (convert dates to local time)
  - `campaign_ui/templates/documents.html` (convert dates to local time)
  - `campaign_ui/static/js/common.js` (ensure `formatDateTime()` uses local time consistently)
  - Create utility JavaScript function for consistent local time formatting across all pages
- **Status**: Open
- **Priority**: Medium

---

### UI-6: Limit Visible Skills and Add Modal to View All Skills

- **Date Added**: 2026-01-XX
- **Description**: When a job has many skills (e.g., 20+), displaying all of them can clutter the UI and make the job details page hard to scan. We should limit the number of visible skills (e.g., show first 10-15) and add a "View All Skills" button/link that opens a modal displaying all skills in an organized way.
- **Location**: 
  - `campaign_ui/templates/job_details.html` - Skills display section (lines 72-93)
  - `campaign_ui/static/css/pages.css` - Skills list styling (lines 474-494)
  - `campaign_ui/static/js/` - Modal functionality (may need new file or add to existing)
- **Current Behavior**: All skills are displayed as skill tags in the skills list, regardless of how many there are.
- **Acceptance Criteria:**
  - Show only a limited number of skills initially (e.g., first 10-15 skills)
  - Display a "View All Skills" or "+X more skills" button/link when there are more skills than the limit
  - Clicking the button opens a modal that displays all skills
  - Modal shows skills in an organized layout (e.g., grid or list)
  - Modal is accessible (keyboard navigation, close button, ESC key to close)
  - Modal displays job title/company for context
  - Skills are displayed as tags in the modal (consistent styling)
  - Works for both regular extracted skills and ChatGPT-extracted skills
  - Mobile responsive design
- **Implementation Approach:**
  1. Limit visible skills in template (e.g., `skills_parsed[:15]`)
  2. Count total skills and show "+X more" link if there are more than the limit
  3. Store all skills in a data attribute or JavaScript variable
  4. Create modal HTML structure (can reuse existing modal patterns)
  5. Add JavaScript to open/close modal and populate with all skills
  6. Style modal to match existing design system
- **Update Files:**
  - `campaign_ui/templates/job_details.html` (limit visible skills, add "View All" button, add modal HTML)
  - `campaign_ui/static/css/pages.css` (style skills modal if needed)
  - `campaign_ui/static/js/` (add modal functionality - can be in existing JS file or new file)
- **Status**: Open
- **Priority**: Low

---

### UI-7: Add Page Number Navigation to Pagination

- **Date Added**: 2026-01-XX
- **Description**: Currently, pagination only has Previous (←) and Next (→) buttons, which makes it tedious to navigate to a specific page when there are many pages (e.g., page 50 of 100). Users should be able to jump directly to a desired page number, either by clicking page number buttons or by typing a page number in an input field.
- **Location**: 
  - `campaign_ui/templates/view_campaign.html` - Pagination controls (lines 350-354)
  - `campaign_ui/templates/view_campaign.html` - Pagination JavaScript functions (lines 640-815)
  - `campaign_ui/static/css/pages.css` - Pagination styling (lines 1682-1710)
- **Current Behavior**: 
  - Pagination shows: `[←] 1 of 10 [→]`
  - Users can only navigate page by page using Previous/Next buttons
  - There's a `goToPage()` function that can navigate to a specific page, but no UI to trigger it
- **Acceptance Criteria:**
  - Users can see and click on page number buttons (e.g., 1, 2, 3, 4, 5, ...)
  - Page number buttons show current page as active/highlighted
  - For many pages, show ellipsis (...) and smart truncation (e.g., "1 ... 5 6 7 ... 20")
  - Users can type a page number in an input field and press Enter to jump to that page
  - Input field validates page number (must be between 1 and total pages)
  - Shows error message if invalid page number is entered
  - Works with existing search and filter functionality
  - Mobile responsive (may need different layout for mobile)
  - Accessible (keyboard navigation, ARIA labels)
- **Implementation Approach:**
  1. **Page Number Buttons**:
     - Display page numbers around current page (e.g., show 5-7 page numbers)
     - Show first page, last page, and ellipsis for gaps
     - Highlight current page
     - Click handler calls `goToPage(pageNumber)`
  2. **Page Number Input** (Optional but recommended):
     - Add input field next to pagination controls
     - Allow users to type page number and press Enter
     - Validate input (must be number, within range)
     - Show error message for invalid input
  3. **Smart Truncation Logic**:
     - If total pages <= 7: Show all pages
     - If total pages > 7: Show first, last, current page ± 2, and ellipsis
     - Example: "1 ... 5 6 [7] 8 9 ... 20" (where [7] is current page)
- **Update Files:**
  - `campaign_ui/templates/view_campaign.html` (add page number buttons and/or input field to pagination HTML)
  - `campaign_ui/templates/view_campaign.html` (add JavaScript for page number button clicks and input handling)
  - `campaign_ui/static/css/pages.css` (style page number buttons, input field, active state, ellipsis)
  - Consider adding similar pagination to other pages that use pagination (if any)
- **Status**: Open
- **Priority**: Medium

---

### UI-8: Move Campaign Settings to Top of Campaign Page with Toggle Switch

- **Date Added**: 2026-01-XX
- **Description**: Currently, the "Campaign Settings" section with the "Active" checkbox is located at the bottom of the campaign edit form. Users need to go to the edit page to activate/deactivate a campaign. We should move this functionality to the top of the campaign view page (view_campaign.html) and make it a toggle switch for easier activation/deactivation without navigating to the edit page.
- **Location**: 
  - `campaign_ui/templates/view_campaign.html` - Campaign view page (currently shows status badge but no toggle)
  - `campaign_ui/templates/edit_campaign.html` - Campaign Settings section (lines 182-199)
  - `campaign_ui/templates/create_campaign.html` - Campaign Settings section (lines 187-204)
  - `campaign_ui/app.py` - `toggle_active()` route already exists (lines 977-991)
- **Current Behavior**: 
  - Campaign Settings section is at the bottom of the edit form
  - Uses a checkbox input for "Active" status
  - Users must navigate to edit page to change active status
  - View page shows status badge but no way to toggle it
- **Acceptance Criteria:**
  - Campaign Settings section appears at the top of the campaign view page (before stats grid or as first stat card)
  - Uses a toggle switch UI component (not a checkbox) for activate/deactivate
  - Toggle switch visually shows active/inactive state clearly
  - Toggle switch updates campaign status via AJAX (using existing `/campaign/<id>/toggle-active` route)
  - No page reload required when toggling
  - Shows success/error feedback when toggling
  - Toggle switch is disabled during DAG execution (if applicable)
  - Status badge updates immediately when toggle is changed
  - Mobile responsive design
  - Accessible (keyboard navigation, ARIA labels)
- **Implementation Approach:**
  1. **Add Toggle Switch to View Page**:
     - Create toggle switch component at top of view_campaign.html
     - Position it prominently (e.g., as first stat card or above stats grid)
     - Style toggle switch to match design system
  2. **AJAX Toggle Functionality**:
     - Use existing `/campaign/<id>/toggle-active` POST route
     - Add JavaScript to handle toggle switch change
     - Update status badge and page state without reload
     - Show success/error messages
  3. **Optional**: Keep Campaign Settings in edit form for consistency, or remove if redundant
- **Update Files:**
  - `campaign_ui/templates/view_campaign.html` (add toggle switch at top, add JavaScript for AJAX toggle)
  - `campaign_ui/static/css/components.css` or `pages.css` (add toggle switch styling)
  - `campaign_ui/static/js/` (add toggle switch JavaScript functionality)
  - Consider updating `campaign_ui/templates/edit_campaign.html` to use toggle switch instead of checkbox for consistency
- **Status**: Open
- **Priority**: Medium

---

## Completed UI/UX Tasks

_No completed UI/UX tasks yet._

---

## Notes

- UI tasks should be prioritized based on user impact and design consistency
- All UI changes should maintain responsive design and accessibility
- Design patterns should be consistent across all pages
- Mobile-first approach should be maintained
