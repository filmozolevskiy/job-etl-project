# DAG Trigger Logic - Edge Cases Analysis

## Current Implementation Review

### Backend (`campaign_ui/app.py`)

**Edge Cases Covered:**
1. ✅ Campaign not found
2. ✅ Permission check (user ownership/admin)
3. ✅ Force start admin-only validation
4. ✅ Concurrent DAG check (409 Conflict)
5. ✅ Airflow client not configured
6. ✅ Exception handling with proper error responses

**Potential Gaps:**
1. ⚠️ **Race condition**: Small window between status check and trigger
2. ⚠️ **Airflow API exceptions**: Handled but could be more specific
3. ⚠️ **Missing dag_run_id**: If Airflow returns success but no dag_run_id
4. ⚠️ **Invalid campaign_id type**: What if campaign_id is not an integer?
5. ⚠️ **Airflow timeout**: 30-second timeout might be too long for user experience
6. ⚠️ **Airflow API unavailable after check**: Check happens, then API becomes unavailable

### Frontend (`campaign_ui/static/js/campaignDetails.js`)

**Edge Cases Covered:**
1. ✅ Button disabled check
2. ✅ Cooldown check
3. ✅ Force start bypass
4. ✅ 409 Conflict handling
5. ✅ Error handling with button reset
6. ✅ Polling error handling (MAX_POLLING_ERRORS)
7. ✅ localStorage persistence

**Potential Gaps:**
1. ⚠️ **Network failure during trigger**: isDagRunning set but request fails
2. ⚠️ **Missing dag_run_id in response**: Frontend handles null, but polling might fail
3. ⚠️ **Multiple tabs**: localStorage conflicts possible
4. ⚠️ **Browser navigation**: State lost if user navigates away
5. ⚠️ **Tab close during trigger**: State not persisted
6. ⚠️ **Response parsing failure**: What if response is not valid JSON?
7. ⚠️ **Polling with null dag_run_id**: Is this safe?

### AirflowClient (`services/airflow_client/airflow_client.py`)

**Edge Cases Covered:**
1. ✅ 401 Unauthorized
2. ✅ 403 Forbidden
3. ✅ 404 Not Found
4. ✅ Timeout (30 seconds)
5. ✅ Connection errors
6. ✅ Generic RequestException

**Potential Gaps:**
1. ⚠️ **Partial response**: What if response is incomplete?
2. ⚠️ **Invalid JSON response**: What if Airflow returns invalid JSON?
3. ⚠️ **Rate limiting**: What if Airflow rate limits requests?

## Missing Edge Cases to Address

### Critical
1. **Race condition in concurrent trigger check**: Need database-level locking or atomic check
2. **Network failure after isDagRunning=true**: Need timeout/retry mechanism
3. **Missing dag_run_id**: Need fallback polling strategy
4. **Invalid campaign_id**: Need type validation

### Important
5. **Multiple tabs**: Need to sync state across tabs (BroadcastChannel API)
6. **Browser navigation**: Need to persist state in sessionStorage
7. **Tab close**: Need beforeunload handler to clean up
8. **Response parsing failure**: Need better error handling

### Nice to Have
9. **Airflow rate limiting**: Need exponential backoff
10. **Partial response**: Need validation of response structure


