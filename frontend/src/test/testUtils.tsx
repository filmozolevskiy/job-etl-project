import type { FC, ReactElement, ReactNode } from 'react';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';

interface RenderOptions {
  route?: string;
  withAuth?: boolean;
}

export const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

export const renderWithProviders = (ui: ReactElement, options: RenderOptions = {}) => {
  const { route = '/', withAuth = true } = options;
  const queryClient = createTestQueryClient();

  const Wrapper: FC<{ children: ReactNode }> = ({ children }) => {
    const content = withAuth ? <AuthProvider>{children}</AuthProvider> : children;
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>{content}</MemoryRouter>
      </QueryClientProvider>
    );
  };

  return { queryClient, ...render(ui, { wrapper: Wrapper }) };
};
