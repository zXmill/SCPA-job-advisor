'use client';

import React from 'react';

interface MatchDonutProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export default function MatchDonut({ score, size = 80, strokeWidth = 6, className = '' }: MatchDonutProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const getColor = () => {
    if (score >= 85) return '#10B981';
    if (score >= 70) return '#10B981';
    return 'var(--text-secondary)';
  };

  return (
    <div className={`match-donut ${className}`} style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--border-subtle)"
          strokeWidth={strokeWidth}
        />
        {/* Score arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={getColor()}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease-in-out' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{score}%</span>
        <span className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-secondary)' }}>Match</span>
      </div>
    </div>
  );
}
