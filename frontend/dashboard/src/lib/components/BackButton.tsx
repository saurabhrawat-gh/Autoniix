'use client';

import { useRouter } from 'next/navigation';
import { ArrowLeft } from './Icon';
import { cn } from '../utils';
import { Button } from '../ui';

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
    <Button
      type="button"
      variant="secondary"
      size="sm"
      onClick={go}
      aria-label={label}
      title={label}
      leftIcon={<ArrowLeft size={14} />}
      className={cn('h-8 px-2.5 text-xs font-medium text-content-secondary hover:text-content-primary', className)}
    >
      <span className="hidden sm:inline">{label}</span>
    </Button>
  );
}
