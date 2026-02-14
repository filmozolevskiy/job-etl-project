# Subproject 3: Professional UI/UX & Landing Page

**Objective**: Create a high-converting, trustworthy, and modern user experience following "Modern Minimalist" design principles.

## Detailed Tasks

### 1. Landing Page Development
*   **Hero Section**:
    *   Craft a compelling headline and subheadline focused on the "AI-Ranked" value proposition.
    *   Implement a primary CTA for "Start Searching Now" (leading to the anonymous search flow).
*   **Feature Highlights**:
    *   Visual sections for: AI Ranking, Application Tracking, and Automated Daily Alerts.
*   **"How it Works"**:
    *   A simple 3-step guide: 1. Create Campaign, 2. AI Ranks Jobs, 3. Apply Smarter.
*   **Social Proof/Trust**:
    *   Add placeholders for testimonials or "As seen on" logos.
*   **Pricing Section**:
    *   A clear comparison table for Free vs. Premium tiers.

### 2. Dashboard & App UI Overhaul
*   **Minimalist Design System**:
    *   Adopt a clean color palette (mostly whites, grays, and a single accent color).
    *   Use high-quality typography (e.g., Inter or Geist).
    *   Implement consistent spacing and border-radius (e.g., `rounded-lg`).
*   **Navigation Redesign**:
    *   Streamline the Sidebar for better focus.
    *   Implement a "Command Palette" (Cmd+K) for fast navigation (future enhancement).
*   **Job Card/Table Polishing**:
    *   Improve the visual hierarchy of job listings.
    *   Add subtle animations for status updates and transitions.

### 3. Mobile-First Responsiveness
*   **Responsive Breakpoints**:
    *   Audit all pages at 320px, 768px, and 1024px widths.
    *   Ensure the Sidebar converts to a bottom-nav or hamburger menu on mobile.
*   **Touch Optimization**:
    *   Ensure all buttons and interactive elements have a minimum 44x44px touch target.

### 4. SEO Optimization
*   **Dynamic Meta Tags**:
    *   Integrate `react-helmet-async`.
    *   Set unique `title` and `description` tags for each job details page and campaign page.
*   **Technical SEO**:
    *   Implement a `sitemap.xml` generation script.
    *   Ensure all images have `alt` tags.
    *   Optimize page load speed (Core Web Vitals).
*   **Open Graph / Twitter Cards**:
    *   Add meta tags for social sharing (preview images, titles).

### 5. Accessibility (a11y)
*   **Compliance**:
    *   Aim for WCAG 2.1 Level AA compliance.
    *   Ensure proper color contrast and keyboard navigability.
    *   Add ARIA labels where necessary.
