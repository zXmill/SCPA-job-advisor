'use client';

import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { AnimatedShaderHero } from './animated-shader-hero';
import { LiquidGlassFilter, LiquidGlassSurface } from './liquid-glass';
import { LogoIcon } from './Logo';
import { VapourTextEffect } from './vapour-text-effect';

const DEFAULT_MESSAGES = [
  'Membaca sinyal profil',
  'Mencocokkan semantic fit',
  'Menghitung skill gap',
];

interface CareerLoadingProps {
  title?: string;
  messages?: string[];
  fullScreen?: boolean;
  className?: string;
}

export function CareerLoading({
  title = 'Menyiapkan SCPA',
  messages = DEFAULT_MESSAGES,
  fullScreen = false,
  className = '',
}: CareerLoadingProps) {
  const [messageIndex, setMessageIndex] = useState(0);
  const safeMessages = messages.length > 0 ? messages : DEFAULT_MESSAGES;

  useEffect(() => {
    if (safeMessages.length <= 1) return;
    const interval = window.setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % safeMessages.length);
    }, 1400);
    return () => window.clearInterval(interval);
  }, [safeMessages.length]);

  const content = (
    <AnimatedShaderHero
      compact={!fullScreen}
      className={fullScreen ? className : `border border-[var(--app-card-border)] ${className}`}
      contentClassName="px-5 py-10 md:px-8"
    >
      <LiquidGlassFilter />
      <LiquidGlassSurface
        className="w-full max-w-xl px-6 py-8 md:px-9 md:py-10"
        innerClassName="flex flex-col items-center text-center"
      >
        <motion.div
          initial={{ opacity: 0, y: -8, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="relative"
        >
          <div aria-hidden className="loader-logo-halo absolute inset-[-18px] rounded-full" />
          <LogoIcon size={fullScreen ? 60 : 48} glow />
        </motion.div>

        <VapourTextEffect
          key={title}
          as="h1"
          className="mt-7 text-2xl font-semibold tracking-[-0.03em] text-[var(--text-primary)] md:text-3xl"
        >
          {title}
        </VapourTextEffect>

        <div className="mt-4 min-h-6 text-sm text-[var(--text-secondary)]" aria-live="polite">
          <AnimatePresence mode="wait">
            <motion.p
              key={safeMessages[messageIndex]}
              initial={{ opacity: 0, y: 6, filter: 'blur(8px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              exit={{ opacity: 0, y: -6, filter: 'blur(8px)' }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            >
              {safeMessages[messageIndex]}
            </motion.p>
          </AnimatePresence>
        </div>

        <div className="mt-7 w-full max-w-xs" aria-hidden="true">
          <div className="scpa-loader-track">
            <div className="scpa-loader-bar" />
          </div>
          <div className="mt-4 flex items-center justify-center gap-2 text-[10px] font-bold tracking-[0.16em] text-[var(--text-tertiary)]">
            <span>SBERT</span>
            <span className="h-1 w-1 rounded-full bg-[var(--primary)]" />
            <span>NCF</span>
            <span className="h-1 w-1 rounded-full bg-[var(--primary)]" />
            <span>DQN</span>
          </div>
        </div>
      </LiquidGlassSurface>
    </AnimatedShaderHero>
  );

  if (fullScreen) {
    return (
      <main role="status" aria-live="polite" aria-busy="true" className="min-h-screen bg-[var(--bg-deep)] text-[var(--text-primary)]">
        {content}
      </main>
    );
  }

  return (
    <div role="status" aria-live="polite" aria-busy="true">
      {content}
    </div>
  );
}

export const Component = () => <CareerLoading fullScreen />;
