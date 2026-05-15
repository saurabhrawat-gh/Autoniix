'use client';

import * as React from 'react';
import { cn } from './cn';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
  leftIcon?: React.ReactNode;
  rightSlot?: React.ReactNode;
  hint?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, leftIcon, rightSlot, hint, id, ...props }, ref) => {
    const inputEl = (
      <input
        ref={ref}
        id={id}
        className={cn(
          'w-full bg-surface-0 border text-content-primary rounded-md',
          'px-3.5 py-2.5 text-sm transition-all',
          'placeholder:text-content-tertiary',
          'focus:outline-none focus:ring-2',
          error
            ? 'border-status-error focus:border-status-error focus:ring-status-error/15'
            : 'border-border focus:border-accent focus:ring-accent/10',
          leftIcon && 'pl-9',
          rightSlot && 'pr-9',
          className
        )}
        {...props}
      />
    );

    if (!leftIcon && !rightSlot && !hint) return inputEl;

    return (
      <div className="w-full">
        <div className="relative">
          {leftIcon && (
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-content-tertiary pointer-events-none">
              {leftIcon}
            </span>
          )}
          {inputEl}
          {rightSlot && (
            <span className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center">
              {rightSlot}
            </span>
          )}
        </div>
        {hint && (
          <p className={cn('mt-1.5 text-xs', error ? 'text-status-error' : 'text-content-tertiary')}>
            {hint}
          </p>
        )}
      </div>
    );
  }
);
Input.displayName = 'Input';
