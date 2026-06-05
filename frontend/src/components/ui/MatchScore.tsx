'use client';

import React from 'react';
import { motion } from 'framer-motion';

interface MatchScoreProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
}

export const MatchScore: React.FC<MatchScoreProps> = ({ score, size = 'md' }) => {
  const sizeStyles = {
    sm: { width: 48, height: 48, strokeWidth: 4 },
    md: { width: 64, height: 64, strokeWidth: 5 },
    lg: { width: 80, height: 80, strokeWidth: 6 },
  };

  const { width, height, strokeWidth } = sizeStyles[size];
  const radius = (width - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="relative" style={{ width, height }}>
      <svg width={width} height={height} className="transform -rotate-90">
        <circle
          cx={width / 2}
          cy={height / 2}
          r={radius}
          fill="none"
          stroke="rgba(59,130,246,0.2)"
          strokeWidth={strokeWidth}
        />
        <motion.circle
          cx={width / 2}
          cy={height / 2}
          r={radius}
          fill="none"
          stroke="#3B82F6"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: 'easeOut' }}
          style={{ strokeDasharray: circumference }}
        />
      </svg>
      <div
        className="absolute inset-0 flex items-center justify-center font-bold"
        style={{
          fontSize: size === 'sm' ? '12px' : size === 'md' ? '14px' : '18px',
          color: 'var(--text-primary)',
        }}
      >
        {score}%
      </div>
    </div>
  );
};
