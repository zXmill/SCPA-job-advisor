import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface GlassPanelProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  variant?: 'soft' | 'strong' | 'blue';
}

export function GlassPanel({ children, className, variant = 'soft', ...props }: GlassPanelProps) {
  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-lg border shadow-[0_28px_90px_rgba(0,0,0,0.32)] backdrop-blur-2xl',
        'before:pointer-events-none before:absolute before:inset-0 before:bg-[linear-gradient(135deg,rgba(255,255,255,0.12),transparent_34%,rgba(37,99,235,0.08))] before:opacity-70',
        variant === 'soft' && 'border-white/10 bg-white/[0.045]',
        variant === 'strong' && 'border-cyan-200/18 bg-slate-950/74',
        variant === 'blue' && 'border-blue-300/20 bg-blue-950/20',
        className,
      )}
      {...props}
    >
      <div className="relative z-[1]">{children}</div>
    </div>
  );
}
