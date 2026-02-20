/**
 * Shared helpers for job publisher display and filtering.
 * Normalizes empty/null publisher to "Unknown"; keys are lowercase for case-insensitive filter.
 */

export type PublisherOption = { key: string; display: string };

/**
 * Returns the canonical publisher key for a job (for filter/sort).
 * Empty or null publisher becomes "unknown".
 */
export function getPublisherKey(job: { job_publisher?: string | null }): string {
  const raw = (job.job_publisher as string | undefined) ?? '';
  const trimmed = (typeof raw === 'string' ? raw : '').trim();
  return trimmed ? trimmed.toLowerCase() : 'unknown';
}

/**
 * Returns the display label for a job's publisher (empty -> "Unknown").
 */
export function getPublisherDisplay(job: { job_publisher?: string | null }): string {
  const raw = (job.job_publisher as string | undefined) ?? '';
  const trimmed = (typeof raw === 'string' ? raw : '').trim();
  return trimmed || 'Unknown';
}

/**
 * Returns distinct publishers from a list of jobs, sorted by display name.
 * Empty publisher is shown as "Unknown".
 */
export function getDistinctPublishers(
  jobs: Array<{ job_publisher?: string | null }>
): PublisherOption[] {
  const seen = new Set<string>();
  const result: PublisherOption[] = [];
  for (const job of jobs) {
    const key = getPublisherKey(job);
    if (!seen.has(key)) {
      seen.add(key);
      result.push({ key, display: getPublisherDisplay(job) });
    }
  }
  result.sort((a, b) => a.display.localeCompare(b.display));
  return result;
}
