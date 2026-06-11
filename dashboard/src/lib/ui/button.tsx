'use client';

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import { cn } from './cn';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 font-medium rounded-full ' +
    'transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-[120ms] ' +
    'ease-[cubic-bezier(0.2,0,0,1)] ' +
    'active:scale-[0.98] ' +
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 ' +
    'disabled:opacity-[0.56] disabled:cursor-not-allowed disabled:pointer-events-none select-none',
  {
    variants: {
      variant: {
        primary:
          'bg-accent-primary hover:bg-accent-primary/90 text-accent-primary-fg',
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
        md: 'text-sm px-4 py-2 h-10',
        lg: 'text-sm px-6 py-3 h-12',
        xl: 'text-base px-6 py-3 h-12',
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
    const leading = loading ? (
      <Loader2 className="animate-spin" size={size === 'sm' ? 13 : 15} />
    ) : (
      leftIcon ?? null
    );
    const trailing = !loading ? (rightIcon ?? null) : null;

    if (asChild) {
      // Radix Slot requires exactly one React element child. Clone the
      // consumer-provided child and inject icons inside it so the rendered
      // element (e.g. <Link>) still styles as a button with icons.
      const child = React.Children.only(children) as React.ReactElement;
      return (
        <Slot
          ref={ref}
          className={cn(buttonVariants({ variant, size }), className)}
          {...props}
        >
          {React.cloneElement(
            child,
            undefined,
            leading,
            child.props.children,
            trailing,
          )}
        </Slot>
      );
    }

    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || loading}
        {...props}
      >
        {leading}
        {children}
        {trailing}
      </button>
    );
  }
);
Button.displayName = 'Button';

export { buttonVariants };
