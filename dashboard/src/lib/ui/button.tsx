'use client';

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import { cn } from './cn';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 font-medium rounded-md transition-all ' +
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 ' +
    'disabled:opacity-50 disabled:cursor-not-allowed select-none',
  {
    variants: {
      variant: {
        primary:
          'bg-accent hover:bg-accent-hover text-content-inverse',
        secondary:
          'bg-surface-0 border border-border hover:border-border-hover hover:bg-surface-1 ' +
          'text-content-secondary hover:text-content-primary',
        ghost:
          'text-content-secondary hover:text-content-primary hover:bg-surface-2',
        tonal:
          'bg-accent/10 text-accent hover:bg-accent/15',
        destructive:
          'bg-status-error/10 text-status-error border border-status-error/30 hover:bg-status-error/15',
        link:
          'text-accent hover:underline underline-offset-4 px-0 py-0 h-auto',
        outline:
          'border border-border hover:border-accent text-content-primary hover:text-accent bg-transparent',
      },
      size: {
        sm: 'text-xs px-2.5 py-1.5 h-8',
        md: 'text-sm px-3.5 py-2 h-9',
        lg: 'text-sm px-5 py-2.5 h-10',
        icon: 'h-9 w-9 p-0',
        'icon-sm': 'h-8 w-8 p-0',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant, size, asChild = false, loading, leftIcon, rightIcon, children, disabled, ...props },
    ref
  ) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || loading}
        {...props}
      >
        {loading ? (
          <Loader2 className="animate-spin" size={size === 'sm' ? 13 : 15} />
        ) : (
          leftIcon
        )}
        {children}
        {!loading && rightIcon}
      </Comp>
    );
  }
);
Button.displayName = 'Button';

export { buttonVariants };
