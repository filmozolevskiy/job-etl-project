import { useState, useMemo, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import type { Campaign } from '../types';

export const CampaignsList = () => {
  const { user } = useAuth();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [locationFilter, setLocationFilter] = useState('all');

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target.closest('.action-dropdown-wrapper')) {
        document.querySelectorAll('.action-dropdown-menu').forEach((menu) => {
          (menu as HTMLElement).style.display = 'none';
        });
      }
    };

    document.addEventListener('click', handleClickOutside);
    return () => {
      document.removeEventListener('click', handleClickOutside);
    };
  }, []);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['campaigns'],
    queryFn: async () => {
      const result = await apiClient.getCampaigns();
      return { campaigns: result.campaigns as Campaign[] };
    },
  });

  const campaigns = (data?.campaigns || []) as Campaign[];

  // Extract unique locations from campaigns
  const locations = useMemo(() => {
    const locs = new Set<string>();
    campaigns.forEach((campaign) => {
      const location = (campaign as { location?: string }).location;
      if (location) locs.add(location);
    });
    return Array.from(locs).sort();
  }, [campaigns]);

  // Filter campaigns
  const filteredCampaigns = useMemo(() => {
    return campaigns.filter((campaign) => {
      // Search filter
      if (searchTerm) {
        const name = campaign.campaign_name.toLowerCase();
        if (!name.includes(searchTerm.toLowerCase())) {
          return false;
        }
      }

      // Status filter
      if (statusFilter === 'active' && !campaign.is_active) {
        return false;
      }
      if (statusFilter === 'inactive' && campaign.is_active) {
        return false;
      }

      // Location filter
      if (locationFilter !== 'all') {
        const location = (campaign as { location?: string }).location || '';
        if (location !== locationFilter) {
          return false;
        }
      }

      return true;
    });
  }, [campaigns, searchTerm, statusFilter, locationFilter]);

  const handleDelete = async (campaignId: number, campaignName: string) => {
    if (!window.confirm(`Are you sure you want to delete "${campaignName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await apiClient.deleteCampaign(campaignId);
      refetch();
    } catch (error) {
      console.error('Error deleting campaign:', error);
      alert('Failed to delete campaign. Please try again.');
    }
  };

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading campaigns</div>;

  const isAdmin = user?.role === 'admin';

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Campaigns</h1>
        <Link to="/campaigns/new" className="btn btn-primary">
          <i className="fas fa-plus"></i> New Campaign
        </Link>
      </div>

      {/* Filter Bar */}
      <div className="table-header-bar" style={{ marginBottom: 'var(--spacing-lg)' }}>
        <input
          type="text"
          className="search-input"
          placeholder="Search campaigns..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <div className="header-controls">
          <select
            id="statusFilter"
            className="status-dropdown"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          <select
            id="locationFilter"
            className="status-dropdown"
            value={locationFilter}
            onChange={(e) => setLocationFilter(e.target.value)}
          >
            <option value="all">All Locations</option>
            {locations.map((loc) => (
              <option key={loc} value={loc}>
                {loc}
              </option>
            ))}
          </select>
          <button
            className="refresh-btn btn btn-secondary"
            onClick={() => refetch()}
            aria-label="Refresh"
            style={{ minWidth: 'auto', padding: '0.75rem 1rem' }}
          >
            <i className="fas fa-sync-alt"></i> Refresh
          </button>
        </div>
      </div>

      {/* Results Count */}
      <div
        id="campaignResultsCount"
        style={{
          marginBottom: 'var(--spacing-md)',
          color: 'var(--color-text-muted)',
          fontSize: 'var(--font-size-sm)',
        }}
      >
        {filteredCampaigns.length === campaigns.length
          ? `Showing all ${campaigns.length} campaign${campaigns.length !== 1 ? 's' : ''}`
          : `Showing ${filteredCampaigns.length} of ${campaigns.length} campaign${campaigns.length !== 1 ? 's' : ''}`}
      </div>

      {filteredCampaigns.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <i className="fas fa-folder-open"></i>
          </div>
          <h2 className="empty-state-title">No Campaigns Yet</h2>
          <p className="empty-state-message">
            Get started by creating your first job search campaign. Campaigns help you track and manage your job search
            across different roles and locations.
          </p>
          <Link to="/campaigns/new" className="btn btn-primary">
            <i className="fas fa-plus"></i> Create Your First Campaign
          </Link>
        </div>
      ) : (
        <div className="card">
          {/* Desktop Table View */}
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th className="sortable" data-sort="name">
                    Name
                  </th>
                  {isAdmin && (
                    <th className="sortable" data-sort="owner">
                      Owner
                    </th>
                  )}
                  <th className="sortable" data-sort="location">
                    Location
                  </th>
                  <th className="sortable" data-sort="status">
                    Status
                  </th>
                  <th className="sortable" data-sort="jobs">
                    Jobs Found
                  </th>
                  <th className="sortable" data-sort="date">
                    Last Search
                  </th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredCampaigns.map((campaign: Campaign) => {
                  const campaignData = campaign as Campaign & {
                    location?: string;
                    last_run_at?: string;
                    username?: string;
                  };
                  return (
                    <tr key={campaign.campaign_id}>
                      <td>
                        <Link to={`/campaigns/${campaign.campaign_id}`}>
                          <strong>{campaign.campaign_name}</strong>
                        </Link>
                      </td>
                      {isAdmin && <td>{campaignData.username || '-'}</td>}
                      <td>{campaignData.location || '-'}</td>
                      <td>
                        {campaign.is_active ? (
                          <span className="badge badge-success">
                            <i className="fas fa-check-circle"></i> Active
                          </span>
                        ) : (
                          <span className="badge badge-secondary">
                            <i className="fas fa-pause-circle"></i> Inactive
                          </span>
                        )}
                      </td>
                      <td>
                        <strong>{campaign.total_jobs || 0}</strong>
                      </td>
                      <td>
                        {campaignData.last_run_at
                          ? new Date(campaignData.last_run_at).toLocaleString('en-US', {
                              year: 'numeric',
                              month: '2-digit',
                              day: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : 'Never'}
                      </td>
                      <td>
                        <div className="action-dropdown-wrapper">
                          <button
                            className="action-dropdown-toggle"
                            aria-label={`Actions for ${campaign.campaign_name}`}
                            aria-expanded="false"
                            aria-haspopup="true"
                            title="Actions"
                            onClick={(e) => {
                              e.stopPropagation();
                              const menu = (e.currentTarget.nextElementSibling as HTMLElement) || null;
                              const allMenus = document.querySelectorAll('.action-dropdown-menu');
                              allMenus.forEach((m) => {
                                if (m !== menu) (m as HTMLElement).style.display = 'none';
                              });
                              if (menu) {
                                menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
                              }
                            }}
                          >
                            <i className="fas fa-ellipsis-v" aria-hidden="true"></i>
                          </button>
                          <div className="action-dropdown-menu">
                            <Link
                              to={`/campaigns/${campaign.campaign_id}`}
                              className="action-dropdown-item primary"
                            >
                              <i className="fas fa-eye"></i> View
                            </Link>
                            <Link
                              to={`/campaigns/${campaign.campaign_id}/edit`}
                              className="action-dropdown-item"
                            >
                              <i className="fas fa-edit"></i> Edit
                            </Link>
                            <div className="action-dropdown-divider"></div>
                            <button
                              type="button"
                              className="action-dropdown-item danger"
                              onClick={() => handleDelete(campaign.campaign_id, campaign.campaign_name)}
                            >
                              <i className="fas fa-trash"></i> Delete
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile Card View */}
          <div className="cards-container">
            {filteredCampaigns.map((campaign: Campaign) => {
              const campaignData = campaign as Campaign & {
                location?: string;
                last_run_at?: string;
                username?: string;
              };
              return (
                <div key={campaign.campaign_id} className="campaign-card">
                  <div className="campaign-card-header">
                    <h3 className="campaign-card-title">
                      <Link to={`/campaigns/${campaign.campaign_id}`}>{campaign.campaign_name}</Link>
                    </h3>
                    <div>
                      {campaign.is_active ? (
                        <span className="badge badge-success">
                          <i className="fas fa-check-circle"></i> Active
                        </span>
                      ) : (
                        <span className="badge badge-secondary">
                          <i className="fas fa-pause-circle"></i> Inactive
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="campaign-card-meta">
                    {isAdmin && (
                      <div className="campaign-card-meta-item">
                        <span className="campaign-card-meta-label">Owner:</span>
                        <span>{campaignData.username || '-'}</span>
                      </div>
                    )}
                    <div className="campaign-card-meta-item">
                      <span className="campaign-card-meta-label">Location:</span>
                      <span>{campaignData.location || '-'}</span>
                    </div>
                    <div className="campaign-card-meta-item">
                      <span className="campaign-card-meta-label">Jobs Found:</span>
                      <span>
                        <strong>{campaign.total_jobs || 0}</strong>
                      </span>
                    </div>
                    <div className="campaign-card-meta-item">
                      <span className="campaign-card-meta-label">Last Search:</span>
                      <span>
                        {campaignData.last_run_at
                          ? new Date(campaignData.last_run_at).toLocaleString('en-US', {
                              year: 'numeric',
                              month: '2-digit',
                              day: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : 'Never'}
                      </span>
                    </div>
                  </div>
                  <div className="campaign-card-actions">
                    <Link
                      to={`/campaigns/${campaign.campaign_id}`}
                      className="btn btn-primary btn-small"
                    >
                      <i className="fas fa-eye"></i> View
                    </Link>
                    <div className="action-dropdown-wrapper">
                      <button
                        className="action-dropdown-toggle"
                        aria-label={`More actions for ${campaign.campaign_name}`}
                        aria-expanded="false"
                        aria-haspopup="true"
                        title="More actions"
                        onClick={(e) => {
                          const menu = (e.currentTarget.nextElementSibling as HTMLElement) || null;
                          const allMenus = document.querySelectorAll('.action-dropdown-menu');
                          allMenus.forEach((m) => {
                            if (m !== menu) (m as HTMLElement).style.display = 'none';
                          });
                          if (menu) {
                            menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
                          }
                        }}
                      >
                        <i className="fas fa-ellipsis-v" aria-hidden="true"></i>
                      </button>
                      <div className="action-dropdown-menu">
                        <Link
                          to={`/campaigns/${campaign.campaign_id}/edit`}
                          className="action-dropdown-item"
                        >
                          <i className="fas fa-edit"></i> Edit
                        </Link>
                        <div className="action-dropdown-divider"></div>
                        <button
                          type="button"
                          className="action-dropdown-item danger"
                          onClick={() => handleDelete(campaign.campaign_id, campaign.campaign_name)}
                        >
                          <i className="fas fa-trash"></i> Delete
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
