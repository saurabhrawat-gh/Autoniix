'use client';

import * as React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from './cn';

export interface KpiCardProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: React.ReactNode;
  label: string;
  value: React.ReactNode;
  delta?: number;
  deltaLabel?: string;
}

export function KpiCard({ icon, label, value, delta, deltaLabel, className, ...props }: KpiCardProps) {
  const trend = delta == null ? null : delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat';

  return (
    <div
      className={cn(
        'bg-surface-0 border border-border rounded-xl p-4 flex flex-col gap-3',
        className
      )}
      {...props}
    >
      {icon && (
        <div className="text-content-tertiary">{icon}</div>
      )}
      <div className="flex items-end justify-between gap-2">
        <div>
          <p className="text-metric font-bold text-content-primary leading-none">{value}</p>
          <p className="mt-1 text-body-sm text-content-secondary">{label}</p>
        </div>
        {trend != null && (
          <span
            className={cn(
              'inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full',
              trend === 'up'   && 'bg-status-success/10 text-status-success',
              trend === 'down' && 'bg-status-error/10 text-status-error',
              trend === 'flat' && 'bg-surface-2 text-content-muted',
            )}
          >
            {trend === 'up'   && <TrendingUp size={11} />}
            {trend === 'down' && <TrendingDown size={11} />}
            {trend === 'flat' && <Minus size={11} />}
            {deltaLabel ?? `${Math.abs(delta!)}%`}
          </span>
        )}
      </div>
    </div>
  );
}
