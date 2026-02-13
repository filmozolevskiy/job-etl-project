import React, { useState, useRef, useEffect } from 'react';

/** Apply option from API: array of { apply_link?: string } or similar */
type ApplyOption = { apply_link?: string; link?: string; [key: string]: unknown };

type JobPostingLinksProps = {
  jobApplyLink?: string | null;
  jobGoogleLink?: string | null;
  applyOptions?: ApplyOption[] | null;
  /** Compact: single primary link + dropdown. Inline: list/dropdown for detail page */
  variant?: 'compact' | 'inline';
  className?: string;
};

/** Collect unique posting URLs from job fields (primary, Google, apply_options). */
function collectPostingLinks(
  jobApplyLink?: string | null,
  jobGoogleLink?: string | null,
  applyOptions?: ApplyOption[] | null
): { primary: string | null; others: { url: string; label: string }[] } {
  const seen = new Set<string>();
  let primary: string | null = null;

  if (jobApplyLink && jobApplyLink.trim()) {
    primary = jobApplyLink.trim();
    seen.add(primary);
  }

  const others: { url: string; label: string }[] = [];

  if (jobGoogleLink && jobGoogleLink.trim() && !seen.has(jobGoogleLink.trim())) {
    seen.add(jobGoogleLink.trim());
    others.push({ url: jobGoogleLink.trim(), label: 'Google Jobs' });
  }

  if (Array.isArray(applyOptions)) {
    applyOptions.forEach((opt, i) => {
      const url = (opt?.apply_link ?? opt?.link ?? '').trim();
      if (url && !seen.has(url)) {
        seen.add(url);
        others.push({ url, label: `Apply option ${i + 1}` });
      }
    });
  }

  return { primary, others };
}

export const JobPostingLinks: React.FC<JobPostingLinksProps> = ({
  jobApplyLink,
  jobGoogleLink,
  applyOptions,
  variant = 'compact',
  className = '',
}) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const { primary: rawPrimary, others } = collectPostingLinks(jobApplyLink, jobGoogleLink, applyOptions);
  const primary = rawPrimary ?? (others.length > 0 ? others[0].url : null);
  const othersAfterPrimary = rawPrimary ? others : others.slice(1);
  const hasMultiple = primary && othersAfterPrimary.length > 0;
  const hasAny = primary || others.length > 0;

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!hasAny) {
    return <span className={className} style={{ opacity: 0.6 }}>Not available</span>;
  }

  if (variant === 'inline') {
    return (
      <div className={`job-posting-links-inline ${className}`}>
        {primary && (
          <a href={primary} target="_blank" rel="noreferrer" className="posting-link primary">
            View primary posting
          </a>
        )}
        {othersAfterPrimary.length > 0 && (
          <div className="posting-links-dropdown-wrapper" ref={dropdownRef}>
            <button
              type="button"
              className="posting-links-dropdown-trigger"
              onClick={() => setDropdownOpen((o) => !o)}
              aria-expanded={dropdownOpen}
              aria-haspopup="true"
            >
              More links ({othersAfterPrimary.length})
            </button>
            {dropdownOpen && (
              <ul className="posting-links-dropdown-menu" role="menu">
                {othersAfterPrimary.map(({ url, label }) => (
                  <li key={url} role="none">
                    <a href={url} target="_blank" rel="noreferrer" role="menuitem">
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    );
  }

  // compact: primary link + optional "More" dropdown
  return (
    <div className={`job-posting-links-compact ${className}`} ref={dropdownRef}>
      {primary && (
        <a href={primary} target="_blank" rel="noreferrer" className="posting-link-primary">
          Apply
        </a>
      )}
      {hasMultiple && (
        <>
          <button
            type="button"
            className="posting-links-more-btn"
            onClick={() => setDropdownOpen((o) => !o)}
            aria-expanded={dropdownOpen}
            aria-haspopup="true"
            title="More posting links"
          >
            More
          </button>
          {dropdownOpen && (
            <ul className="posting-links-dropdown-menu" role="menu">
              {othersAfterPrimary.map(({ url, label }) => (
                <li key={url} role="none">
                  <a href={url} target="_blank" rel="noreferrer" role="menuitem">
                    {label}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
};
