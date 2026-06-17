'use client';

import { useEffect } from 'react';
import { useMotionValue, useTransform, useSpring, motion, useReducedMotion } from 'framer-motion';

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
  duration = 0.15, // kept for API compat; spring physics are used instead
  className,
}: AnimatedNumberProps) {
  const reduce = useReducedMotion();
  const mv = useMotionValue(value);
  const springMv = useSpring(mv, { stiffness: 80, damping: 20 });
  const display = useTransform(
    reduce ? mv : springMv,
    (n) => `${prefix}${n.toFixed(decimals)}${suffix}`,
  );

  useEffect(() => {
    mv.set(value);
  }, [value, mv]);

  return <motion.span className={className}>{display}</motion.span>;
}
