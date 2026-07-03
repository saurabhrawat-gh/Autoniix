'use client';

import * as React from 'react';
import * as SwitchPrimitive from '@radix-ui/react-switch';
import { cn } from './cn';

export interface SwitchRowProps extends React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root> {
  label: React.ReactNode;
  description?: React.ReactNode;
  rowClassName?: string;
}

export const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root
    ref={ref}
    className={cn(
      'peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full',
      'border-2 border-transparent transition-[background-color] duration-[200ms] ease-[cubic-bezier(0.2,0,0,1)]',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40',
      'disabled:cursor-not-allowed disabled:opacity-50',
      'data-[state=checked]:bg-accent data-[state=unchecked]:bg-surface-2',
      className
    )}
    {...props}
  >
    <SwitchPrimitive.Thumb
      className={cn(
        'pointer-events-none block h-5 w-5 rounded-full bg-white shadow-lg',
        'ring-0 transition-transform duration-[120ms] ease-[cubic-bezier(0.16,1,0.3,1)]',
        'data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0'
      )}
    />
  </SwitchPrimitive.Root>
));
Switch.displayName = 'Switch';

export const SwitchRow = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  SwitchRowProps
>(({ label, description, rowClassName, id, className, ...props }, ref) => (
  <div className={cn('flex items-center justify-between gap-4 py-3', rowClassName)}>
    <div className="flex-1 min-w-0">
      <label
        htmlFor={id}
        className="block text-sm font-medium text-content-primary leading-snug cursor-pointer"
      >
        {label}
      </label>
      {description && (
        <p className="mt-0.5 text-xs text-content-tertiary">{description}</p>
      )}
    </div>
    <Switch ref={ref} id={id} className={className} {...props} />
  </div>
));
SwitchRow.displayName = 'SwitchRow';
