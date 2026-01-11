# Integration Tests for Ranking Modal

## Overview

These integration tests verify the ranking modal functionality in a real browser environment.

## Test Setup

1. Start the application: `docker-compose up`
2. Navigate to a campaign page with jobs that have ranking explanations
3. Use browser automation (Selenium, Playwright, or similar) to test interactions

## Test Cases

### TC-1: Modal Opens on Icon Click

**Steps:**
1. Navigate to campaign page (e.g., `/campaign/1`)
2. Find a job row with a ranking info icon (`.fit-info-icon`)
3. Click the icon

**Expected:**
- Modal appears (`#rankingModal` has class `active`)
- Modal displays company name and job title
- Modal displays overall score
- Modal displays ranking breakdown with progress bars

**Assertions:**
- `document.getElementById('rankingModal').classList.contains('active')` === true
- `document.getElementById('modalCompanyName').textContent` !== ''
- `document.getElementById('modalJobPosition').textContent` !== ''
- `document.getElementById('rankingDetails').children.length` > 0

---

### TC-2: Modal Displays Ranking Breakdown Correctly

**Steps:**
1. Open modal (see TC-1)
2. Inspect ranking breakdown content

**Expected:**
- Each ranking factor displayed with label and score/max format
- Factors sorted by contribution (highest first)
- Progress bars displayed with correct colors (green/yellow/gray)
- `total_score` excluded from breakdown
- All factors have human-readable labels

**Assertions:**
- No factor named 'total_score' in breakdown
- First factor has highest score
- Progress bars have class `ranking-progress-fill` with color class (`high`, `medium`, or `low`)
- All labels are human-readable (not snake_case)

---

### TC-3: Modal Closes on Overlay Click

**Steps:**
1. Open modal (see TC-1)
2. Click on modal overlay (outside modal content)

**Expected:**
- Modal closes (`#rankingModal` does not have class `active`)

**Assertions:**
- `document.getElementById('rankingModal').classList.contains('active')` === false

---

### TC-4: Modal Closes on Close Button Click

**Steps:**
1. Open modal (see TC-1)
2. Click close button (`.modal-close`)

**Expected:**
- Modal closes

**Assertions:**
- `document.getElementById('rankingModal').classList.contains('active')` === false

---

### TC-5: Modal Closes on Escape Key

**Steps:**
1. Open modal (see TC-1)
2. Press Escape key

**Expected:**
- Modal closes

**Assertions:**
- `document.getElementById('rankingModal').classList.contains('active')` === false

---

### TC-6: Modal Handles Empty Breakdown

**Steps:**
1. Navigate to campaign page
2. Find a job without ranking explanation (no `rank_explain` data)
3. Click ranking info icon (if icon exists)

**Expected:**
- Modal opens
- Displays "Ranking explanation not available" message
- No progress bars displayed

**Assertions:**
- `document.querySelector('.ranking-empty-state')` !== null
- `document.querySelector('.ranking-empty-state').textContent` includes 'not available'

---

### TC-7: Modal Handles Custom Campaign Weights

**Steps:**
1. Create campaign with custom ranking weights (e.g., location_match: 20.0 instead of default 15.0)
2. Run job extraction/ranking
3. Open modal for a job with score that exceeds default max

**Expected:**
- Modal displays score/max format correctly (e.g., "20.0 / 20.0" not "20.0 / 15.0")
- Progress bar shows correct percentage (100% not 133%)

**Assertions:**
- Score values don't exceed max values
- Progress bar percentage <= 100%

---

### TC-8: Modal on Job Details Page

**Steps:**
1. Navigate to job details page (e.g., `/job/<job_id>`)
2. Find ranking info icon next to rank score
3. Click icon

**Expected:**
- Modal opens with same behavior as campaign page
- All functionality works identically

**Assertions:**
- Same as TC-1 through TC-7

---

### TC-9: Accessibility - Screen Reader Support

**Steps:**
1. Open modal (see TC-1)
2. Use screen reader (NVDA, JAWS, or VoiceOver)
3. Navigate through modal content

**Expected:**
- Progress bars announce values correctly
- Modal is properly labeled
- Close button is accessible
- Keyboard navigation works

**Assertions:**
- All progress bars have `role="progressbar"`
- Progress bars have `aria-valuenow`, `aria-valuemin`, `aria-valuemax`
- Progress bars have `aria-label` with descriptive text
- Close button has `aria-label="Close"`

---

### TC-10: Error Handling - Missing DOM Elements

**Steps:**
1. Manually remove modal HTML from page (via browser console)
2. Attempt to open modal

**Expected:**
- Error logged to console (not thrown)
- No JavaScript errors that break page
- Page remains functional

**Assertions:**
- No uncaught exceptions
- Console contains warning/error message
- Page functionality unaffected

---

## Automated Test Implementation

For automated testing, use a browser automation framework:

### Example (Playwright)

```javascript
test('Modal opens on icon click', async ({ page }) => {
    await page.goto('/campaign/1');
    
    const icon = page.locator('.fit-info-icon').first();
    await icon.click();
    
    const modal = page.locator('#rankingModal');
    await expect(modal).toHaveClass(/active/);
    
    const companyName = await page.locator('#modalCompanyName').textContent();
    expect(companyName).toBeTruthy();
    
    const details = page.locator('#rankingDetails');
    const items = await details.locator('.ranking-progress-item').count();
    expect(items).toBeGreaterThan(0);
});

test('Modal closes on Escape key', async ({ page }) => {
    await page.goto('/campaign/1');
    
    const icon = page.locator('.fit-info-icon').first();
    await icon.click();
    
    await page.keyboard.press('Escape');
    
    const modal = page.locator('#rankingModal');
    await expect(modal).not.toHaveClass(/active/);
});
```

---

## Manual Test Checklist

- [ ] Modal opens on icon click (campaign page)
- [ ] Modal opens on icon click (job details page)
- [ ] Ranking breakdown displays correctly
- [ ] Factors sorted by contribution (highest first)
- [ ] Progress bars show correct colors
- [ ] Score/max format displays correctly
- [ ] Modal closes on overlay click
- [ ] Modal closes on close button click
- [ ] Modal closes on Escape key
- [ ] Empty breakdown handled gracefully
- [ ] Custom weights handled correctly
- [ ] Screen reader navigation works
- [ ] Keyboard navigation works
- [ ] No JavaScript errors in console
