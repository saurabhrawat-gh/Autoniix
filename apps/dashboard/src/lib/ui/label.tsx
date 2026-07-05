'use client';

import * as React from 'react';
import * as LabelPrimitive from '@radix-ui/react-label';
import { cn } from './cn';

export const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root> & { required?: boolean }
>(({ className, required, children, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn(
      'text-sm font-medium text-content-secondary leading-none',
      'peer-disabled:cursor-not-allowed peer-disabled:opacity-50',
      className
    )}
    {...props}
  >
    {children}
    {required && <span className="text-status-error ml-0.5">*</span>}
  </LabelPrimitive.Root>
));
Label.displayName = 'Label';
