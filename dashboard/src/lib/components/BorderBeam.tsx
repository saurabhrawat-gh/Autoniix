'use client';

import { useReducedMotion } from 'framer-motion';
import { cn } from '../utils';

interface BorderBeamProps {
  duration?: number;
  size?: number;
  colorFrom?: string;
  colorTo?: string;
  className?: string;
  delay?: number;
}

export function BorderBeam({
  duration = 3,
  size = 50,
  colorFrom = 'rgb(var(--accent) / 0.85)',
  colorTo = 'transparent',
  className,
  delay = 0,
}: BorderBeamProps) {
  const reduce = useReducedMotion();

  if (reduce) {
    return (
      <span
        aria-hidden="true"
        className={cn(
          'pointer-events-none absolute inset-0 rounded-[inherit] border border-accent/30',
          className,
        )}
      />
    );
  }

  return (
    <span
      aria-hidden="true"
      className={cn('pointer-events-none absolute inset-0 rounded-[inherit]', className)}
      style={{
        padding: '1px',
        WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
        WebkitMaskComposite: 'xor',
        mask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
        maskComposite: 'exclude',
      }}
    >
      <span
        className="block h-full w-full rounded-[inherit]"
        style={{
          background: `conic-gradient(from 0deg at 50% 50%, transparent 0deg, ${colorFrom} ${size}deg, ${colorTo} ${size * 2}deg, transparent 360deg)`,
          animationName: 'border-beam-spin',
          animationDuration: `${duration}s`,
          animationTimingFunction: 'linear',
          animationIterationCount: 'infinite',
          animationDelay: `${delay}s`,
        }}
      />
    </span>
  );
}
