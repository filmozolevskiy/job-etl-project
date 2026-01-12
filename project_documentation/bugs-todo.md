# Bugs TODO List

This document tracks bugs that have been identified and need to be fixed later.

## Bug Tracking Format

Each bug entry should include:
- **Date Found**: When the bug was discovered
- **Description**: Clear description of the issue
- **Location**: File(s) or component(s) affected
- **Severity**: Critical / High / Medium / Low
- **Status**: Open / In Progress / Fixed / Deferred
- **Notes**: Any additional context or workarounds

---

## Open Bugs

### Bug #14: Action Dropdown Menu Allows Accidental Clicks on Elements Below

- **Date Found**: 2026-01-XX
- **Description**: When opening the campaign actions dropdown menu (three-dot button), users can still see and accidentally click on buttons or elements below the dropdown menu. The dropdown doesn't properly block interaction with elements behind it, causing accidental clicks on buttons in rows below the dropdown.
- **Location**: 
  - `campaign_ui/templates/list_campaigns.html` - Action dropdown menu (lines 90-105, 163-175)
  - `campaign_ui/static/css/components.css` - Action dropdown styling (lines 1468-1581, specifically z-index at line 1511)
  - `campaign_ui/static/js/common.js` - Action dropdown JavaScript (lines 432-476)
- **Root Cause**: 
  1. **No Backdrop/Overlay**: The dropdown menu doesn't have a backdrop or overlay to block clicks on elements below it (unlike modals which have `.modal-overlay`)
  2. **Z-Index May Be Insufficient**: The dropdown has `z-index: 1000`, but if other elements have higher z-index or the dropdown is positioned in a way that doesn't fully cover buttons below, clicks can pass through
  3. **No Pointer Events Blocking**: The dropdown doesn't prevent pointer events on elements below it when open
  4. **Positioning Issue**: The dropdown is positioned absolutely but may not fully cover the area where buttons below are located
- **Severity**: Medium
- **Status**: Open
- **Acceptance Criteria:**
  - When dropdown menu is open, users cannot click on buttons or elements below it
  - Dropdown menu properly blocks interaction with elements behind it
  - Clicking outside the dropdown closes it (already implemented, but should work correctly)
  - Dropdown menu has sufficient z-index to appear above all table elements
  - No accidental clicks on buttons in rows below when dropdown is open
  - Works correctly on both desktop and mobile views
- **Fix Approach:**
  1. **Option 1 (Recommended)**: Add a backdrop/overlay when dropdown is open
     - Create a transparent overlay that covers the entire table/area
     - Position it behind the dropdown menu but above other content
     - Close dropdown when clicking on the backdrop
  2. **Option 2**: Increase z-index and ensure proper positioning
     - Increase dropdown menu z-index to be higher than all table elements
     - Ensure dropdown menu fully covers the area where buttons below are located
     - Add `pointer-events: none` to elements below when dropdown is open
  3. **Option 3**: Close dropdown immediately when opening (prevent interaction)
     - Close dropdown when user clicks outside (already implemented)
     - Ensure click events on buttons below are properly blocked
- **Update Files:**
  - `campaign_ui/static/css/components.css` (add backdrop/overlay styling, increase z-index if needed, add pointer-events handling)
  - `campaign_ui/static/js/common.js` (add backdrop creation/removal logic when dropdown opens/closes)
  - `campaign_ui/templates/list_campaigns.html` (add backdrop element if using HTML approach)
- **Related**: This may also affect other dropdown menus in the application if they have the same issue

### Bug #13: Performance Issue - Campaign Pages Load Slowly with Many Jobs

- **Date Found**: 2026-01-XX
- **Description**: When a campaign has a large number of jobs (e.g., 1000+), the campaign page takes a very long time to load. All jobs are loaded from the database at once and rendered in the template, causing slow initial page load times and poor user experience. This affects both the database query time and the client-side rendering time.
- **Location**: 
  - `campaign_ui/app.py` - `view_campaign()` route (lines 616-624)
  - `services/jobs/job_service.py` - `get_jobs_for_campaign()` method (lines 33-78)
  - `services/jobs/queries.py` - `GET_JOBS_FOR_CAMPAIGN_BASE` query (no LIMIT clause)
  - `campaign_ui/templates/view_campaign.html` - Jobs table rendering (all jobs rendered at once)
