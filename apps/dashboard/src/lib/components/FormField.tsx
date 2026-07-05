'use client';

import type { FieldError } from 'react-hook-form';
import { cn } from '@/lib/utils';
import { Label } from '@/lib/ui';

interface FormFieldProps {
  id: string;
  label: string;
  required?: boolean;
  error?: FieldError;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}

export function FormField({ id, label, required, error, hint, children, className }: FormFieldProps) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <Label htmlFor={id} required={required}>{label}</Label>
      {children}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-xs text-status-error">
          {error.message}
        </p>
      ) : hint ? (
        <p className="text-xs text-content-tertiary">{hint}</p>
      ) : null}
    </div>
  );
}
