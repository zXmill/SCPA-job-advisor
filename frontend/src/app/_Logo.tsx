/* ───────────────────────────────────────────────────────────────────────────
   SCPA Logo — inline SVG so it can be recolored / animated.
   Strictly follows /logo/logo-guide.md:
     - Primary  #2563EB → Light #3B82F6 (linear top-left → bottom-right)
     - White variant uses #60A5FA → #93C5FD for dark backgrounds
     - 24px icon-only minimum; never rotate, distort, or add effects
   ─────────────────────────────────────────────────────────────────────── */

import type { CSSProperties } from 'react';

type Variant = 'gradient' | 'light' | 'mono';

export function LogoIcon({
  size = 28,
  variant = 'gradient',
  className,
  style,
  glow = false,
  animated = false,
}: {
  size?: number;
  variant?: Variant;
  className?: string;
  style?: CSSProperties;
  glow?: boolean;
  animated?: boolean;
}) {
  // Unique gradient id so multiple instances on the page don't collide.
  const gid = `scpa-grad-${variant}-${size}`;

  const stops =
    variant === 'gradient'
      ? ['#2563EB', '#3B82F6']
      : variant === 'light'
      ? ['#60A5FA', '#93C5FD']
      : ['#FFFFFF', '#FFFFFF'];

  const stroke = variant === 'mono' ? '#FFFFFF' : `url(#${gid})`;
  const fill = variant === 'mono' ? '#FFFFFF' : `url(#${gid})`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{
        filter: glow ? 'drop-shadow(0 0 18px rgba(59,130,246,0.55))' : undefined,
        ...style,
      }}
      aria-label="SCPA logo"
    >
      <defs>
        <linearGradient id={gid} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={stops[0]} />
          <stop offset="100%" stopColor={stops[1]} />
        </linearGradient>
      </defs>

      {/* Connector paths (drawn first so nodes sit on top) */}
      <path
        d="M 25 75 Q 35 65 40 55"
        stroke={stroke}
        strokeWidth={animated ? 5 : 4}
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M 40 55 Q 50 50 60 45"
        stroke={stroke}
        strokeWidth={animated ? 5 : 4}
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M 60 45 Q 67.5 35 75 25"
        stroke={stroke}
        strokeWidth={animated ? 5 : 4}
        strokeLinecap="round"
        fill="none"
      />

      {/* Arrow head */}
      <path
        d="M 75 25 L 70 32 M 75 25 L 82 30"
        stroke={stroke}
        strokeWidth={animated ? 5 : 4}
        strokeLinecap="round"
        fill="none"
      />

      {/* Nodes */}
      <circle cx="25" cy="75" r="8" fill={fill} />
      <circle cx="40" cy="55" r="8" fill={fill} />
      <circle cx="60" cy="45" r="8" fill={fill} />
      <circle cx="75" cy="25" r="8" fill={fill} />
    </svg>
  );
}

/* Horizontal lockup = icon + "SCPA" wordmark in the same gradient */
export function LogoLockup({
  iconSize = 28,
  variant = 'gradient',
  className,
  glow = false,
}: {
  iconSize?: number;
  variant?: Variant;
  className?: string;
  glow?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-2.5 ${className ?? ''}`}
      aria-label="SCPA — Smart Career Path Advisor"
    >
      <LogoIcon size={iconSize} variant={variant} glow={glow} />
      <span
        className="font-extrabold tracking-tight"
        style={{
          fontSize: `${Math.round(iconSize * 0.58)}px`,
          letterSpacing: '-0.02em',
          background:
            variant === 'mono'
              ? '#FFFFFF'
              : variant === 'light'
              ? 'linear-gradient(135deg, #93C5FD, #60A5FA)'
              : 'linear-gradient(135deg, #FFFFFF, #CBD5E1)',
          WebkitBackgroundClip: 'text',
          backgroundClip: 'text',
          color: 'transparent',
        }}
      >
        SCPA
      </span>
    </span>
  );
}
