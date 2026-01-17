import { Routes, Route } from 'react-router-dom';
import { screen } from '@testing-library/react';
import { ProtectedRoute } from './ProtectedRoute';
import { renderWithProviders } from '../test/testUtils';

const ProtectedContent = () => <div>Protected Content</div>;

describe('ProtectedRoute', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('redirects to login when unauthenticated', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route
          path="/protected"
          element={
            <ProtectedRoute>
              <ProtectedContent />
            </ProtectedRoute>
          }
        />
      </Routes>,
      { route: '/protected' }
    );

    expect(await screen.findByText('Login Page')).toBeInTheDocument();
  });

  it('renders content when authenticated', async () => {
    localStorage.setItem(
      'user',
      JSON.stringify({ user_id: 1, username: 'demo', email: 'demo@example.com', role: 'user' })
    );
    localStorage.setItem('access_token', 'token-123');

    renderWithProviders(
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route
          path="/protected"
          element={
            <ProtectedRoute>
              <ProtectedContent />
            </ProtectedRoute>
          }
        />
      </Routes>,
      { route: '/protected' }
    );

    expect(await screen.findByText('Protected Content')).toBeInTheDocument();
  });
});
