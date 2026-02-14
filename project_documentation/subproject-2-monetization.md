# Subproject 2: Monetization (Payment System Integration)

**Objective**: Establish a framework for future revenue generation via a subscription-based model. This will be implemented in later phases, but the architecture must support it from the start.

## Detailed Tasks

### 1. Subscription Logic & Data Model
*   **Subscription Tables**:
    *   Create `marts.subscription_plans`: Store plan details (name, price, features, Stripe Price ID).
    *   Create `marts.user_subscriptions`: Track user subscription status, current period end, and Stripe Subscription ID.
*   **Feature Gating Logic**:
    *   Implement a `FeatureService` or utility to check if a user has access to a specific feature based on their current plan.
    *   Define feature flags: `max_active_campaigns`, `advanced_ranking_access`, `glassdoor_enrichment_access`, `document_storage_limit`.

### 2. Stripe Integration Research & Planning
*   **Stripe Account Setup**:
    *   Define the process for creating a Stripe account and obtaining API keys.
*   **Webhook Handling**:
    *   Design a `/api/payments/webhook` endpoint to handle Stripe events (e.g., `customer.subscription.created`, `invoice.payment_succeeded`, `customer.subscription.deleted`).
*   **Checkout Flow**:
    *   Plan the integration of Stripe Checkout for seamless payment processing.
    *   Plan for the Stripe Billing Portal to allow users to manage their own subscriptions.

### 3. Frontend Billing UI
*   **Pricing Page**:
    *   Design a `frontend/src/pages/Pricing.tsx` page comparing "Free" and "Premium" tiers.
*   **Billing Dashboard**:
    *   Add a "Billing" tab in the User Account settings.
    *   Show current plan, next billing date, and a button to "Manage Subscription" (linking to Stripe Billing Portal).
*   **Paywall Components**:
    *   Create reusable UI components (e.g., `PremiumFeatureGate`) that show a "Upgrade to Premium" CTA if the user tries to access a locked feature.

### 4. Backend Enforcement
*   **Middleware/Decorators**:
    *   Create a `@require_subscription` decorator for API endpoints that are premium-only.
    *   Implement usage limits in existing services (e.g., prevent creating more than 1 campaign if on the free tier).

### 5. Future-Proofing
*   **Trial Periods**:
    *   Plan for implementing a 7-day or 14-day free trial for the Premium tier.
*   **Promotional Codes**:
    *   Ensure the system can handle Stripe coupons and promotion codes.
