'use client';

import * as React from 'react';
import { cn } from './cn';

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-md bg-surface-2 animate-skeleton-pulse',
        className
      )}
      {...props}
    />
  );
}
