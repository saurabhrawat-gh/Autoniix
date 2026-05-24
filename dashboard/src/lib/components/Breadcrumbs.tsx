'use client';

import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
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
      <AnimatePresence initial={false} mode="popLayout">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <motion.span
              key={c.href ?? c.label}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -6 }}
              transition={{ duration: 0.12, delay: i * 0.03, ease: [0.12, 0, 0.1, 1] }}
              className="inline-flex items-center"
            >
              {c.href && !last ? (
                <Link
                  href={c.href}
                  className="hover:text-content-primary transition-colors duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)]"
                >
                  {c.label}
                </Link>
              ) : (
                <span className={cn(last && 'text-content-secondary font-medium')}>{c.label}</span>
              )}
              {!last && <ChevronRight size={12} className="mx-1.5 opacity-60" />}
            </motion.span>
          );
        })}
      </AnimatePresence>
    </nav>
  );
}
