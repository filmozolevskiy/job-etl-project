import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import type { StagingSlot } from '../types';

export const StagingDashboard: React.FC = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [isCheckingAll, setIsCheckingAll] = useState(false);

  const { data: slots, isLoading, error } = useQuery<StagingSlot[]>({
    queryKey: ['staging-slots'],
    queryFn: async () => {
      const response = await apiClient.getStagingSlots();
      return response as StagingSlot[];
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  const checkHealthMutation = useMutation({
    mutationFn: (slotId: number) => apiClient.checkStagingSlotHealth(slotId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staging-slots'] });
    },
  });

  const checkAllHealthMutation = useMutation({
    mutationFn: () => apiClient.checkAllStagingSlotsHealth(),
    onMutate: () => setIsCheckingAll(true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staging-slots'] });
      setIsCheckingAll(false);
    },
    onError: () => setIsCheckingAll(false),
  });

  const releaseSlotMutation = useMutation({
    mutationFn: (slotId: number) => apiClient.releaseStagingSlot(slotId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staging-slots'] });
    },
  });

  if (user?.role !== 'admin') {
    return (
      <div className="error-container">
        <h1>Access Denied</h1>
        <p>You do not have permission to view this page.</p>
      </div>
    );
  }

  if (isLoading) return <div className="loading">Loading staging slots...</div>;
  if (error) return <div className="error">Error loading staging slots: {(error as Error).message}</div>;

  const getHealthBadgeClass = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy': return 'badge-success';
      case 'degraded': return 'badge-warning';
      case 'down': return 'badge-danger';
      default: return 'badge-secondary';
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status.toLowerCase()) {
      case 'available': return 'badge-success';
      case 'in use': return 'badge-info';
      case 'reserved': return 'badge-warning';
      default: return 'badge-secondary';
    }
  };

  /** Staging links use subdomains so each row opens the correct slot (e.g. https://staging-2.justapply.net). */
  const STAGING_BASE_HOST = 'justapply.net';

  const getSlotCampaignUrl = (slotId: number) =>
    `https://staging-${slotId}.${STAGING_BASE_HOST}`;
  const getSlotAirflowUrl = (slotId: number) =>
    `https://staging-${slotId}.${STAGING_BASE_HOST}/airflow/`;

  return (
    <div className="staging-dashboard">
      <div className="page-header">
        <div>
          <h1>Staging Management</h1>
          <p>Monitor and manage staging environment slots</p>
        </div>
        <div className="header-actions">
          <button 
            className="btn btn-secondary" 
            onClick={() => checkAllHealthMutation.mutate()}
            disabled={isCheckingAll}
          >
            <i className={`fas fa-sync-alt ${isCheckingAll ? 'fa-spin' : ''}`}></i>
            {isCheckingAll ? ' Checking All...' : ' Refresh All Health'}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="table-responsive">
          <table className="table">
            <thead>
              <tr>
                <th>Slot</th>
                <th>Status</th>
                <th>Health</th>
                <th>Owner / Branch</th>
                <th>Issue</th>
                <th>Deployed At</th>
                <th>Links</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {slots?.map((slot) => (
                <tr key={slot.slot_id}>
                  <td>
                    <strong>{slot.slot_name}</strong>
                  </td>
                  <td>
                    <span className={`badge ${getStatusBadgeClass(slot.status)}`}>
                      {slot.status}
                    </span>
                  </td>
                  <td>
                    <div className="health-info">
                      <span className={`badge ${getHealthBadgeClass(slot.health_status)}`}>
                        {slot.health_status}
                      </span>
                      {slot.last_health_check_at && (
                        <small className="d-block text-muted" style={{ fontSize: '0.7rem' }}>
                          {new Date(slot.last_health_check_at).toLocaleTimeString()}
                        </small>
                      )}
                    </div>
                  </td>
                  <td>
                    {slot.status === 'In Use' ? (
                      <div>
                        <div className="owner-name">{slot.owner || 'Unknown'}</div>
                        <div className="branch-name text-muted" style={{ fontSize: '0.8rem' }}>
                          <i className="fas fa-code-branch mr-1"></i>
                          {slot.branch || 'N/A'}
                        </div>
                      </div>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td>
                    {slot.issue_id ? (
                      <a 
                        href={`https://linear.app/job-search-assistant/issue/${slot.issue_id}`} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="issue-link"
                      >
                        {slot.issue_id}
                      </a>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td>
                    {slot.deployed_at ? (
                      <div className="deploy-time">
                        {new Date(slot.deployed_at).toLocaleDateString()}<br />
                        <small className="text-muted">{new Date(slot.deployed_at).toLocaleTimeString()}</small>
                      </div>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td>
                    <div className="slot-links">
                      <a href={getSlotCampaignUrl(slot.slot_id)} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline-primary mr-1" title={`Campaign UI (${slot.slot_name})`}>
                        <i className="fas fa-desktop"></i>
                      </a>
                      <a href={getSlotAirflowUrl(slot.slot_id)} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline-info mr-1" title={`Airflow (${slot.slot_name})`}>
                        <i className="fas fa-wind"></i>
                      </a>
                    </div>
                  </td>
                  <td>
                    <div className="btn-group">
                      <button 
                        className="btn btn-sm btn-outline-secondary" 
                        onClick={() => checkHealthMutation.mutate(slot.slot_id)}
                        disabled={checkHealthMutation.isPending && checkHealthMutation.variables === slot.slot_id}
                        title="Check Health"
                      >
                        <i className={`fas fa-heartbeat ${checkHealthMutation.isPending && checkHealthMutation.variables === slot.slot_id ? 'fa-spin' : ''}`}></i>
                      </button>
                      {slot.status === 'In Use' && (
                        <button 
                          className="btn btn-sm btn-outline-danger" 
                          onClick={() => {
                            if (window.confirm(`Are you sure you want to release ${slot.slot_name}?`)) {
                              releaseSlotMutation.mutate(slot.slot_id);
                            }
                          }}
                          title="Release Slot"
                        >
                          <i className="fas fa-sign-out-alt"></i>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4">
        <h3>Staging Slot Rules</h3>
        <div className="card p-3">
          <ul className="mb-0">
            <li><strong>One slot per task:</strong> Each Linear issue gets exactly one staging slot.</li>
            <li><strong>Release after merge:</strong> Slots should be released after the PR is merged to main.</li>
            <li><strong>Health Checks:</strong> Use the heartbeat icon to manually trigger a health check for a specific slot.</li>
            <li><strong>Auto-Update:</strong> Deployment scripts automatically update slot information when a new branch is deployed.</li>
          </ul>
        </div>
      </div>
    </div>
  );
};
