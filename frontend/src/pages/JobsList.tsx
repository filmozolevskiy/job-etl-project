import React, { useState, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import type { Job } from '../types';

export const JobsList: React.FC = () => {
  const [searchParams] = useSearchParams();
  const campaignId = searchParams.get('campaign_id');
  const [statusFilter, setStatusFilter] = useState('');
  const [publisherFilter, setPublisherFilter] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['jobs', campaignId || null],
    queryFn: async () => {
      const result = await apiClient.getJobs(campaignId ? parseInt(campaignId, 10) : undefined);
      return { jobs: result.jobs as Job[] };
    },
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading jobs</div>;

  const jobs = (data?.jobs || []) as Job[];
  const distinctPublishers = useMemo(() => {
    const seen = new Set<string>();
    const result: Array<{ key: string; display: string }> = [];
    for (const job of jobs) {
      const raw = (job.job_publisher as string | undefined) ?? '';
      const trimmed = (typeof raw === 'string' ? raw : '').trim();
      const display = trimmed || 'Unknown';
      const key = trimmed ? trimmed.toLowerCase() : 'unknown';
      if (!seen.has(key)) {
        seen.add(key);
        result.push({ key, display });
      }
    }
    result.sort((a, b) => a.display.localeCompare(b.display));
    return result;
  }, [jobs]);

  const filteredJobs = jobs.filter((job: Job) => {
    if (statusFilter && job.job_status !== statusFilter) return false;
    if (publisherFilter) {
      const raw = (job.job_publisher as string | undefined) ?? '';
      const trimmed = (typeof raw === 'string' ? raw : '').trim();
      const key = trimmed ? trimmed.toLowerCase() : 'unknown';
      if (key !== publisherFilter) return false;
    }
    return true;
  });

  return (
    <div>
      <div className="page-header">
        <h1>Jobs</h1>
        <div className="header-controls">
          <select
            className="status-dropdown"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="found">Found</option>
            <option value="applied">Applied</option>
            <option value="rejected">Rejected</option>
            <option value="interview">Interview</option>
            <option value="offer">Offer</option>
          </select>
          {distinctPublishers.length > 0 && (
            <select
              className="status-dropdown"
              value={publisherFilter}
              onChange={(e) => setPublisherFilter(e.target.value)}
            >
              <option value="">All publishers</option>
              {distinctPublishers.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.display}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Job Title</th>
              <th>Company</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredJobs.length === 0 ? (
              <tr>
                <td colSpan={4}>No jobs found</td>
              </tr>
            ) : (
              filteredJobs.map((job: Job) => (
                <tr key={job.jsearch_job_id}>
                  <td>{job.job_title || 'N/A'}</td>
                  <td>{job.company_name || 'N/A'}</td>
                  <td>
                    <span className={`badge badge-${job.job_status || 'secondary'}`}>
                      {job.job_status || 'N/A'}
                    </span>
                  </td>
                  <td>
                    <Link
                      to={`/jobs/${job.jsearch_job_id}`}
                      className="btn btn-sm btn-secondary"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
