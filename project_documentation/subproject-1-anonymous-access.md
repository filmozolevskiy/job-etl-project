9*# Subproject 1: Anonymous Access & Conversion

**Objective**: Allow users to experience the full value of the platform immediately without friction, converting them to registered users only after they see the value.

## Detailed Tasks

### 1. Data Model Refactoring
*   **Nullable User Associations**:
    *   Modify `marts.job_campaigns` table: Change `user_id` to be nullable.
    *   Modify `marts.job_applications` table: Change `user_id` to be nullable.
    *   Modify `marts.user_documents` table: Change `user_id` to be nullable.
*   **Guest Tracking**:
    *   Add `guest_session_id` (UUID) to `marts.job_campaigns`, `marts.job_applications`, and `marts.user_documents`.
    *   Create an index on `guest_session_id` for fast lookups of anonymous data.

### 2. Backend API Updates
*   **Session Management**:
    *   Implement middleware to detect or generate a `guest_session_id` for unauthenticated requests.
    *   Update `CampaignService` to query by `user_id` OR `guest_session_id`.
    *   Update `JobService` to handle status updates (e.g., "Applied", "Rejected") for anonymous sessions.
*   **Conversion Endpoint**:
    *   Create a new API endpoint `/api/auth/claim-account` that:
        1. Takes a `guest_session_id` and a new user's credentials.
        2. Creates a new user in `marts.users`.
        3. Updates all records in `marts.job_campaigns`, `marts.job_applications`, and `marts.user_documents` where `guest_session_id` matches, setting the new `user_id` and clearing the `guest_session_id`.

### 3. Frontend Implementation
*   **Anonymous State Handling**:
    *   Modify `AuthContext` to support a `guestId` state, persisted in `localStorage`.
    *   Update `apiClient` to include the `X-Guest-Session-ID` header if the user is not authenticated.
*   **UI/UX for Guests**:
    *   Remove `ProtectedRoute` from `/dashboard`, `/campaigns`, and `/jobs`.
    *   Add a "Save Your Progress" banner or modal that appears after the user creates their first campaign or updates a job status.
    *   Implement the "Claim Account" form/flow that triggers the backend conversion.
*   **Navigation Logic**:
    *   Ensure the Sidebar and Header show "Login/Register" for guests and "Profile/Logout" for authenticated users.

### 4. Cleanup & Maintenance
*   **Guest Data Retention Policy**:
    *   Define a policy for how long anonymous data is kept (e.g., 30 days).
    *   Create an Airflow task or script to purge expired guest data to keep the database clean.
