# Commercial Roadmap: Job Search Platform Pivot

This document outlines the strategic roadmap for transitioning the Job Search Project from a "pet project" into a commercial SaaS platform. The goal is to maximize user conversion, implement a sustainable monetization model, and ensure production-grade security and user experience.

## Vision
To provide the most frictionless and intelligent job search experience for professionals, leveraging AI-driven ranking and seamless application tracking.

## Core Pillars (Subprojects)

### 1. Architectural Shift: Anonymous Access & Conversion
**Objective**: Remove all barriers to entry by allowing users to experience the full value of the platform immediately.

*   **Session-Based Campaign Management**:
    *   Implement a system to track "guest" campaigns using session IDs or local storage.
    *   Allow full access to search, filtering, and ranking for anonymous users.
*   **Conversion Funnel ("Claim Account")**:
    *   Design a seamless transition for guest users to register and "claim" their temporary campaigns and data.
    *   Implement data migration logic to link session-based data to a new user account.
*   **Data Model Updates**:
    *   Update `marts.job_campaigns` and `marts.job_applications` to allow nullable `user_id`.
    *   Add `session_id` or `guest_id` columns to track anonymous data.
*   **Persistence Strategy**:
    *   Evaluate and implement a hybrid approach: Local storage for immediate UI responsiveness and server-side session tracking for data consistency.

### 2. Monetization: Payment System Integration
**Objective**: Establish a framework for future revenue generation via a subscription-based model. (Implementation scheduled for later phases).

*   **Stripe Integration**:
    *   Research and plan for Stripe Checkout and Billing Portal integration.
    *   Define product SKUs and pricing tiers in Stripe.
*   **Feature Tiering**:
    *   Define "Free" vs "Premium" capabilities:
        *   Free: Limited active campaigns, basic search.
        *   Premium: Unlimited campaigns, advanced AI ranking, Glassdoor enrichment, document storage (resumes/cover letters).
*   **Subscription Management**:
    *   Design UI for plan selection, billing history, and payment method management.
*   **Paywall Framework**:
    *   Implement a flexible "feature flag" system to toggle paywalls on/off as the business model evolves.

### 3. Professional UI/UX & Landing Page
**Objective**: Create a trustworthy, high-converting, and modern "Modern Minimalist" user experience.

*   **High-Converting Landing Page**:
    *   Develop `frontend/src/pages/Landing.tsx` with clear value propositions, "How it works" section, and pricing.
*   **Dashboard Overhaul**:
    *   Redesign the main dashboard for clarity and focus, following minimalist design principles (e.g., Linear, Vercel).
*   **Mobile-First Responsiveness**:
    *   Ensure 100% functionality and visual polish on mobile devices.
*   **SEO Strategy**:
    *   Implement dynamic meta tags using `react-helmet-async`.
    *   Generate automated `sitemap.xml` and `robots.txt`.
    *   Optimize semantic HTML for better search engine indexing.

### 4. Security & Production Readiness (DigitalOcean)
**Objective**: Ensure the platform is secure, scalable, and reliable for a commercial audience.

*   **Authentication Hardening**:
    *   Move from simple JWT to a robust Refresh Token + Access Token flow.
    *   Implement secure, HTTP-only cookies for token storage.
*   **API Protection**:
    *   Implement rate limiting on all public and private API endpoints.
    *   Configure DigitalOcean's built-in DDoS protection and firewall rules.
*   **Infrastructure Optimization**:
    *   Evaluate migration from Docker Compose to DigitalOcean App Platform or Managed Kubernetes (DOKS) for better scaling.
*   **Observability & Monitoring**:
    *   Integrate **Sentry** for real-time error tracking.
    *   Integrate **PostHog** or Google Analytics for user behavior analysis.
*   **Disaster Recovery**:
    *   Automate PostgreSQL backups on DigitalOcean.
    *   Document recovery procedures and establish uptime SLAs.
