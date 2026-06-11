'use client';

import * as React from 'react';
import { cn } from './cn';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
  label?: React.ReactNode;
  leftIcon?: React.ReactNode;
  rightSlot?: React.ReactNode;
  hint?: React.ReactNode;
  variant?: 'form' | 'search';
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, label, leftIcon, rightSlot, hint, id, variant = 'form', ...props }, ref) => {
    const isSearch = variant === 'search';
    const inputEl = (
      <input
        ref={ref}
        id={id}
        className={cn(
          'w-full bg-surface-0 border text-content-primary',
          'transition-[border-color,box-shadow,background-color] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)]',
          'placeholder:text-content-tertiary',
          'hover:border-border-hover hover:bg-surface-0',
          'focus:outline-none focus:ring-2',
          isSearch
            ? 'h-9 px-3.5 text-sm rounded-full'
            : 'h-11 px-3.5 text-sm rounded-[8px]',
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

    if (!label && !leftIcon && !rightSlot && !hint) return inputEl;

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={id} className="block text-[11px] font-medium text-content-secondary mb-1.5">
            {label}
          </label>
        )}
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
