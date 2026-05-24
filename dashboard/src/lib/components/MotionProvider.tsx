'use client';

import { MotionConfig } from 'framer-motion';
import { type ReactNode } from 'react';
import { ease, dur } from '../motion';

export function MotionProvider({ children }: { children: ReactNode }) {
  return (
    <MotionConfig
      reducedMotion="user"
      transition={{ duration: dur.base, ease: ease.standard }}
    >
      {children}
    </MotionConfig>
  );
}
