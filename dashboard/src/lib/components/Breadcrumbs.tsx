'use client';

import Link from 'next/link';
import { Fragment } from 'react';
import { ChevronRight } from './Icon';
import { cn } from '../utils';

export interface Crumb {
  label: string;
  href?: string;
}

export function Breadcrumbs({ crumbs, className }: { crumbs: Crumb[]; className?: string }) {
  if (!crumbs.length) return null;
  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center text-xs text-content-tertiary', className)}>
      {crumbs.map((c, i) => {
        const last = i === crumbs.length - 1;
        return (
          <Fragment key={i}>
            {c.href && !last ? (
              <Link href={c.href} className="hover:text-content-primary transition-colors">
                {c.label}
              </Link>
            ) : (
              <span className={cn(last && 'text-content-secondary font-medium')}>{c.label}</span>
            )}
            {!last && <ChevronRight size={12} className="mx-1.5 opacity-60" />}
          </Fragment>
        );
      })}
    </nav>
  );
}
