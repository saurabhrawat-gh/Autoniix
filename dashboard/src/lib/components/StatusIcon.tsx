'use client';

import { Check, X, Square, Ban, RotateCw, CircleDot, Hourglass, Circle } from './Icon';
import { statusIconName, statusColor, cn as _cn } from '../utils';
import { cn } from '../utils';

const ICONS = {
  'check': Check,
  'x': X,
  'square': Square,
  'ban': Ban,
  'rotate-cw': RotateCw,
  'circle-dot': CircleDot,
  'hourglass': Hourglass,
  'circle': Circle,
} as const;

interface Props {
  status: string;
  size?: number;
  /** Apply the matching status colour class. */
  colored?: boolean;
  className?: string;
}

/** Lucide-rendered status indicator. Falls back to the existing colour helper. */
export function StatusIcon({ status, size = 14, colored = true, className }: Props) {
  const name = statusIconName(status);
  const Cmp = ICONS[name];
  return <Cmp size={size} className={cn(colored && statusColor(status), className)} />;
}