- **Root Cause**: 
  1. **No Server-Side Pagination**: The `view_campaign()` route calls `get_jobs_for_campaign()` without `limit` or `offset` parameters, loading all jobs at once (line 619-621)
  2. **No LIMIT in Query**: The `GET_JOBS_FOR_CAMPAIGN_BASE` query doesn't have a default LIMIT, so it returns all matching jobs
  3. **All Jobs Rendered**: The template renders all jobs in the DOM at once, even though client-side pagination shows only 20 per page
  4. **Complex Query**: The query joins multiple tables (dim_ranking, fact_jobs, dim_companies, job_notes, user_job_status) which can be slow for large datasets
- **Severity**: High (Performance)
- **Status**: Open
- **Acceptance Criteria:**
  - Campaign pages load quickly (< 2 seconds) even with 1000+ jobs
  - Initial page load only fetches a limited number of jobs (e.g., 50-100)
  - Users can load more jobs on demand (infinite scroll, "Load More" button, or pagination)
  - Database query time is reduced for large campaigns
  - Client-side rendering time is acceptable
  - Search and filtering still work correctly with pagination
  - Sorting works with paginated data
- **Implementation Strategies** (choose one or combine):
  1. **Server-Side Pagination** (Recommended):
     - Add pagination parameters to `view_campaign()` route (page number, page size)
     - Use `limit` and `offset` in `get_jobs_for_campaign()` call
     - Add pagination controls to template (page numbers, "Load More" button)
     - Update URL parameters to reflect current page
  2. **Lazy Loading / Infinite Scroll**:
     - Load initial batch of jobs (e.g., 50)
     - Load additional jobs as user scrolls or clicks "Load More"
     - Use AJAX to fetch more jobs without page reload
  3. **Virtual Scrolling**:
     - Only render visible jobs in the DOM
     - Use a virtual scrolling library or custom implementation
     - Reduces DOM size and improves rendering performance
  4. **Optimize Query**:
     - Add database indexes on frequently queried columns
     - Consider materialized views for complex joins
     - Cache frequently accessed data
- **Update Files:**
  - `campaign_ui/app.py` (add pagination parameters to `view_campaign()` route)
  - `services/jobs/job_service.py` (ensure `limit`/`offset` are used, add total count method)
  - `campaign_ui/templates/view_campaign.html` (add pagination controls, update JavaScript for pagination)
  - `services/jobs/queries.py` (add query to get total job count for pagination)
  - Consider adding database indexes if needed
- **Related**: This issue may also affect the dashboard and other pages that display large lists of jobs

### Bug #12: Sorting Not Working for Date Columns (Posted At)

- **Date Found**: 2026-01-XX
- **Description**: Sorting by date columns (e.g., "Posted At") is not working. When users select "Date (Newest)" or "Date (Oldest)" from the sort dropdown, or click on the "Posted At" column header, the table order does not change. This affects both the dropdown sort filter and the clickable column header sorting.
- **Location**: 
  - `campaign_ui/templates/view_campaign.html` - Sort filter dropdown handler (lines 603-638)
  - `campaign_ui/templates/view_campaign.html` - Date column display (lines 178-199)
  - `campaign_ui/static/js/common.js` - TableSorter implementation (lines 281-351)
