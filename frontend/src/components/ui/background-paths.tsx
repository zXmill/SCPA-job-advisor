'use client';

import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

const PATH_DURATIONS: number[] = Array.from(
  { length: 36 },
  (_, i) => 20 + ((i * 7) % 11)
);

function FloatingPaths({ position }: { position: number }) {
  // Only the path geometry depends on `position`; durations are static.
  const paths = useMemo(
    () =>
      Array.from({ length: 36 }, (_, i) => ({
        id: i,
        d: `M-${380 - i * 5 * position} -${189 + i * 6}C-${
          380 - i * 5 * position
        } -${189 + i * 6} -${312 - i * 5 * position} ${216 - i * 6} ${
          152 - i * 5 * position
        } ${343 - i * 6}C${616 - i * 5 * position} ${470 - i * 6} ${
          684 - i * 5 * position
        } ${875 - i * 6} ${684 - i * 5 * position} ${875 - i * 6}`,
        width: 0.5 + i * 0.03,
        duration: PATH_DURATIONS[i] ?? 25,
      })),
    [position]
  );

  return (
    <div className="absolute inset-0 pointer-events-none">
      <svg
        className="w-full h-full text-[var(--text-primary)]"
        viewBox="0 0 696 316"
        fill="none"
      >
        <title>Background Paths</title>
        {paths.map((path) => (
          <motion.path
            key={path.id}
            d={path.d}
            stroke="currentColor"
            strokeWidth={path.width}
            strokeOpacity={0.1 + path.id * 0.03}
            initial={{ pathLength: 0.3, opacity: 0.6 }}
            animate={{
              pathLength: 1,
              opacity: [0.3, 0.6, 0.3],
              pathOffset: [0, 1, 0],
            }}
            transition={{
              duration: path.duration,
              repeat: Number.POSITIVE_INFINITY,
              ease: 'linear',
            }}
          />
        ))}
      </svg>
    </div>
  );
}

export interface BackgroundPathsProps {
  title?: string;
  ctaLabel?: string;
  className?: string;
}

export function BackgroundPaths({
  title = 'Background Paths',
  ctaLabel = 'Discover Excellence',
  className,
}: BackgroundPathsProps) {
  const words = title.split(' ');

  return (
    <div
      className={cn(
        'relative min-h-[60vh] w-full flex items-center justify-center overflow-hidden bg-[var(--bg-deep)]',
        className
      )}
    >
      <div className="absolute inset-0">
        <FloatingPaths position={1} />
        <FloatingPaths position={-1} />
      </div>

      <div className="relative z-10 container mx-auto px-4 md:px-6 text-center">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 2 }}
          className="max-w-4xl mx-auto"
        >
          <h1 className="text-5xl sm:text-7xl md:text-8xl font-bold mb-8 tracking-tighter text-[var(--text-primary)]">
            {words.map((word, wordIndex) => (
              <span
                key={`${word}-${wordIndex}`}
                className="inline-block mr-4 last:mr-0"
              >
                {word.split('').map((letter, letterIndex) => (
                  <motion.span
                    key={`${wordIndex}-${letterIndex}`}
                    initial={{ y: 100, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{
                      delay: wordIndex * 0.1 + letterIndex * 0.03,
                      type: 'spring',
                      stiffness: 150,
                      damping: 25,
                    }}
                    className="inline-block text-[var(--text-primary)]"
                  >
                    {letter}
                  </motion.span>
                ))}
              </span>
            ))}
          </h1>

          <div className="inline-block group relative bg-gradient-to-b from-white/10 to-white/0 p-px rounded-2xl backdrop-blur-lg overflow-hidden">
            <Button
              variant="ghost"
              className="rounded-[1.15rem] px-8 py-6 text-lg font-semibold backdrop-blur-md bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)] text-[var(--text-primary)] transition-all duration-300 group-hover:-translate-y-0.5 border border-[var(--glass-border)]"
            >
              <span className="opacity-90 group-hover:opacity-100 transition-opacity">
                {ctaLabel}
              </span>
              <span className="ml-3 opacity-70 group-hover:opacity-100 group-hover:translate-x-1.5 transition-all duration-300">
                →
              </span>
            </Button>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
