'use client';

import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';

interface VapourTextEffectProps {
  children?: string;
  text?: string;
  as?: React.ElementType;
  className?: string;
  delay?: number;
  stagger?: number;
}

export function VapourTextEffect({
  children,
  text,
  as: Element = 'span',
  className = '',
  delay = 0,
  stagger = 0.035,
}: VapourTextEffectProps) {
  const reducedMotion = useReducedMotion();
  const content = text ?? children ?? '';
  const characters = Array.from(content);

  return (
    <Element className={`vapour-text ${className}`} aria-label={content}>
      {characters.map((char, index) => {
        const isSpace = char === ' ';
        return (
          <motion.span
            key={`${char}-${index}`}
            aria-hidden="true"
            className="vapour-letter inline-block"
            initial={reducedMotion ? false : { opacity: 0, y: 10, filter: 'blur(14px)' }}
            animate={reducedMotion ? { opacity: 1 } : { opacity: 1, y: 0, filter: 'blur(0px)' }}
            transition={{
              duration: 0.72,
              delay: delay + index * stagger,
              ease: [0.22, 1, 0.36, 1],
            }}
          >
            {isSpace ? '\u00a0' : char}
          </motion.span>
        );
      })}
    </Element>
  );
}

export const Component = () => (
  <div className="grid min-h-screen place-items-center bg-[var(--bg-deep)] text-white">
    <VapourTextEffect as="h1" className="text-4xl font-semibold">
      SCPA loading
    </VapourTextEffect>
  </div>
);
