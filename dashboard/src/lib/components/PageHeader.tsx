'use client';

import { type ReactNode } from 'react';
import { BackButton } from './BackButton';
import { Breadcrumbs, type Crumb } from './Breadcrumbs';
import { cn } from '../utils';

interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  back?: boolean;
  fallbackHref?: string;
  crumbs?: Crumb[];
  actions?: ReactNode;
  className?: string;
  containerClassName?: string;
}

export function PageHeader({
  title,
  subtitle,
  back = true,
  fallbackHref = '/dashboard',
  crumbs,
  actions,
  className,
  containerClassName = 'max-w-5xl',
}: PageHeaderProps) {
  return (
    <div className={cn('border-b border-border bg-surface-0/40 px-6 pt-4 pb-4', className)}>
      <div className={cn('mx-auto', containerClassName)}>
        {crumbs && crumbs.length > 0 && (
          <Breadcrumbs crumbs={crumbs} className="mb-2" />
        )}
        <div className="flex items-start sm:items-center justify-between gap-3 flex-col sm:flex-row">
          <div className="flex items-center gap-3 min-w-0">
            {back && <BackButton fallbackHref={fallbackHref} />}
            <div className="min-w-0">
              <h1 className="text-lg font-semibold text-content-primary truncate">{title}</h1>
              {subtitle && (
                <div className="text-xs text-content-tertiary mt-0.5">{subtitle}</div>
              )}
            </div>
          </div>
          {actions && (
            <div className="flex items-center gap-2 flex-wrap">{actions}</div>
          )}
        </div>
      </div>
    </div>
  );
}
