import { Link } from 'react-router-dom';

export const NotFound = () => {
  return (
    <div className="empty-state">
      <h1>404</h1>
      <h2>Page Not Found</h2>
      <p>The page you're looking for doesn't exist.</p>
      <Link to="/dashboard" className="btn btn-primary">
        Go to Dashboard
      </Link>
    </div>
  );
};
