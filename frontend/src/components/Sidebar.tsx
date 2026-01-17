import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export const Sidebar = () => {
  const { user } = useAuth();
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1>Job Search</h1>
        <p>Campaign Manager</p>
        {user && (
          <Link to="/account" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="user-profile">
              <div className="user-avatar">
                <i className="fas fa-user"></i>
              </div>
              <div className="user-info">
                <div className="user-name">
                  <span>{user.username}</span>
                  <span className="user-badge">{user.role === 'admin' ? 'Admin' : 'User'}</span>
                </div>
                <div className="user-email">{user.email || 'No email'}</div>
              </div>
            </div>
          </Link>
        )}
      </div>
      <nav>
        <ul className="nav-menu">
          {user && (
            <>
              <li className="nav-item">
                <Link
                  to="/dashboard"
                  className={`nav-link ${isActive('/dashboard') ? 'active' : ''}`}
                >
                  <i className="fas fa-chart-line"></i>
                  <span>Dashboard</span>
                </Link>
              </li>
              <li className="nav-item">
                <Link
                  to="/campaigns"
                  className={`nav-link ${isActive('/campaigns') ? 'active' : ''}`}
                >
                  <i className="fas fa-folder-open"></i>
                  <span>Campaigns</span>
                </Link>
              </li>
              <li className="nav-item">
                <Link
                  to="/documents"
                  className={`nav-link ${isActive('/documents') ? 'active' : ''}`}
                >
                  <i className="fas fa-file-alt"></i>
                  <span>Documents</span>
                </Link>
              </li>
            </>
          )}
        </ul>
      </nav>
    </aside>
  );
};
