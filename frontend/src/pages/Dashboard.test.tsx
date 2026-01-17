import { screen } from '@testing-library/react';
import { vi } from 'vitest';
import { Dashboard } from './Dashboard';
import { renderWithProviders } from '../test/testUtils';

const apiClientMock = vi.hoisted(() => ({
  getDashboard: vi.fn(),
}));

vi.mock('../services/api', () => ({
  apiClient: apiClientMock,
}));

vi.mock('chart.js/auto', () => ({
  default: class ChartMock {
    destroy() {}
  },
}));

describe('Dashboard page', () => {
  beforeEach(() => {
    apiClientMock.getDashboard.mockReset();
  });

  it('renders dashboard stats and recent jobs', async () => {
    apiClientMock.getDashboard.mockResolvedValue({
      active_campaigns_count: 2,
      total_campaigns_count: 4,
      jobs_processed_count: 12,
      success_rate: 50,
      recent_jobs: [
        {
          job_title: 'Data Analyst',
          company_name: 'Acme',
          location: 'Remote',
          ranked_at: '2026-01-10',
          jsearch_job_id: 'job-1',
        },
      ],
      activity_data: [],
    });

    renderWithProviders(<Dashboard />);

    expect(await screen.findByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('2/4')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('50%')).toBeInTheDocument();
    expect(screen.getByText('Data Analyst')).toBeInTheDocument();
  });
});
