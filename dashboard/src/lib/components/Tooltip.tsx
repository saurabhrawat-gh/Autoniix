'use client';

import { type ReactNode } from 'react';
import { cn } from '../utils';

interface TipProps {
  text: string;
  children: ReactNode;
  pos?: 'top' | 'bottom';
  className?: string;
}

export function Tip({ text, children, pos = 'top', className }: TipProps) {
  return (
    <span className={cn('has-tooltip inline-flex', className)}>
      {children}
      <span
        className={cn(
          'tooltip-text',
          pos === 'bottom' && '!bottom-auto !top-full !mt-1.5 !mb-0',
        )}
      >
        {text}
      </span>
    </span>
  );
}
