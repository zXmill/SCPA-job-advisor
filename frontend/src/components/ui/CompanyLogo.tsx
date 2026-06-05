'use client';

import React, { useState } from 'react';
import Image from 'next/image';

interface CompanyLogoProps {
  logoUrl?: string | null;
  companyName: string;
  size?: number;
  className?: string;
}

function isSafeImageUrl(url: string | null | undefined): url is string {
  if (!url) return false;
  try {
    const u = new URL(url);
    const isLocalGateway = u.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(u.hostname);
    return isLocalGateway;
  } catch {
    return url.startsWith('/api/company-logo');
  }
}

export const CompanyLogo: React.FC<CompanyLogoProps> = ({
  logoUrl,
  companyName,
  size = 40,
  className = '',
}) => {
  const [failedLogoUrl, setFailedLogoUrl] = useState<string | null>(null);
  const initial = (companyName || '?').charAt(0).toUpperCase();
  const showRemoteLogo = isSafeImageUrl(logoUrl) && failedLogoUrl !== logoUrl;

  if (showRemoteLogo) {
    return (
      <Image
        src={logoUrl}
        alt={companyName}
        width={size}
        height={size}
        className={`rounded-lg object-cover flex-shrink-0 ${className}`}
        style={{ width: size, height: size }}
        onError={() => setFailedLogoUrl(logoUrl)}
        unoptimized
      />
    );
  }

  return (
    <div
      role="img"
      aria-label={`${companyName} logo`}
      className={`rounded-lg flex items-center justify-center font-bold flex-shrink-0 text-white ${className}`}
      style={{
        width: size,
        height: size,
        fontSize: size * 0.4,
        background: 'linear-gradient(135deg, #2563EB 0%, #1d4ed8 100%)',
      }}
    >
      {initial}
    </div>
  );
};
