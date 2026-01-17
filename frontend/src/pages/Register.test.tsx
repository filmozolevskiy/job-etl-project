import { Routes, Route } from 'react-router-dom';
import { screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import { Register } from './Register';
import { renderWithProviders } from '../test/testUtils';

const apiClientMock = vi.hoisted(() => ({
  register: vi.fn(),
}));

vi.mock('../services/api', () => ({
  apiClient: apiClientMock,
}));

describe('Register page', () => {
  beforeEach(() => {
    apiClientMock.register.mockReset();
    localStorage.clear();
  });

  it('validates password match before submit', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/register" element={<Register />} />
      </Routes>,
      { route: '/register' }
    );

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'newuser' } });
    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'new@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'secret1' } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'secret2' } });
    fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument();
  });

  it('submits registration and navigates to dashboard', async () => {
    apiClientMock.register.mockResolvedValue({
      access_token: 'token-abc',
      user: { user_id: 2, username: 'newuser', email: 'new@example.com', role: 'user' },
    });

    renderWithProviders(
      <Routes>
        <Route path="/register" element={<Register />} />
        <Route path="/dashboard" element={<div>Dashboard Page</div>} />
      </Routes>,
      { route: '/register' }
    );

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'newuser' } });
    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'new@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'secret1' } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'secret1' } });
    fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

    expect(await screen.findByText('Dashboard Page')).toBeInTheDocument();
  });
});
