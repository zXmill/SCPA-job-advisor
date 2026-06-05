'use client';

import React from 'react';

interface LogoIconProps {
  size?: number;
  glow?: boolean;
  className?: string;
}

export const LogoIcon: React.FC<LogoIconProps> = ({ size = 28, glow = false, className = '' }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 80 80"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{
        filter: glow ? 'drop-shadow(0 0 8px rgba(37,99,235,0.5))' : 'none',
      }}
    >
      <defs>
        <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#2563EB" />
          <stop offset="100%" stopColor="#3B82F6" />
        </linearGradient>
      </defs>

      {/* Connecting lines */}
      <path
        d="M25 75 L40 55"
        stroke="#3B82F6"
        strokeWidth="1.5"
        fill="none"
      />
      <path
        d="M40 55 L60 45"
        stroke="#3B82F6"
        strokeWidth="1.5"
        fill="none"
      />
      <path
        d="M60 45 L75 25"
        stroke="#3B82F6"
        strokeWidth="1.5"
        fill="none"
      />

      {/* Arrowhead on last line */}
      <path
        d="M75 25 L70 28 M75 25 L72 30"
        stroke="#3B82F6"
        strokeWidth="1.5"
        strokeLinecap="round"
      />

      {/* Nodes */}
      <circle cx="25" cy="75" r="3.5" fill="url(#logoGradient)" />
      <circle cx="40" cy="55" r="3.5" fill="url(#logoGradient)" />
      <circle cx="60" cy="45" r="3.5" fill="url(#logoGradient)" />
      <circle cx="75" cy="25" r="3.5" fill="url(#logoGradient)" />
    </svg>
  );
};

interface LogoLockupProps {
  iconSize?: number;
  variant?: 'default' | 'light' | 'compact';
  className?: string;
}

export const LogoLockup: React.FC<LogoLockupProps> = ({
  iconSize = 28,
  variant = 'default',
  className = ''
}) => {
  const textSize = variant === 'compact' ? 'text-lg' : variant === 'light' ? 'text-2xl' : 'text-xl';
  const fontWeight = 'font-extrabold';
  const letterSpacing = variant === 'compact' ? 'tracking-tight' : 'tracking-tighter';

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <LogoIcon size={iconSize} glow={variant !== 'compact'} />
      <span
        className={`${textSize} ${fontWeight} ${letterSpacing} bg-gradient-to-r from-blue-400 to-blue-300 bg-clip-text text-transparent`}
      >
        SCPA
      </span>
    </div>
  );
};
