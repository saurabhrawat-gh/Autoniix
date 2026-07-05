'use client';

import { type ReactNode } from 'react';
import { TooltipProvider, SimpleTooltip } from '@/lib/ui';

interface TipProps {
  text: string;
  children: ReactNode;
  pos?: 'top' | 'bottom' | 'right' | 'left';
  className?: string;
}

/**
 * Backwards-compatible wrapper around `SimpleTooltip` for legacy callers.
 * New code should import `SimpleTooltip` from `@/lib/ui` directly.
 */
export function Tip({ text, children, pos = 'top', className }: TipProps) {
  return (
    <TooltipProvider delayDuration={250}>
      <SimpleTooltip content={text} side={pos}>
        <span className={className ? `inline-flex ${className}` : 'inline-flex'}>
          {children}
        </span>
      </SimpleTooltip>
    </TooltipProvider>
  );
}
