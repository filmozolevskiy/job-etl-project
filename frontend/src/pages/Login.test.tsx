import { Routes, Route } from 'react-router-dom';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { Login } from './Login';
import { renderWithProviders } from '../test/testUtils';

const apiClientMock = vi.hoisted(() => ({
  login: vi.fn(),
}));

vi.mock('../services/api', () => ({
  apiClient: apiClientMock,
  setAccessToken: vi.fn(),
}));

describe('Login page', () => {
  beforeEach(() => {
    apiClientMock.login.mockReset();
    localStorage.clear();
  });

  it('submits credentials and navigates to dashboard', async () => {
    apiClientMock.login.mockResolvedValue({
      access_token: 'token-123',
      user: { user_id: 1, username: 'demo', email: 'demo@example.com', role: 'user' },
    });

    renderWithProviders(
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<div>Dashboard Page</div>} />
      </Routes>,
      { route: '/login' }
    );

    fireEvent.change(screen.getByLabelText(/username or email/i), { target: { value: 'demo' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'secret' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('Dashboard Page')).toBeInTheDocument();
    await waitFor(() => {
      expect(localStorage.getItem('access_token')).toBe('token-123');
    });
  });

  it('shows error on failed login', async () => {
    apiClientMock.login.mockRejectedValue(new Error('Invalid credentials'));

    renderWithProviders(
      <Routes>
        <Route path="/login" element={<Login />} />
      </Routes>,
      { route: '/login' }
    );

    fireEvent.change(screen.getByLabelText(/username or email/i), { target: { value: 'demo' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('Invalid credentials')).toBeInTheDocument();
  });
});
