'use client';

import { motion } from 'framer-motion';

interface AnimatedCheckmarkProps {
  size?: number;
  className?: string;
}

export function AnimatedCheckmark({ size = 16, className }: AnimatedCheckmarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <motion.path
        d="M2.5 8.5L6 12L13.5 4"
        stroke="currentColor"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.25, ease: 'easeOut' }}
      />
    </svg>
  );
}
