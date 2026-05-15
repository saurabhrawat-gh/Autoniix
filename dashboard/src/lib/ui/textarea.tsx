'use client';

import * as React from 'react';
import { cn } from './cn';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean;
  hint?: React.ReactNode;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, hint, ...props }, ref) => {
    const el = (
      <textarea
        ref={ref}
        className={cn(
          'w-full bg-surface-0 border text-content-primary rounded-md',
          'px-3.5 py-2.5 text-sm transition-all min-h-[80px] resize-y',
          'placeholder:text-content-tertiary',
          'focus:outline-none focus:ring-2',
          error
            ? 'border-status-error focus:border-status-error focus:ring-status-error/15'
            : 'border-border focus:border-accent focus:ring-accent/10',
          className
        )}
        {...props}
      />
    );
    if (!hint) return el;
    return (
      <div className="w-full">
        {el}
        <p className={cn('mt-1.5 text-xs', error ? 'text-status-error' : 'text-content-tertiary')}>
          {hint}
        </p>
      </div>
    );
  }
);
Textarea.displayName = 'Textarea';
