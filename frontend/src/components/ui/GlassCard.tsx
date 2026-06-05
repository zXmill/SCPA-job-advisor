'use client';

import React from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { animation } from '@/lib/design-tokens';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  glow?: boolean;
  href?: string;
  onClick?: () => void;
}

export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  className = '',
  glow = false,
  href,
  onClick,
}) => {
  // Theme-aware via CSS variables defined in globals.css.
  const cardStyle: React.CSSProperties = {
    background: 'var(--app-card-bg)',
    border: '1px solid var(--app-card-border)',
    backdropFilter: 'blur(14px) saturate(1.08)',
    WebkitBackdropFilter: 'blur(14px) saturate(1.08)',
    borderRadius: '16px',
    boxShadow: 'var(--app-card-shadow)',
    color: 'var(--text-primary)',
  };

  const MotionDiv = motion.div;

  if (href) {
    return (
      <Link href={href} style={{ textDecoration: 'none' }}>
        <MotionDiv
          className={`p-5 md:p-6 ${className}`}
          style={cardStyle}
          whileHover={{ y: -2, borderColor: 'rgba(147,197,253,0.28)' }}
          whileTap={{ scale: 0.992 }}
          transition={animation.cardHover}
        >
          {children}
        </MotionDiv>
      </Link>
    );
  }

  if (onClick) {
    return (
      <button
        onClick={onClick}
        style={{ border: 'none', background: 'none', padding: 0, cursor: 'pointer', width: '100%' }}
      >
        <MotionDiv
          className={`p-5 md:p-6 ${className}`}
          style={cardStyle}
          whileHover={{ y: -2, borderColor: 'rgba(147,197,253,0.28)' }}
          whileTap={{ scale: 0.992 }}
          transition={animation.cardHover}
        >
          {children}
        </MotionDiv>
      </button>
    );
  }

  return (
    <MotionDiv
      className={`p-5 md:p-6 ${className}`}
      style={cardStyle}
      whileHover={glow ? { y: -2, borderColor: 'rgba(147,197,253,0.28)' } : undefined}
      transition={animation.cardHover}
    >
      {children}
    </MotionDiv>
  );
};
