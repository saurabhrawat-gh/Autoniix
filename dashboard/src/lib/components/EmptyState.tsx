'use client';

import Link from 'next/link';
import { type ReactNode } from 'react';
import { motion } from 'framer-motion';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../utils';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: ReactNode;
  body?: ReactNode;
  cta?: { label: string; href?: string; onClick?: () => void };
  className?: string;
}

export function EmptyState({ icon: Icon, title, body, cta, className }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={cn(
        'flex flex-col items-center justify-center text-center py-16 px-6 rounded-xl',
        'border border-dashed border-border bg-surface-1/40',
        className,
      )}
    >
      {Icon && (
        <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mb-4">
          <Icon size={22} className="text-accent" />
        </div>
      )}
      <h3 className="text-base font-semibold text-content-primary">{title}</h3>
      {body && <p className="mt-1.5 text-sm text-content-tertiary max-w-md">{body}</p>}
      {cta && (
        <div className="mt-5">
          {cta.href ? (
            <Link href={cta.href} className="btn-primary !py-2 !text-xs">
              {cta.label}
            </Link>
          ) : (
            <button onClick={cta.onClick} className="btn-primary !py-2 !text-xs">
              {cta.label}
            </button>
          )}
        </div>
      )}
    </motion.div>
  );
}
