import type { FC } from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { useAuth } from './AuthContext';
import { renderWithProviders } from '../test/testUtils';

const apiClientMock = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
}));

vi.mock('../services/api', () => ({
  apiClient: apiClientMock,
  setAccessToken: vi.fn(),
}));

const TestConsumer: FC = () => {
  const { user, login, register, logout, isAuthenticated } = useAuth();
  return (
    <div>
      <div data-testid="auth-status">{isAuthenticated ? 'authed' : 'guest'}</div>
      <div data-testid="username">{user?.username || ''}</div>
      <button type="button" onClick={() => login({ username: 'demo', password: 'secret' })}>
        Login
      </button>
      <button
        type="button"
        onClick={() =>
          register({
            username: 'newuser',
            email: 'newuser@example.com',
            password: 'secret',
            password_confirm: 'secret',
          })
        }
      >
        Register
      </button>
      <button type="button" onClick={logout}>
        Logout
      </button>
    </div>
  );
};

describe('AuthContext', () => {
  beforeEach(() => {
    apiClientMock.login.mockReset();
    apiClientMock.register.mockReset();
    localStorage.clear();
  });

  it('stores user on login', async () => {
    apiClientMock.login.mockResolvedValue({
      access_token: 'token-123',
      user: { user_id: 1, username: 'demo', email: 'demo@example.com', role: 'user' },
    });

    renderWithProviders(<TestConsumer />);

    fireEvent.click(screen.getByRole('button', { name: 'Login' }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('authed');
      expect(screen.getByTestId('username')).toHaveTextContent('demo');
    });

    expect(localStorage.getItem('access_token')).toBe('token-123');
  });

  it('stores user on register', async () => {
    apiClientMock.register.mockResolvedValue({
      access_token: 'token-abc',
      user: { user_id: 2, username: 'newuser', email: 'newuser@example.com', role: 'user' },
    });

    renderWithProviders(<TestConsumer />);

    fireEvent.click(screen.getByRole('button', { name: 'Register' }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('authed');
      expect(screen.getByTestId('username')).toHaveTextContent('newuser');
    });

    expect(localStorage.getItem('access_token')).toBe('token-abc');
  });

  it('clears state on logout', async () => {
    localStorage.setItem('access_token', 'token-existing');
    localStorage.setItem(
      'user',
      JSON.stringify({ user_id: 9, username: 'existing', email: 'existing@example.com', role: 'user' })
    );

    renderWithProviders(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('authed');
    });

    fireEvent.click(screen.getByRole('button', { name: 'Logout' }));

    expect(screen.getByTestId('auth-status')).toHaveTextContent('guest');
    expect(localStorage.getItem('access_token')).toBeNull();
  });
});
