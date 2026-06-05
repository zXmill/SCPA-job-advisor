'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface AnimatedMetricBarProps {
  label: string;
  value: number;
  caption?: string;
  className?: string;
}

export function AnimatedMetricBar({ label, value, caption, className }: AnimatedMetricBarProps) {
  const reduceMotion = useReducedMotion();
  const width = `${Math.max(0, Math.min(100, value))}%`;

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center justify-between gap-4 text-sm">
        <span className="font-semibold text-slate-100">{label}</span>
        <span className="tabular-nums text-cyan-100">{value}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/10">
        <motion.div
          className="h-full rounded-full bg-[linear-gradient(90deg,#2563eb,#22d3ee)] shadow-[0_0_24px_rgba(34,211,238,0.34)]"
          initial={reduceMotion ? false : { width: 0 }}
          whileInView={{ width }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          style={reduceMotion ? { width } : undefined}
        />
      </div>
      {caption ? <p className="text-xs leading-relaxed text-slate-400">{caption}</p> : null}
    </div>
  );
}
