import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

export const Account: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [passwordError, setPasswordError] = useState('');

  const { data: accountData } = useQuery({
    queryKey: ['account'],
    queryFn: () => apiClient.getAccount(),
  });

  const accountUser = accountData
    ? ((accountData as { user: unknown }).user as Record<string, unknown>)
    : user;

  const changePasswordMutation = useMutation({
    mutationFn: (data: {
      current_password: string;
      new_password: string;
      confirm_password: string;
    }) => apiClient.changePassword(data),
    onSuccess: () => {
      setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
      setPasswordError('');
      alert('Password updated successfully');
    },
    onError: (error: unknown) => {
      setPasswordError(error instanceof Error ? error.message : 'Failed to update password');
    },
  });

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError('');

    if (passwordData.new_password !== passwordData.confirm_password) {
      setPasswordError('Passwords do not match');
      return;
    }

    if (passwordData.new_password.length < 8) {
      setPasswordError('Password must be at least 8 characters');
      return;
    }

    changePasswordMutation.mutate(passwordData);
  };

  return (
    <div>
      <div className="page-header">
        <h1>Account Settings</h1>
      </div>

      <div className="section-card">
        <h2>Profile Information</h2>
        <div className="info-grid">
          <div>
            <strong>Username:</strong> {accountUser?.username as string || user?.username}
          </div>
          <div>
            <strong>Email:</strong> {accountUser?.email as string || user?.email}
          </div>
          <div>
            <strong>Role:</strong> {accountUser?.role as string || user?.role}
          </div>
        </div>
      </div>

      <div className="section-card">
        <h2>Change Password</h2>
        {passwordError && (
          <div className="notification notification-error">
            <span>{passwordError}</span>
          </div>
        )}
        <form onSubmit={handlePasswordSubmit}>
          <div className="form-group">
            <label htmlFor="current_password">Current Password</label>
            <input
              type="password"
              id="current_password"
              value={passwordData.current_password}
              onChange={(e) =>
                setPasswordData({ ...passwordData, current_password: e.target.value })
              }
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="new_password">New Password</label>
            <input
              type="password"
              id="new_password"
              value={passwordData.new_password}
              onChange={(e) =>
                setPasswordData({ ...passwordData, new_password: e.target.value })
              }
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="confirm_password">Confirm New Password</label>
            <input
              type="password"
              id="confirm_password"
              value={passwordData.confirm_password}
              onChange={(e) =>
                setPasswordData({ ...passwordData, confirm_password: e.target.value })
              }
              required
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={changePasswordMutation.isPending}
          >
            Update Password
          </button>
        </form>
      </div>

      <div className="section-card">
        <h2>Session Management</h2>
        <div style={{ marginTop: '1rem' }}>
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => {
              logout();
              navigate('/login');
            }}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <i className="fas fa-sign-out-alt"></i>
            <span>Log Out</span>
          </button>
          <p style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
            Log out of your account. You will need to log in again to access your data.
          </p>
        </div>
      </div>
    </div>
  );
};
