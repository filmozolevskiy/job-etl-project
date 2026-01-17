import { screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { CampaignsList } from './CampaignsList';
import { renderWithProviders } from '../test/testUtils';

const apiClientMock = vi.hoisted(() => ({
  getCampaigns: vi.fn(),
  deleteCampaign: vi.fn(),
}));

vi.mock('../services/api', () => ({
  apiClient: apiClientMock,
}));

const campaigns = [
  {
    campaign_id: 1,
    campaign_name: 'Alpha Campaign',
    is_active: true,
    total_jobs: 5,
    location: 'Remote',
    last_run_at: null,
  },
  {
    campaign_id: 2,
    campaign_name: 'Beta Campaign',
    is_active: false,
    total_jobs: 3,
    location: 'Toronto',
    last_run_at: null,
  },
];

describe('CampaignsList page', () => {
  beforeEach(() => {
    apiClientMock.getCampaigns.mockReset();
    apiClientMock.deleteCampaign.mockReset();
    localStorage.setItem(
      'user',
      JSON.stringify({ user_id: 1, username: 'admin', email: 'admin@example.com', role: 'admin' })
    );
    localStorage.setItem('access_token', 'token-123');
    apiClientMock.getCampaigns.mockResolvedValue({ campaigns });
  });

  it('filters campaigns by search term', async () => {
    renderWithProviders(<CampaignsList />);

    expect((await screen.findAllByText('Alpha Campaign')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Beta Campaign').length).toBeGreaterThan(0);

    fireEvent.change(screen.getByPlaceholderText('Search campaigns...'), {
      target: { value: 'Alpha' },
    });

    expect(screen.getAllByText('Alpha Campaign').length).toBeGreaterThan(0);
    expect(screen.queryAllByText('Beta Campaign').length).toBe(0);
    expect(screen.getByText('Showing 1 of 2 campaigns')).toBeInTheDocument();
  });

  it('deletes campaign when confirmed', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    apiClientMock.deleteCampaign.mockResolvedValue(undefined);

    renderWithProviders(<CampaignsList />);

    expect((await screen.findAllByText('Alpha Campaign')).length).toBeGreaterThan(0);
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(apiClientMock.deleteCampaign).toHaveBeenCalledWith(1);
    });

    vi.restoreAllMocks();
  });
});
