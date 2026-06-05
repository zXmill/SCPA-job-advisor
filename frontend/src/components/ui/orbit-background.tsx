'use client';

import { cn } from '@/lib/utils';

interface OrbitBackgroundProps {
  className?: string;
  density?: 'low' | 'medium';
  muted?: boolean;
}

const stars = Array.from({ length: 34 }, (_, index) => ({
  left: `${(index * 37) % 100}%`,
  top: `${(index * 19 + 11) % 100}%`,
  opacity: 0.22 + ((index * 13) % 30) / 100,
  scale: 0.6 + ((index * 7) % 5) / 10,
}));

export function OrbitBackground({ className, density = 'medium', muted = false }: OrbitBackgroundProps) {
  const visibleStars = density === 'low' ? stars.slice(0, 18) : stars;

  return (
    <div className={cn('pointer-events-none absolute inset-0 overflow-hidden', className)} aria-hidden>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_18%,rgba(37,99,235,0.20),transparent_33%),radial-gradient(circle_at_82%_18%,rgba(34,211,238,0.10),transparent_24%),linear-gradient(180deg,rgba(2,6,23,0.68)_0%,rgba(3,7,18,0.52)_48%,rgba(5,5,5,0.78)_100%)]" />
      <div className="scpa-noise absolute inset-0" />
      <div className={cn('absolute left-1/2 top-1/2 aspect-square w-[min(86vw,980px)] -translate-x-1/2 -translate-y-1/2 rounded-full border border-blue-200/10', !muted && 'scpa-orbit-slow')} />
      <div className={cn('absolute left-1/2 top-1/2 aspect-square w-[min(68vw,760px)] -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-cyan-200/14', !muted && 'scpa-orbit-reverse')} />
      <div className="absolute left-1/2 top-1/2 aspect-square w-[min(44vw,520px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,rgba(37,99,235,0.18),rgba(34,211,238,0.08)_34%,transparent_68%)] blur-sm" />
      {visibleStars.map((star, index) => (
        <span
          key={index}
          className="absolute h-1 w-1 rounded-full bg-cyan-100"
          style={{
            left: star.left,
            top: star.top,
            opacity: star.opacity,
            transform: `scale(${star.scale})`,
          }}
        />
      ))}
    </div>
  );
}
