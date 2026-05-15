'use client';

import * as React from 'react';
import { cn } from './cn';

export function Kbd({ className, ...props }: React.HTMLAttributes<HTMLElement>) {
  return (
    <kbd
      className={cn(
        'inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded',
        'border border-border bg-surface-2 text-content-secondary',
        'text-[10px] font-mono font-semibold leading-none',
        className
      )}
      {...props}
    />
  );
}
