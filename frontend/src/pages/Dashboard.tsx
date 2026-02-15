import React, { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import Chart from 'chart.js/auto';
import { apiClient } from '../services/api';
import type { DashboardStats } from '../types';

export const Dashboard: React.FC = () => {
  const { data, isLoading, error } = useQuery<DashboardStats>({
    queryKey: ['dashboard'],
    queryFn: async () => {
      const response = await apiClient.getDashboard();
      return response as DashboardStats;
    },
  });

  const stats = data || {
    active_campaigns_count: 0,
    total_campaigns_count: 0,
    jobs_processed_count: 0,
    success_rate: 0,
    recent_jobs: [],
    activity_data: [],
  };

  const chartRef = useRef<HTMLCanvasElement | null>(null);
  const chartInstanceRef = useRef<Chart | null>(null);

  useEffect(() => {
    if (!chartRef.current || !stats.activity_data || stats.activity_data.length === 0) {
      return;
    }

    const labels = stats.activity_data.map((item) => {
      const date = new Date(item.date);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });
    const foundData = stats.activity_data.map((item) => item.found || 0);
    const appliedData = stats.activity_data.map((item) => item.applied || 0);

    if (chartInstanceRef.current) {
      chartInstanceRef.current.destroy();
    }

    chartInstanceRef.current = new Chart(chartRef.current, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Jobs Found',
            data: foundData,
            borderColor: 'rgb(124, 58, 237)',
            backgroundColor: 'rgba(124, 58, 237, 0.1)',
            tension: 0.4,
            fill: true,
          },
          {
            label: 'Jobs Applied',
            data: appliedData,
            borderColor: 'rgb(40, 167, 69)',
            backgroundColor: 'rgba(40, 167, 69, 0.1)',
            tension: 0.4,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
          },
          tooltip: {
            mode: 'index',
            intersect: false,
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              stepSize: 1,
            },
          },
        },
        interaction: {
          mode: 'nearest',
          axis: 'x',
          intersect: false,
        },
      },
    });

    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
      }
    };
  }, [stats.activity_data]);

  if (isLoading) return <div>Loading...</div>;
  if (error) {
    console.error('Dashboard error:', error);
    // If it's a 422 error, it's likely an old token - suggest re-login
    const isTokenError = (error as { response?: { status?: number } })?.response?.status === 422;
    return (
      <div>
        <div className="error-message" style={{ padding: '1rem', background: '#fee2e2', color: '#991b1b', borderRadius: '8px', marginBottom: '1rem' }}>
          <strong>Error loading dashboard</strong>
          {isTokenError && (
            <div style={{ marginTop: '0.5rem' }}>
              <p>Your session token is invalid. Please <a href="/login" style={{ color: '#991b1b', textDecoration: 'underline' }}>log out and log back in</a> to refresh your token.</p>
            </div>
          )}
          {!isTokenError && (
            <p style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
              {(error as Error)?.message || 'An unexpected error occurred'}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Overview of your job search activity</p>
      </div>

      <div className="stats-grid dashboard-stats-grid">
        <div className="stat-card">
          <div className="stat-icon-circle stat-icon-blue">
            <i className="fas fa-clipboard-list"></i>
          </div>
          <div className="stat-card-content">
            <div className="stat-value-large">
              {stats.active_campaigns_count}/{stats.total_campaigns_count}
            </div>
            <div className="stat-label">Active Campaigns</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-circle stat-icon-purple">
            <i className="fas fa-briefcase"></i>
          </div>
          <div className="stat-card-content">
            <div className="stat-value-large">{stats.jobs_processed_count}</div>
            <div className="stat-label">Jobs Processed</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-circle stat-icon-orange">
            <i className="fas fa-percentage"></i>
          </div>
          <div className="stat-card-content">
            <div className="stat-value-large">{stats.success_rate}%</div>
            <div className="stat-label">Success Rate</div>
          </div>
        </div>
      </div>

      <div className="chart-card">
        <div className="chart-header">
          <h2>Activity Per Day</h2>
        </div>
        {stats.activity_data && stats.activity_data.length > 0 ? (
          <div className="chart-container">
            <canvas id="activityChart" ref={chartRef}></canvas>
          </div>
        ) : (
          <div className="chart-empty-state">
            <i
              className="fas fa-chart-line"
              style={{ fontSize: '3rem', color: 'var(--color-text-muted)', marginBottom: 'var(--spacing-md)' }}
            ></i>
            <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-base)' }}>
              No activity data yet. Start searching for jobs to see your progress.
            </p>
          </div>
        )}
      </div>

      <div className="recent-jobs">
        <div className="section-header">
          <h2>Last Jobs Applied</h2>
          <a href="/jobs" className="btn btn-primary">
            <i className="fas fa-eye"></i> View All
          </a>
        </div>
        {stats.recent_jobs && stats.recent_jobs.length > 0 ? (
          <ul className="job-list">
            {stats.recent_jobs.slice(0, 4).map((job: unknown) => {
              const j = job as {
                job_title?: string;
                company_name?: string;
                location?: string;
                ranked_at?: string;
                jsearch_job_id?: string;
              };
              return (
                <li key={j.jsearch_job_id} className="job-item">
                  <div className="job-info">
                    <h3>{j.job_title || 'Unknown Title'}</h3>
                    <p>
                      {j.company_name || 'Unknown Company'} • {j.location || 'Location not specified'}
                    </p>
                  </div>
                  <div className="job-date">{j.ranked_at || 'Unknown'}</div>
                </li>
              );
            })}
          </ul>
        ) : (
          <ul className="job-list">
            <li className="job-item">
              <div className="job-info">
                <h3>No jobs applied yet</h3>
                <p>Start searching for jobs to see activity here.</p>
              </div>
              <div className="job-date">—</div>
            </li>
          </ul>
        )}
      </div>
    </div>
  );
};
