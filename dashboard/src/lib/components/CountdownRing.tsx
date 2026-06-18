'use client';

import { motion, useReducedMotion } from 'framer-motion';

const RADIUS = 9;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS; // ≈ 56.55

interface CountdownRingProps {
  /** Countdown duration in ms */
  duration: number;
  size?: number;
  className?: string;
}

export function CountdownRing({ duration, size = 22, className }: CountdownRingProps) {
  const reduce = useReducedMotion();
  if (reduce || duration <= 0) return null;

  const cx = size / 2;
  const cy = size / 2;

  return (
    <svg
      width={size}
      height={size}
      className={className}
      style={{ transform: 'rotate(-90deg)' }}
      aria-hidden="true"
    >
      {/* track */}
      <circle
        cx={cx}
        cy={cy}
        r={RADIUS}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        opacity={0.2}
      />
      {/* depleting arc */}
      <motion.circle
        cx={cx}
        cy={cy}
        r={RADIUS}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeDasharray={CIRCUMFERENCE}
        initial={{ strokeDashoffset: 0 }}
        animate={{ strokeDashoffset: CIRCUMFERENCE }}
        transition={{ duration: duration / 1000, ease: 'linear' }}
      />
    </svg>
  );
}
