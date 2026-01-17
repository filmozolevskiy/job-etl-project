import React, { type ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { useAuth } from '../contexts/AuthContext';

interface LayoutProps {
  children: ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { isAuthenticated } = useAuth();

  return (
    <div className={isAuthenticated ? '' : 'login-page register-page'}>
      {isAuthenticated && (
        <div className="sidebar-container">
          <Sidebar />
        </div>
      )}
      <main className="main-content">
        {children}
      </main>
    </div>
  );
};
