'use client';

import React from 'react';
import Link from 'next/link';

interface LiquidGlassSurfaceProps {
  children: React.ReactNode;
  className?: string;
  innerClassName?: string;
  style?: React.CSSProperties;
  href?: string;
  target?: string;
  interactive?: boolean;
}

const baseTiming = 'cubic-bezier(0.32, 0.72, 0, 1)';

export function LiquidGlassFilter() {
  return (
    <svg aria-hidden style={{ position: 'absolute', width: 0, height: 0 }}>
      <filter
        id="scpa-glass-distortion"
        x="0%"
        y="0%"
        width="100%"
        height="100%"
        filterUnits="objectBoundingBox"
      >
        <feTurbulence
          type="fractalNoise"
          baseFrequency="0.004 0.012"
          numOctaves="1"
          seed="17"
          result="turbulence"
        />
        <feGaussianBlur in="turbulence" stdDeviation="2" result="softMap" />
        <feDisplacementMap
          in="SourceGraphic"
          in2="softMap"
          scale="18"
          xChannelSelector="R"
          yChannelSelector="G"
        />
      </filter>
    </svg>
  );
}

export function LiquidGlassSurface({
  children,
  className = '',
  innerClassName = '',
  style,
  href,
  target,
  interactive = false,
}: LiquidGlassSurfaceProps) {
  const content = (
    <div
      className={`liquid-glass relative overflow-hidden rounded-[24px] ${
        interactive ? 'transition-transform duration-700 hover:-translate-y-1 active:scale-[0.99]' : ''
      } ${className}`}
      style={{ transitionTimingFunction: baseTiming, ...style }}
    >
      <div className="liquid-glass-distort absolute inset-0" />
      <div className="liquid-glass-fill absolute inset-0" />
      <div className="liquid-glass-bezel absolute inset-0" />
      <div className={`relative z-[1] ${innerClassName}`}>{children}</div>
    </div>
  );

  if (!href) return content;

  if (href.startsWith('/')) {
    return (
      <Link href={href} className="block">
        {content}
      </Link>
    );
  }

  return (
    <a href={href} target={target ?? '_blank'} rel="noopener noreferrer" className="block">
      {content}
    </a>
  );
}

interface LiquidGlassButtonProps {
  children: React.ReactNode;
  href?: string;
  onClick?: () => void;
  className?: string;
  variant?: 'primary' | 'ghost';
  icon?: React.ReactNode;
  type?: 'button' | 'submit' | 'reset';
  disabled?: boolean;
}

export function LiquidGlassButton({
  children,
  href,
  onClick,
  className = '',
  variant = 'primary',
  icon,
  type = 'button',
  disabled = false,
}: LiquidGlassButtonProps) {
  const classes = `liquid-glass-button group inline-flex items-center justify-center gap-3 rounded-full px-5 py-2.5 text-sm font-semibold transition-all duration-700 active:scale-[0.98] ${
    variant === 'primary' ? 'liquid-glass-button-primary' : 'liquid-glass-button-ghost'
  } ${disabled ? 'pointer-events-none opacity-60' : ''} ${className}`;

  const content = (
    <>
      <span>{children}</span>
      {icon && (
        <span className="grid h-7 w-7 place-items-center rounded-full bg-white/14 text-current transition-transform duration-700 group-hover:translate-x-0.5 group-hover:-translate-y-0.5">
          {icon}
        </span>
      )}
    </>
  );

  if (href) {
    if (href.startsWith('/')) {
      return (
        <Link href={href} className={classes} style={{ transitionTimingFunction: baseTiming }}>
          {content}
        </Link>
      );
    }

    return (
      <a href={href} className={classes} style={{ transitionTimingFunction: baseTiming }}>
        {content}
      </a>
    );
  }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={classes}
      style={{ transitionTimingFunction: baseTiming }}
    >
      {content}
    </button>
  );
}

export const Component = () => (
  <div className="grid min-h-[100dvh] place-items-center bg-[var(--bg-deep)] p-6">
    <LiquidGlassFilter />
    <LiquidGlassSurface className="max-w-xl p-8" innerClassName="space-y-5 text-center">
      <p className="text-sm font-semibold text-[var(--text-secondary)]">SCPA liquid glass surface</p>
      <LiquidGlassButton href="/auth?mode=signup" icon={<span aria-hidden>-&gt;</span>}>
        Bangun profil
      </LiquidGlassButton>
    </LiquidGlassSurface>
  </div>
);
