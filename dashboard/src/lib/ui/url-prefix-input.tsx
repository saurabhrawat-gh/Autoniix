'use client';

import * as React from 'react';
import { cn } from './cn';

export interface UrlPrefixInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'id'> {
  prefix: string;
  id?: string;
  error?: boolean;
  hint?: string;
  label?: string;
}

export const UrlPrefixInput = React.forwardRef<HTMLInputElement, UrlPrefixInputProps>(
  ({ prefix, id, error, hint, label, className, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label htmlFor={id} className="block text-caption font-medium text-content-secondary mb-1.5">
            {label}
          </label>
        )}
        <div
          className={cn(
            'flex items-center rounded-md border bg-surface-0 overflow-hidden',
            'transition-[border-color,box-shadow] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)]',
            'focus-within:ring-2',
            error
              ? 'border-status-error focus-within:border-status-error focus-within:ring-status-error/15'
              : 'border-border focus-within:border-accent focus-within:ring-accent/10'
          )}
        >
          <span className="flex-shrink-0 px-3 py-2.5 text-sm text-content-muted bg-surface-2 border-r border-border select-none whitespace-nowrap">
            {prefix}
          </span>
          <input
            ref={ref}
            id={id}
            className={cn(
              'flex-1 min-w-0 px-3 py-2.5 text-sm text-content-primary bg-transparent',
              'placeholder:text-content-tertiary',
              'focus:outline-none',
              className
            )}
            {...props}
          />
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
UrlPrefixInput.displayName = 'UrlPrefixInput';
