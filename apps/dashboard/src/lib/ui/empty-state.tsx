'use client';

import * as React from 'react';
import { cn } from './cn';

export interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: React.ReactNode;
  heading: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, heading, description, action, className, ...props }: EmptyStateProps) {
  return (
    <div
      className={cn('flex flex-col items-center justify-center text-center py-16 px-6 gap-4', className)}
      {...props}
    >
      {icon && (
        <div className="text-content-disabled mb-1">{icon}</div>
      )}
      <div className="space-y-1.5 max-w-xs">
        <p className="text-h4 font-semibold text-content-primary">{heading}</p>
        {description && (
          <p className="text-body-sm text-content-secondary">{description}</p>
        )}
      </div>
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
