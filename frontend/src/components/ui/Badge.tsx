'use client';

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-200/60 focus:ring-offset-0',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-white hover:bg-primary/80',
        secondary: 'border-[var(--app-field-border)] bg-[var(--app-control-bg)] text-[var(--text-secondary)] hover:bg-[var(--app-control-hover-bg)]',
        destructive: 'border-transparent bg-red-600 text-white hover:bg-red-500',
        outline: 'border-[var(--app-field-border)] text-[var(--text-primary)]',
        blue: 'border-[var(--app-chip-border)] bg-[var(--app-chip-bg)] text-[var(--app-chip-text)]',
        green: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
        amber: 'border-[var(--app-chip-border)] bg-[var(--app-chip-bg)] text-[var(--app-chip-text)]',
        red: 'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-200',
        gray: 'border-[var(--app-field-border)] bg-[var(--app-control-bg)] text-[var(--text-secondary)]',
        purple: 'border-[var(--app-chip-border)] bg-[var(--app-chip-bg)] text-[var(--app-chip-text)]',
      },
    },
    defaultVariants: {
      variant: 'blue',
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
