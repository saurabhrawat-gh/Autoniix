'use client';

import { useRouter } from 'next/navigation';
import { ArrowLeft } from './Icon';
import { cn } from '../utils';

interface BackButtonProps {
  fallbackHref?: string;
  className?: string;
  label?: string;
}

export function BackButton({ fallbackHref = '/dashboard', className, label = 'Back' }: BackButtonProps) {
  const router = useRouter();

  function go() {
    if (typeof window !== 'undefined' && window.history.length > 1) {
      router.back();
    } else {
      router.push(fallbackHref);
    }
  }

  return (
    <button
      onClick={go}
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 h-8 px-2.5 rounded-lg',
        'bg-surface-2 hover:bg-surface-3 text-content-secondary hover:text-content-primary',
        'transition-colors text-xs font-medium',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40',
        className,
      )}
    >
      <ArrowLeft size={14} />
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}
