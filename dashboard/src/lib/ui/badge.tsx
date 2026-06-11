'use client';

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from './cn';

const badgeVariants = cva(
  'inline-flex items-center font-medium rounded-full transition-colors',
  {
    variants: {
      variant: {
        neutral: 'bg-surface-2 text-content-secondary',
        accent: 'bg-accent/10 text-accent',
        secondary: 'bg-secondary/10 text-secondary',
        success: 'bg-status-success/10 text-status-success',
        warning: 'bg-status-warning/10 text-status-warning',
        error: 'bg-status-error/10 text-status-error',
        info: 'bg-status-info/10 text-status-info',
        outline: 'border border-border text-content-secondary',
        short: 'bg-accent/10 text-accent uppercase tracking-wider',
        long: 'bg-secondary/10 text-secondary uppercase tracking-wider',
      },
      size: {
        sm: 'text-[10px] px-1.5 py-0.5 font-semibold',
        md: 'text-xs px-2 py-0.5',
        lg: 'text-sm px-2.5 py-1',
      },
    },
    defaultVariants: { variant: 'neutral', size: 'md' },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, size, ...props }, ref) => (
    <span ref={ref} className={cn(badgeVariants({ variant, size }), className)} {...props} />
  )
);
Badge.displayName = 'Badge';

export { badgeVariants };
