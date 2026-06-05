'use client';

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap text-sm font-semibold transition-all outline-none active:scale-[0.98] disabled:pointer-events-none disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-cyan-200/70 focus-visible:ring-offset-2 focus-visible:ring-offset-black',
  {
    variants: {
      variant: {
        default: 'rounded-md bg-primary text-white hover:bg-primary-hover',
        primary: 'liquid-glass-button liquid-glass-button-primary rounded-full border',
        ghost: 'liquid-glass-button liquid-glass-button-ghost rounded-full border',
        danger:
          'rounded-full border border-red-500/30 bg-red-500/10 text-red-700 hover:border-red-500/45 hover:bg-red-500/16 dark:border-red-300/35 dark:bg-red-500/14 dark:text-red-100 dark:hover:border-red-300/55 dark:hover:bg-red-500/22',
        destructive: 'rounded-md bg-red-600 text-white hover:bg-red-500',
        outline:
          'rounded-md border border-[var(--app-field-border)] bg-transparent text-[var(--text-primary)] hover:bg-[var(--app-control-hover-bg)]',
        secondary: 'rounded-md bg-[var(--app-control-bg)] text-[var(--text-primary)] hover:bg-[var(--app-control-hover-bg)]',
        link: 'rounded-md text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 px-3',
        md: 'px-4 py-2',
        lg: 'h-11 px-8',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      asChild = false,
      loading = false,
      disabled,
      icon,
      children,
      ...props
    },
    ref,
  ) => {
    const Comp = asChild ? Slot : 'button';

    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={!asChild ? disabled || loading : undefined}
        {...props}
      >
        {loading ? (
          <>
            <svg className="h-4 w-4 animate-spin text-white" fill="none" viewBox="0 0 24 24" aria-hidden>
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Memuat...
          </>
        ) : (
          <>
            {icon}
            {children}
          </>
        )}
      </Comp>
    );
  },
);
Button.displayName = 'Button';

export { Button, buttonVariants };
