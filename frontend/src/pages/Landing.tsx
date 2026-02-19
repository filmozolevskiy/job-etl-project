import { Link } from 'react-router-dom';
import { useEffect } from 'react';
import './Landing.css';

const LANDING_TITLE = 'Job Search Manager | AI-Ranked Jobs & Cover Letters';

export function Landing() {
  useEffect(() => {
    document.title = LANDING_TITLE;
    return () => {
      document.title = 'Job Search Manager';
    };
  }, []);

  return (
    <div className="landing" role="main">
      <header className="landing-header">
        <div className="landing-container">
          <Link to="/" className="landing-logo" aria-label="JustApply home">
            JustApply
          </Link>
          <nav className="landing-nav" aria-label="Main navigation">
            <Link to="/login" className="landing-nav-link">
              Log in
            </Link>
            <Link to="/register" className="landing-nav-cta">
              Get started
            </Link>
          </nav>
        </div>
      </header>

      <section className="landing-hero" aria-labelledby="hero-heading">
        <div className="landing-container">
          <h1 id="hero-heading" className="landing-hero-title">
            Find, rank, and apply to jobs with AI
          </h1>
          <p className="landing-hero-sub">
            We score jobs to your profile, draft tailored cover letters, and help you track every application—so you spend less time searching and more time landing offers.
          </p>
          <Link to="/register" className="landing-btn landing-btn-primary">
            Start Searching Now
          </Link>
        </div>
      </section>

      <section className="landing-features" aria-labelledby="features-heading">
        <div className="landing-container">
          <h2 id="features-heading" className="landing-section-title">
            Built for your job hunt
          </h2>
          <div className="landing-features-grid">
            <article className="landing-feature" aria-labelledby="feature-ai-ranking">
              <div className="landing-feature-icon" aria-hidden="true">
                <span className="landing-feature-icon-emoji">📊</span>
              </div>
              <h3 id="feature-ai-ranking" className="landing-feature-title">
                AI Ranking
              </h3>
              <p className="landing-feature-desc">
                Jobs are scored against your profile so you see the best matches first—no more sifting through irrelevant postings.
              </p>
            </article>
            <article className="landing-feature" aria-labelledby="feature-cover-letters">
              <div className="landing-feature-icon" aria-hidden="true">
                <span className="landing-feature-icon-emoji">✉️</span>
              </div>
              <h3 id="feature-cover-letters" className="landing-feature-title">
                AI Cover Letters
              </h3>
              <p className="landing-feature-desc">
                Get tailored cover letters for every job. Our AI drafts unique, role-specific letters so you can apply faster and stand out.
              </p>
            </article>
            <article className="landing-feature" aria-labelledby="feature-crm">
              <div className="landing-feature-icon" aria-hidden="true">
                <span className="landing-feature-icon-emoji">📋</span>
              </div>
              <h3 id="feature-crm" className="landing-feature-title">
                Application CRM
              </h3>
              <p className="landing-feature-desc">
                Track status, CV and cover letter used, and contacts in one place. Never lose a lead or forget a follow-up again.
              </p>
            </article>
            <article className="landing-feature" aria-labelledby="feature-alerts">
              <div className="landing-feature-icon" aria-hidden="true">
                <span className="landing-feature-icon-emoji">🔔</span>
              </div>
              <h3 id="feature-alerts" className="landing-feature-title">
                Automated Daily Alerts
              </h3>
              <p className="landing-feature-desc">
                Get notified about high-match opportunities so you can apply while the posting is fresh—without checking job boards every day.
              </p>
            </article>
          </div>
        </div>
      </section>

      <section className="landing-how" aria-labelledby="how-heading">
        <div className="landing-container">
          <h2 id="how-heading" className="landing-section-title">
            How it works
          </h2>
          <ol className="landing-steps">
            <li className="landing-step">
              <span className="landing-step-num" aria-hidden="true">1</span>
              <h3 className="landing-step-title">Create Campaign</h3>
              <p className="landing-step-desc">Define your search criteria: role, location, and preferences.</p>
            </li>
            <li className="landing-step">
              <span className="landing-step-num" aria-hidden="true">2</span>
              <h3 className="landing-step-title">AI Ranks & Drafts</h3>
              <p className="landing-step-desc">Our engine finds matches and drafts tailored cover letters for you.</p>
            </li>
            <li className="landing-step">
              <span className="landing-step-num" aria-hidden="true">3</span>
              <h3 className="landing-step-title">Track & Apply</h3>
              <p className="landing-step-desc">Use the CRM to manage applications and contacts in one place.</p>
            </li>
          </ol>
        </div>
      </section>

      <section className="landing-cta" aria-labelledby="cta-heading">
        <div className="landing-container">
          <h2 id="cta-heading" className="landing-cta-title">
            Free for everyone
          </h2>
          <p className="landing-cta-sub">
            The service is currently <strong>100% free</strong> for all users. No pricing tiers, no payment plans—just better job search.
          </p>
          <Link to="/register" className="landing-btn landing-btn-primary landing-btn-large">
            Get Started for Free
          </Link>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="landing-container">
          <p className="landing-footer-text">
            © {new Date().getFullYear()} JustApply. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
