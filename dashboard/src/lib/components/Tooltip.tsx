'use client';

import { type ReactNode } from 'react';
import { cn } from '../utils';

interface TipProps {
  text: string;
  children: ReactNode;
  pos?: 'top' | 'bottom' | 'right';
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
          pos === 'right' && '!bottom-auto !top-1/2 !-translate-y-1/2 !left-full !translate-x-2 !mb-0',
        )}
      >
        {text}
      </span>
    </span>
  );
}
