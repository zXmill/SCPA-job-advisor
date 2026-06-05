import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface ModelChipProps {
  children: ReactNode;
  tone?: 'blue' | 'cyan' | 'green' | 'slate';
  className?: string;
}

const toneClasses = {
  blue: 'border-blue-300/24 bg-blue-500/10 text-blue-100 shadow-[0_0_28px_rgba(37,99,235,0.16)]',
  cyan: 'border-cyan-200/26 bg-cyan-400/10 text-cyan-100 shadow-[0_0_28px_rgba(34,211,238,0.14)]',
  green: 'border-emerald-200/24 bg-emerald-400/10 text-emerald-100 shadow-[0_0_28px_rgba(16,185,129,0.12)]',
  slate: 'border-white/12 bg-white/[0.055] text-slate-100',
};

export function ModelChip({ children, tone = 'blue', className }: ModelChipProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold',
        toneClasses[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
