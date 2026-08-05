'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { AlertTriangle, RotateCw, Home } from '@/lib/components/Icon';
import { Button } from '@/lib/ui';

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error('[dashboard error]', error);
  }, [error]);

  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="max-w-md w-full text-center space-y-4"
      >
        <div className="mx-auto w-12 h-12 rounded-full bg-status-error/10 flex items-center justify-center text-status-error">
          <AlertTriangle size={22} />
        </div>
        <div>
          <h1 className="text-base font-semibold text-content-primary">Something went wrong</h1>
          <p className="text-xs text-content-tertiary mt-1">
            {error?.message || 'An unexpected error occurred while rendering this page.'}
          </p>
          {error?.digest && (
            <p className="text-[10px] text-content-tertiary mt-2 font-mono">digest: {error.digest}</p>
          )}
        </div>
        <div className="flex items-center justify-center gap-2 pt-2">
          <Button onClick={() => reset()} size="sm" leftIcon={<RotateCw size={14} />}>
            Try again
          </Button>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg text-xs font-medium border border-border bg-surface-1 hover:bg-surface-2 transition-colors"
          >
            <Home size={14} /> Dashboard
          </Link>
        </div>
      </motion.div>
    </div>
  );
}
