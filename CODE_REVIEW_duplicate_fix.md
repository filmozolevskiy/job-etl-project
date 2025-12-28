# Code Review: Duplicate Jobs Fix and Related Changes

## Date: 2025-12-27
## Reviewer: AI Assistant
## Files Reviewed:
- `services/jobs/queries.py`
- `services/jobs/job_service.py`
- `services/jobs/job_status_service.py`
- `profile_ui/app.py` (trigger_profile_dag route)

---

## 🔴 Critical Issues

### 1. SQL Injection Risk in LIMIT/OFFSET (Medium Severity)
**File:** `services/jobs/job_service.py` (lines 42, 67)

**Issue:** LIMIT and OFFSET values are concatenated directly into SQL strings using f-strings.

```python
query += f" LIMIT {limit} OFFSET {offset}"
```

**Risk:** While `limit` and `offset` are typed as `int`, there's no explicit validation. If these values come from user input indirectly, this could be exploited.

**Recommendation:**
- Validate that `limit` and `offset` are positive integers
- Consider using a safer pattern (though PostgreSQL doesn't support parameterized LIMIT/OFFSET directly)
- Add validation: `if limit and limit < 0: raise ValueError("Limit must be non-negative")`

**Note:** This pattern exists elsewhere in the codebase (checked - no similar issues found), but it's worth addressing.

---

## ⚠️ Potential Issues

### 2. GET_JOBS_FOR_USER Missing DISTINCT ON
**File:** `services/jobs/queries.py` (line 64-101)

**Issue:** `GET_JOBS_FOR_USER` query does not have `DISTINCT ON` like `GET_JOBS_FOR_PROFILE` does, which could potentially cause duplicates when viewing all jobs for a user.

**Current code:**
```sql
GET_JOBS_FOR_USER = """
    SELECT
        dr.jsearch_job_id,
        dr.profile_id,
        ...
```

**Recommendation:** Consider adding `DISTINCT ON (dr.jsearch_job_id, dr.profile_id)` to ensure no duplicates when a job appears in multiple profiles for the same user. However, this might be intentional if you want to show the same job multiple times (once per profile).

**Decision needed:** Is it intended behavior to show duplicate jobs if they appear in multiple profiles?

---

### 3. Subquery Complexity in GET_JOBS_FOR_PROFILE
**File:** `services/jobs/queries.py` (lines 4-61)

**Issue:** The query uses a subquery wrapper to handle DISTINCT ON and ordering. This is more complex than other queries in the codebase.

**Observation:** The pattern is:
1. Inner query with `DISTINCT ON (dr.jsearch_job_id)` ordered by `dr.jsearch_job_id, dr.rank_score DESC`
2. Outer query ordered by `rank_score DESC`

**Assessment:** This is technically correct and handles the requirement, but it's different from other queries. Since `dim_ranking` has a primary key on `(jsearch_job_id, profile_id)`, duplicates shouldn't occur naturally. The DISTINCT ON might be unnecessary defensive programming.

**Recommendation:** Verify if duplicates actually occur without DISTINCT ON. If the primary key constraint is working correctly, the subquery complexity may be unnecessary.

---

## ✅ Good Practices Observed

### 4. Consistent Query Structure
- Queries follow the established pattern in `services/*/queries.py`
- Uses parameterized queries (%s placeholders)
- Proper use of LEFT JOINs for optional data
- Consistent naming conventions (GET_*, INSERT_*, UPDATE_*, UPSERT_*)

### 5. Proper Error Handling
- `JobStatusService.upsert_status()` validates status values
- Proper exception handling and logging
- Type hints are used consistently

### 6. Security
- All user inputs are parameterized in SQL queries
- Profile ownership checks in `trigger_profile_dag`
- User authentication and authorization checks

---

## 🔍 Code Quality Observations

### 7. Documentation
**Status:** Good
- Docstrings are present and descriptive
- Type hints are used
- Function parameters are documented

### 8. Consistency with Codebase
- Service classes follow the same pattern as `ProfileService`
- Database connection handling is consistent
- Logging patterns match existing code

### 9. SQL Query Formatting
**Status:** Consistent
- Multi-line queries are properly formatted
- JOIN conditions are clear
- Column lists are organized

---

## 📋 Recommendations Summary

### High Priority
1. ✅ **Add validation for LIMIT/OFFSET** in `job_service.py` to ensure they're non-negative integers

### Medium Priority
2. ⚠️ **Clarify duplicate handling intent** for `GET_JOBS_FOR_USER` - should it have DISTINCT ON?
3. ⚠️ **Consider simplifying** `GET_JOBS_FOR_PROFILE` if DISTINCT ON is not actually needed (verify duplicates exist without it)

### Low Priority
4. Consider adding unit tests for edge cases (empty results, large limits, etc.)

---

## ✅ Approved Patterns

1. Use of `DISTINCT ON` is appropriate for PostgreSQL
2. Subquery wrapper pattern is correct for ordering after DISTINCT ON
3. Service layer separation is clean
4. Route handlers properly check permissions
5. Consistent use of `COALESCE` for default values

---

## Testing Recommendations

1. **Test for duplicates:**
   - Create a test profile with jobs
   - Verify no duplicates appear in job listing
   - Test with jobs that have notes and status

2. **Test edge cases:**
   - Empty job lists
   - Jobs without company information
   - Jobs without notes/status
   - Large LIMIT values

3. **Test security:**
   - Verify users can only see their own jobs
   - Verify admins can see all jobs
   - Test profile ownership checks

---

## Overall Assessment

**Status:** ✅ **APPROVED with minor recommendations**

The code follows good practices and is consistent with the codebase. The main concerns are:
1. LIMIT/OFFSET validation (low risk, but good practice)
2. Clarifying the intent for GET_JOBS_FOR_USER duplicates (design decision)
3. Potential simplification of GET_JOBS_FOR_PROFILE if DISTINCT ON proves unnecessary

The duplicate fix is implemented correctly and should resolve the reported issue.