- **Root Cause**: 
  1. **Dropdown Sort Issue**: The date sorting cases in the dropdown filter (`date-newest` and `date-oldest`) return `0` without any actual date parsing or comparison (lines 614-617). The code has a comment "Would need actual date parsing" indicating it was never implemented.
  2. **Column Header Sort Issue**: The date column displays relative dates like "Today", "2 days ago", "1 week ago" instead of actual dates. The `TableSorter` in `common.js` tries to sort by text content, but relative date strings cannot be sorted correctly (e.g., "Today" vs "2 days ago" won't sort properly).
  3. **Date Format Problem**: Dates are displayed as relative strings which makes proper date sorting impossible without parsing the underlying date value from data attributes.
- **Severity**: Medium
- **Status**: Open
- **Acceptance Criteria:**
  - Dropdown sort "Date (Newest)" sorts jobs by posted date, newest first
  - Dropdown sort "Date (Oldest)" sorts jobs by posted date, oldest first
  - Clicking "Posted At" column header toggles between ascending/descending date order
  - Sorting works correctly regardless of how dates are displayed (relative or absolute)
  - Date sorting uses actual date values, not displayed text
- **Fix Approach:**
  1. Store actual date values in data attributes on table rows (e.g., `data-posted-date="2026-01-15T10:30:00Z"`)
  2. Update dropdown sort handler to parse and compare actual date values from data attributes
  3. Update `TableSorter` to detect date columns and parse dates from data attributes instead of text content
  4. Ensure dates are stored in ISO format for reliable parsing
- **Update Files:**
  - `campaign_ui/templates/view_campaign.html` (add data attributes with actual dates, fix dropdown sort handler)
  - `campaign_ui/static/js/common.js` (update TableSorter to handle date columns)
  - Consider adding date parsing utility function for consistent date handling

### Bug #11: Dashboard Needs Enhanced Metrics and Features

- **Date Found**: 2026-01-XX
- **Description**: The dashboard currently shows basic metrics but needs enhancement with:
  1. **Active Campaigns**: Should display as "active campaigns / all campaigns" (currently shows single number)
  2. **Jobs Processed**: Should display as "jobs applied / jobs found" (currently shows single number)
  3. **Average Fit Score**: Missing - should calculate and display average `rank_score` for all jobs
  4. **Activity Per Day Chart**: Currently only shows "Jobs Found" and "Jobs Applied". Should include:
     - Jobs found
     - Jobs approved
     - Jobs rejected
     - Jobs applied
     - Interviews
     - Offers
  5. **Last Applied Jobs**: Currently shows list with link to `view_jobs` route (which should be removed). Should:
     - Display links to last applied jobs
     - "View All" button opens modal with all applied jobs (not redirect to separate page)
  6. **Favorite Jobs**: Missing feature - users should be able to:
     - Mark jobs as favorite from job details page
     - View favorite jobs on dashboard
     - "View All" button opens modal with all favorite jobs
- **Location**: 
  - `campaign_ui/app.py` - `dashboard()` route
  - `campaign_ui/templates/dashboard.html` - Dashboard template
  - `services/jobs/job_service.py` - Missing methods for metrics
  - Database schema - Missing `is_favorite` column or `user_favorite_jobs` table
- **Severity**: Medium (Enhancement)
- **Status**: Open
- **Related Tasks**: See implementation-todo.md tasks 3.15.6 and 3.15.7

---

## Fixed Bugs

### Bug #9: Authentication Redirect Issue Caused by before_request Handler and Rapid Page Navigation

- **Date Found**: 2026-01-11
- **Date Fixed**: 2026-01-11
- **Description**: Users were being redirected to the login page when accessing job details pages (and potentially other protected routes) even though they were already authenticated. Three related issues were identified:
  1. **Initial Issue**: A `@app.before_request` handler accessed `current_user.is_authenticated` before Flask-Login had a chance to load the user from the session, causing false authentication failures.
  2. **Rapid Navigation Issue**: When switching between pages quickly, multiple simultaneous requests would call `load_user()`, each creating a new database connection. This could cause database connection pool exhaustion, race conditions, or slow responses that made the session appear invalid, resulting in redirects to the login page.
  3. **Session Invalidation Issue**: When navigating away from a page and returning to it, users were redirected to login. This was caused by Flask-Login's `session_protection = "strong"` setting, which aggressively invalidates sessions when it detects any change in request headers (IP address, user agent, etc.), even during normal navigation.
- **Location**: 
  - `campaign_ui/app.py` - `@app.before_request` handler (removed)
  - `campaign_ui/app.py` - `load_user()` function (optimized with caching)
  - All routes protected by `@login_required` were potentially affected
- **Severity**: High
- **Status**: Fixed
- **Resolution**:
  - **Root Cause #1**: The `before_request` handler accessed `current_user.is_authenticated` before Flask-Login's `@login_required` decorator had a chance to load the user from the session. Flask-Login's user loading happens when the decorator is evaluated, which occurs after `before_request` handlers run.
  - **Root Cause #2**: The `load_user()` function created a new database connection on every call via `get_user_service()`. During rapid page navigation, multiple simultaneous requests would each create new connections, potentially causing:
    - Database connection pool exhaustion
    - Race conditions
    - Slow database responses
    - Connection errors that caused `load_user` to return `None`, triggering authentication failures
  - **Fix**: 
    1. Removed the problematic `@app.before_request` handler
    2. Added in-memory caching to `load_user()` to avoid database hits on every request (5-minute TTL)
    3. Added fallback to cached user data if database query fails (prevents authentication failures due to transient DB issues)
    4. Configured Flask session settings for better persistence:
       - Set `PERMANENT_SESSION_LIFETIME` to 30 days
       - Made sessions permanent on login with `session.permanent = True`
       - Added `remember=True` and `force=True` to `login_user()` call
       - Set `session.modified = True` to ensure session is saved
       - Configured session cookie settings (HttpOnly, SameSite)
    5. Changed `session_protection` from "strong" to "basic" to prevent aggressive session invalidation during normal navigation
    6. Added `@app.before_request` handler to refresh session on each request, keeping it alive during navigation
    7. Added cache clearing on logout and login to ensure fresh user data
    6. Verified that all routes are properly protected with `@login_required` decorator
    7. Confirmed that Flask-Login User class uses properties (not methods) for `is_authenticated`, `is_active`, and `is_anonymous` (Flask-Login 0.6+ requirement)
  - **Changes Made**:
    1. Removed `@app.before_request` handler that logged authentication state
    2. Removed redundant authentication checks in route handlers
    3. Added `_user_cache` dictionary with 5-minute TTL for user data caching
    4. Updated `load_user()` to check cache first, fallback to cache on DB errors
    5. Added session configuration: `PERMANENT_SESSION_LIFETIME`, cookie settings
    6. Updated `login()` to set `session.permanent = True` and `remember=True`
    7. Updated `logout()` to clear user cache
    8. Verified all 40 routes are properly protected (only `/register` and `/login` are public)
  - **Prevention Measures**:
    1. Added this bug to the bug list with detailed explanation
    2. Documented the Flask-Login execution order: `before_request` → route decorators → route handler
    3. Established rule: Never access `current_user` in `before_request` handlers for authentication checks
    4. All authentication checks should rely on `@login_required` decorator, not manual checks in `before_request`
    5. User loading functions should use caching to avoid database hits on every request during rapid navigation
    6. Session should be configured for proper persistence with appropriate lifetime and cookie settings
  - The fix ensures that Flask-Login can properly load users from the session before any authentication checks occur, and that rapid page navigation doesn't cause database connection issues or authentication failures.

---

## Fixed Bugs

### Bug #6: Seniority Level Detection Should Prioritize Job Title Over Description

- **Date Found**: 2025-01-17
- **Date Fixed**: 2025-01-17
- **Description**: The `extract_seniority()` method was combining job title and description into a single text string and searching both simultaneously. This could lead to incorrect seniority detection when the description contained seniority indicators that conflicted with or overrode the title. For example, a "Junior Software Developer" title might be incorrectly classified as "senior" if the description mentioned "senior engineer" requirements.
- **Location**: 
  - `services/enricher/job_enricher.py` - `extract_seniority()` method (line 199-242)
- **Severity**: Medium
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: The method combined title and description into one string (`f"{job_title} {job_description}"`) and searched the combined text, which meant description matches could override title matches.
  - **Fix**: Refactored `extract_seniority()` to:
    1. First check only the job title for seniority patterns
    2. Only if no match is found in the title, then check the description
    3. Return the first match found (prioritizing title)
  - **Changes Made**:
    1. Created helper function `_check_text_for_seniority()` to check a single text string for patterns
    2. Updated logic to check title first, then description only as fallback
    3. Updated docstring to clarify the priority behavior
    4. Added test `test_extract_seniority_title_priority()` to verify title takes priority when both have seniority indicators
    5. Updated existing test `test_extract_seniority_with_description()` docstring to clarify it tests the fallback case
    6. **Pattern matching refinement**: Sorted patterns by length (longest first) within each seniority level to ensure more specific patterns (e.g., "internship") are checked before shorter ones (e.g., "intern"). This prevents potential partial matches and ensures the most specific pattern is matched first, even though word boundaries (`\b`) should prevent substring matches.
    7. Added test `test_extract_seniority_internship_vs_intern()` to verify "internship" and "intern" are both correctly matched without partial matching issues
  - The fix ensures that job titles are the primary source of truth for seniority level, with description only used as a fallback when the title doesn't contain seniority indicators. Pattern matching now prioritizes longer, more specific patterns to avoid any edge cases with partial matches.

### Bug #1: Profile Preferences Tracking Fields Not Updated by DAG

- **Date Found**: 2025-12-14
- **Date Fixed**: 2025-01-17
- **Description**: The `marts.profile_preferences` table has tracking fields (`total_run_count`, `last_run_at`, `last_run_status`, `last_run_job_count`) that are never updated when the DAG runs. The DAG reads from `profile_preferences` to get active profiles, but after processing (extraction, ranking, notifications), it does not update these tracking fields to reflect the run status and results.
- **Location**: 
  - `airflow/dags/task_functions.py` - Task functions (extract_job_postings_task, send_notifications_task)
- **Severity**: Medium
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: The DAG tasks were not updating the tracking fields after processing profiles, even though the fields existed in the schema.
  - **Fix**: Added `update_profile_tracking_fields()` helper function to `airflow/dags/task_functions.py` that updates all tracking fields. The function is called:
    1. After `extract_job_postings_task` completes successfully - updates `last_run_at`, `last_run_status` ('success'), `last_run_job_count` (number of jobs extracted), and increments `total_run_count`
    2. After `extract_job_postings_task` fails - updates all profiles with 'error' status and job_count=0
    3. After `send_notifications_task` completes - updates `last_run_at` and `last_run_status` based on notification success (without incrementing `total_run_count` again)
  - **Changes Made**:
    1. Added `update_profile_tracking_fields()` function with optional `increment_run_count` parameter
    2. Integrated tracking field updates into `extract_job_postings_task` (both success and error paths)
    3. Integrated tracking field updates into `send_notifications_task` (final status update)
  - The fix ensures that profile tracking fields are updated after each DAG run, enabling the Profile UI to display accurate run history and statistics.

### Bug #3: Missing Deduplication at Job Extractor Level for Raw Jobs

- **Date Found**: 2025-12-16
- **Date Fixed**: 2026-01-02
- **Description**: The job extraction service currently relied on downstream staging layer deduplication to handle duplicate job postings. A comment in `services/extractor/job_extractor.py` noted that "Duplicates will be handled by staging layer deduplication," but there was no deduplication at the extractor/raw layer itself. This could result in unnecessary duplicate rows being written to `raw.jsearch_job_postings`, increasing storage and processing overhead.
- **Location**: 
  - `services/extractor/job_extractor.py` - Insert logic for writing to `raw.jsearch_job_postings`
  - `services/extractor/queries.py` - Query for checking existing jobs
- **Severity**: Low
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: The extractor service was inserting all jobs from the API response without checking for existing duplicates in the raw table.
  - **Fix**: Added deduplication logic at the extractor level:
    1. Created `CHECK_EXISTING_JOBS` query in `services/extractor/queries.py` to check for existing jobs by `job_id` and `campaign_id`
    2. Updated `_write_jobs_to_db()` method in `services/extractor/job_extractor.py` to:
       - Check for existing jobs before inserting
       - Filter out duplicates from the jobs list
       - Only insert unique jobs
       - Log the number of duplicates skipped
  - **Changes Made**:
    1. Added `CHECK_EXISTING_JOBS` query to check for existing jobs in raw table
    2. Updated `_write_jobs_to_db()` to perform deduplication before bulk insert
    3. Added logging to track duplicate jobs skipped
    4. Removed comment about relying on staging layer deduplication
  - The fix ensures that only unique jobs are stored in the raw layer, reducing storage and processing overhead while maintaining data integrity.

### Bug #4: Inconsistent Field Value Casing in Database

- **Date Found**: 2025-01-17
- **Date Fixed**: 2026-01-02
- **Description**: Multiple fields in the database had inconsistent casing, leading to data quality issues and potential query/filtering problems. The staging layer extracted values directly from the API without normalization, while the enricher service normalized some fields. This created a mismatch where:
  - **Salary Period**: API returns uppercase values ("YEAR", "HOUR", "MONTH") but enricher normalizes to lowercase ("year", "hour", "month"). If enricher doesn't run or values come directly from API, they remain uppercase, creating mixed casing in the database.
  - **Employment Type**: API returns uppercase ("FULLTIME", "PARTTIME", "CONTRACTOR") which are stored as-is, but there may be inconsistencies if values come from different sources.
  - **Other fields**: Remote type and seniority level are normalized by enricher (lowercase), but if enricher doesn't run, these may be missing or inconsistent.
- **Location**: 
  - `dbt/models/staging/jsearch_job_postings.sql` - Extracts values directly without normalization
  - `services/enricher/job_enricher.py` - Normalizes salary_period to lowercase, but only if enricher runs
  - `services/ranker/job_ranker.py` - Normalizes for comparison but stored values may be inconsistent
- **Severity**: Medium
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: The staging dbt model extracted field values directly from the API without normalization, while the enricher service normalized some fields. This created inconsistent casing depending on whether the enricher ran.
  - **Fix**: Added normalization logic in the staging dbt model to ensure consistent casing regardless of whether enricher runs:
    1. Normalized `job_salary_period` to lowercase using `LOWER()` function
    2. Normalized `job_employment_type` to uppercase using `UPPER()` function
    3. Normalized `employment_types` (comma-separated string) to uppercase by splitting, uppercasing each value, and rejoining
  - **Changes Made**:
    1. Updated `dbt/models/staging/jsearch_job_postings.sql` to normalize field casing during extraction
    2. Created migration script `docker/init/12_normalize_field_casing.sql` to update existing data
    3. Migration script normalizes all affected fields: `job_salary_period`, `job_employment_type`, `employment_types`, `remote_work_type`, `seniority_level`, and `job_salary_currency`
  - The fix ensures consistent casing standards throughout the database, preventing filtering and comparison issues.

### Bug #5: Incorrect Country Code for United Kingdom

- **Date Found**: 2025-01-17
- **Date Fixed**: 2026-01-02
- **Description**: The code used "uk" as the country code for United Kingdom in several places, but JSearch API (and ISO 3166-1 alpha-2 standard) uses "gb" for United Kingdom. This mismatch could cause issues when:
  - Users enter "uk" in the profile UI, but JSearch API expects "gb"
  - Country-based currency detection fails for UK jobs
  - Location matching in the ranker doesn't work correctly for UK profiles
- **Location**: 
  - `services/enricher/job_enricher.py` - `"UK": "GBP"` in country_to_currency mapping
  - `services/ranker/job_ranker.py` - `"uk": ["united kingdom", "england", "britain"]` in country_mappings
  - `campaign_ui/templates/create_campaign.html` - Placeholder example shows "uk"
- **Severity**: Medium
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: The codebase used "uk" instead of "gb" (ISO 3166-1 alpha-2 standard) for United Kingdom, which doesn't match JSearch API expectations.
  - **Fix**: Updated all references to use "gb" consistently:
    1. Updated `country_mappings` in `services/ranker/job_ranker.py` to use "gb" instead of "uk"
    2. Updated UI placeholder in `campaign_ui/templates/create_campaign.html` to show "gb" instead of "uk"
    3. Added normalization in `campaign_ui/app.py` to convert user input "uk" to "gb" in both create and edit campaign routes
    4. Note: `services/enricher/job_enricher.py` already had "GB" as primary key with "UK" as alias (kept for backward compatibility)
  - **Changes Made**:
    1. Updated `country_mappings` in `services/ranker/job_ranker.py`
    2. Updated placeholder in `campaign_ui/templates/create_campaign.html`
    3. Added normalization logic in `campaign_ui/app.py` for both create and edit routes
    4. Created migration script `docker/init/11_fix_uk_country_code.sql` to update existing campaigns
  - The fix ensures consistent use of "gb" (ISO 3166-1 alpha-2 standard) throughout the codebase, matching JSearch API expectations while maintaining backward compatibility.

### Bug #7: "Job Not Found" Error When Clicking Jobs from Campaign Details

- **Date Found**: 2026-01-02
- **Date Fixed**: 2026-01-02
- **Description**: When viewing campaign details and clicking on a job to view its details, users encountered an error: "Job {job_id} not found." The job existed in the database (verified by running the `GET_JOBS_FOR_CAMPAIGN` query), appeared in the campaign jobs list, but when clicked, the `GET_JOB_BY_ID` query failed to retrieve it, resulting in the "Job not found" error.
- **Location**: 
  - `services/jobs/queries.py` - `GET_JOB_BY_ID` query: Used `INNER JOIN marts.job_campaigns` and filtered by `jc.user_id`
  - `services/jobs/queries.py` - `GET_JOBS_FOR_CAMPAIGN` query: Returned jobs that may not be retrievable by `GET_JOB_BY_ID`
  - `services/jobs/job_service.py` - `get_job_by_id()` method: Returned None when query found no matching job
- **Severity**: Medium
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: `GET_JOB_BY_ID` enforced `jc.user_id = %s` via an `INNER JOIN marts.job_campaigns`. When a user (possibly an admin) viewed jobs that belonged to a different user's campaign, the query filtered them out, even though the job existed and showed up in the list produced by `GET_JOBS_FOR_CAMPAIGN` (which does not join `job_campaigns`).
  - **Fix**: Changed `GET_JOB_BY_ID` query to match `GET_JOBS_FOR_CAMPAIGN` behavior:
    1. Changed `INNER JOIN marts.job_campaigns` to `LEFT JOIN marts.job_campaigns`
    2. Removed `AND jc.user_id = %s` filter from WHERE clause
    3. Updated query parameter count in `job_service.py` from 4 to 3 parameters
  - **Changes Made**:
    1. Updated `GET_JOB_BY_ID` query in `services/jobs/queries.py` to use `LEFT JOIN` instead of `INNER JOIN` and removed user_id filter
    2. Updated `get_job_by_id()` method in `services/jobs/job_service.py` to pass correct number of parameters
  - The fix ensures that jobs displayed in the campaign jobs list are retrievable when clicked, regardless of who owns the campaign. Notes and status are still filtered by the requesting user via LEFT JOINs with user_id filters.

### Bug #8: Button Animation Issue on Approve/Reject Buttons

- **Date Found**: 2026-01-10
- **Date Fixed**: 2026-01-10
- **Description**: When clicking Approve or Reject buttons on job postings, the buttons experienced animation issues similar to the "Find Jobs" button. The `common.js` auto-loading functionality was adding the `btn-loading` class to all form submit buttons, which made button text transparent (`color: transparent !important`), causing the text to disappear during form submission. Additionally, disabled buttons could still animate due to transform/transition properties.
- **Location**: 
  - `campaign_ui/templates/view_campaign.html` - Approve/Reject buttons (lines 233, 237, 320, 324)
  - `campaign_ui/static/css/components.css` - Missing `.btn-small:disabled` CSS rules
  - `campaign_ui/static/js/common.js` - Auto-loading behavior for all submit buttons
- **Severity**: Medium
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: The Approve/Reject buttons were form submit buttons without the `data-no-auto-loading` attribute, causing `common.js` to automatically apply the `btn-loading` class on form submission. This class sets `color: transparent !important`, hiding the button text. Additionally, `.btn-small` buttons didn't have the same disabled state CSS fixes as `.find-jobs-btn`, which could cause animation issues.
  - **Fix**: Applied the same solution used for the "Find Jobs" button:
    1. Added `data-no-auto-loading` attribute to all Approve/Reject buttons (both desktop table view and mobile card view)
    2. Added `data-no-auto-loading` attribute to `findJobsBtnEmpty` button for consistency
    3. Added CSS rules for `.btn-small:disabled` to prevent transforms and transitions, matching the fix for `.find-jobs-btn:disabled`
  - **Changes Made**:
    1. Updated `campaign_ui/templates/view_campaign.html` to add `data-no-auto-loading` to all Approve/Reject buttons (4 instances)
    2. Updated `campaign_ui/templates/view_campaign.html` to add `data-no-auto-loading` to `findJobsBtnEmpty` button
    3. Added `.btn-small:disabled` CSS rules in `campaign_ui/static/css/components.css` with:
       - `transform: none !important;` - Prevents any transforms or movements when disabled
       - `transition: none !important;` - Removes all transitions to prevent animation
       - `transition-property: none !important;` - Ensures no transition properties are active
  - The fix ensures that Approve/Reject buttons maintain proper text visibility and don't animate when disabled, consistent with the "Find Jobs" button behavior. This prevents future animation issues for all `.btn-small` buttons.

### Bug #10: Multi-Select Status Filter Implementation

- **Date Found**: 2026-01-11
- **Date Fixed**: 2026-01-11
- **Description**: Enhanced the campaign jobs view with a multi-select status filter to improve job management workflow. The filter allows users to select multiple job statuses simultaneously, with statuses ordered by workflow progression. Default view excludes rejected and archived jobs for cleaner initial display.
- **Location**: 
  - `campaign_ui/templates/view_campaign.html` - Multi-select dropdown and filtering logic
  - `campaign_ui/app.py` - `view_campaign` route (include_rejected parameter)
  - `campaign_ui/static/css/pages.css` and `responsive.css` - Multi-select dropdown styles
- **Severity**: Low (Enhancement)
- **Status**: Fixed
- **Resolution**:
  - **Implementation**: 
    1. Replaced single-select dropdown with multi-select checkbox dropdown
    2. Statuses ordered by workflow: waiting → approved → applied/interview/offer → rejected → archived
    3. Default selected statuses exclude rejected and archived
    4. "All Statuses" button allows unchecking all statuses (shows "Status: None")
    5. Backend updated to include rejected/archived jobs (include_rejected=True) for frontend filtering
    6. Mobile card view also supports status filtering
    7. AJAX support for status updates (no page refresh required)
  - **Changes Made**:
    1. Updated `campaign_ui/templates/view_campaign.html` with multi-select dropdown structure and JavaScript filtering logic
    2. Updated `campaign_ui/app.py` `view_campaign` route to pass `include_rejected=True` to `get_jobs_for_campaign()`
    3. Added CSS styles for multi-select dropdown components
    4. Added mobile card filtering support in JavaScript
    5. Updated filter text to show "None" when no statuses selected
  - The enhancement provides a more flexible and intuitive way to filter jobs by status, with workflow-ordered statuses and sensible defaults that exclude rejected and archived jobs by default.

### Bug #2: Ranker ON CONFLICT Fails Due to Missing Primary Key Constraint

- **Date Found**: 2025-12-14
- **Date Fixed**: 2025-12-14
- **Description**: The `rank_jobs` task fails with `psycopg2.errors.InvalidColumnReference: there is no unique or exclusion constraint matching the ON CONFLICT specification` when trying to insert/update rankings in `marts.dim_ranking`. The code uses `ON CONFLICT (jsearch_job_id, profile_id)` but the table doesn't have a unique constraint on these columns. The task completes with status SUCCESS but ranks 0 jobs, effectively failing silently.
- **Location**: 
  - `services/ranker/job_ranker.py` - Line 381-399, `_write_rankings` method
  - `dbt/models/marts/dim_ranking.sql` - Table definition with post_hook that should create the primary key
- **Severity**: High
- **Status**: Fixed
- **Resolution**: 
  - **Root Cause**: The `dim_ranking` table was supposed to be created by dbt, but dbt is not run automatically in the Docker setup. The table was either missing or existed without the primary key constraint.
  - **Fix**: Added `dim_ranking` table creation to `docker/init/02_create_tables.sql` with the primary key constraint `(jsearch_job_id, profile_id)` defined inline. This ensures the table is created during database initialization, consistent with other tables like `profile_preferences`.
  - **Changes Made**:
    1. Added `CREATE TABLE IF NOT EXISTS marts.dim_ranking` with primary key constraint to `docker/init/02_create_tables.sql`
    2. Updated GRANT permissions to include `dim_ranking` table
    3. Removed `_ensure_dim_ranking_table()` workaround method from `services/ranker/job_ranker.py`
    4. Updated dbt model comments to note that table is primarily created by init script
  - The fix ensures the table and constraint exist from database initialization, preventing the `ON CONFLICT` error. The ranker no longer needs to check/create the table at runtime.

---

## Notes

- This list should be updated as bugs are discovered during development
- Bugs should be prioritized based on severity and impact
- When fixing a bug, move it to the "Fixed Bugs" section with the resolution date

