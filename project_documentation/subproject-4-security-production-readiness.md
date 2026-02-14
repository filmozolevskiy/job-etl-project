# Subproject 4: Security & Production Readiness (DigitalOcean)

**Objective**: Ensure the platform is secure, scalable, and reliable for a commercial audience, optimized for hosting on DigitalOcean.

## Detailed Tasks

### 1. Authentication & Authorization Hardening
*   **Token Management**:
    *   Implement **Refresh Tokens** stored in secure, `HttpOnly`, `SameSite=Strict` cookies.
    *   Shorten **Access Token** (JWT) lifespan to 15 minutes.
    *   Implement token revocation (blacklist) for logout and security breaches.
*   **Password Policy**:
    *   Enforce strong password requirements (length, complexity).
    *   Implement account lockout after multiple failed login attempts.

### 2. API Security & Rate Limiting
*   **Rate Limiting**:
    *   Implement global rate limiting (e.g., using Flask-Limiter with Redis).
    *   Apply stricter limits on sensitive endpoints: `/api/auth/login`, `/api/auth/register`, `/api/auth/claim-account`.
*   **Input Validation**:
    *   Ensure 100% coverage of input validation using `marshmallow` or `pydantic`.
    *   Sanitize all user-generated content to prevent XSS.

### 3. DigitalOcean Infrastructure Optimization
*   **Deployment Strategy**:
    *   Evaluate **DigitalOcean App Platform** for simplified horizontal scaling and automated SSL.
    *   Alternatively, optimize **Droplet** configuration with a managed Load Balancer.
*   **Database Management**:
    *   Ensure **Managed MongoDB/PostgreSQL** is used for automated backups and point-in-time recovery.
    *   Configure VPC peering between app services and the database.
*   **Static Assets**:
    *   Use **DigitalOcean Spaces** (S3-compatible) for user document storage (resumes/cover letters) with CDN enabled.

### 4. Observability & Error Tracking
*   **Error Tracking**:
    *   Integrate **Sentry** for both Backend (Flask) and Frontend (React).
    *   Set up alerting for 5xx errors and critical pipeline failures.
*   **Logging**:
    *   Implement structured JSON logging for easier parsing in production.
    *   Ensure no PII (Personally Identifiable Information) is included in logs.
*   **Analytics**:
    *   Integrate **PostHog** for privacy-focused user behavior tracking and feature flags.

### 5. Compliance & Disaster Recovery
*   **Privacy Policy & TOS**:
    *   Draft and host a basic Privacy Policy and Terms of Service.
    *   Implement a cookie consent banner.
*   **Backup & Recovery**:
    *   Test database restoration from backups.
    *   Document a "Disaster Recovery" runbook for the engineering team.
*   **Security Headers**:
    *   Configure `Content-Security-Policy`, `X-Frame-Options`, and `Strict-Transport-Security` headers.
