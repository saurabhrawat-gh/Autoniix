'use client';

import { useEffect } from 'react';
import { useMotionValue, useTransform, animate, motion, useReducedMotion } from 'framer-motion';

interface AnimatedNumberProps {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
  className?: string;
}

export function AnimatedNumber({
  value,
  decimals = 2,
  prefix = '',
  suffix = '',
  duration = 0.15,
  className,
}: AnimatedNumberProps) {
  const reduce = useReducedMotion();
  const mv = useMotionValue(value);
  const display = useTransform(mv, (n) => `${prefix}${n.toFixed(decimals)}${suffix}`);

  useEffect(() => {
    if (reduce) {
      mv.set(value);
      return;
    }
    const controls = animate(mv, value, { duration, ease: [0.2, 0, 0, 1] });
    return () => controls.stop();
  }, [value, duration, reduce, mv]);

  return <motion.span className={className}>{display}</motion.span>;
}
