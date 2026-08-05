'use client';

import Link from 'next/link';
import { type ReactNode } from 'react';
import { motion } from 'framer-motion';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../utils';
import { Button } from '@/lib/ui';

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
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.26, ease: [0.12, 0, 0.1, 1] }}
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
            <Button asChild size="sm">
              <Link href={cta.href}>{cta.label}</Link>
            </Button>
          ) : (
            <Button size="sm" onClick={cta.onClick}>{cta.label}</Button>
          )}
        </div>
      )}
    </motion.div>
  );
}
