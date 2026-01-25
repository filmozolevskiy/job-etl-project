import React, { useEffect, useState } from 'react';

interface EnvironmentInfo {
  environment: string;
  staging_slot?: number;
}

export const EnvironmentBanner: React.FC = () => {
  const [envInfo, setEnvInfo] = useState<EnvironmentInfo | null>(null);

  useEffect(() => {
    // Fetch environment info from health endpoint
    fetch('/api/health')
      .then(res => res.json())
      .then(data => {
        if (data.environment && data.environment !== 'production') {
          setEnvInfo({
            environment: data.environment,
            staging_slot: data.staging_slot
          });
        }
      })
      .catch(() => {
        // Silently fail - banner just won't show
      });
  }, []);

  // Only show in non-production environments
  if (!envInfo || envInfo.environment === 'production') {
    return null;
  }

  const slotText = envInfo.staging_slot 
    ? `Staging ${envInfo.staging_slot}` 
    : envInfo.environment.toUpperCase();

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      backgroundColor: '#f59e0b',
      color: '#000',
      textAlign: 'center',
      padding: '4px 8px',
      fontSize: '12px',
      fontWeight: 600,
      zIndex: 9999,
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      {slotText} Environment
    </div>
  );
};
