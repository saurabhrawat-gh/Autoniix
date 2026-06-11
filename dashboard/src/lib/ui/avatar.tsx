'use client';

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from './cn';

const avatarVariants = cva(
  'relative inline-flex items-center justify-center shrink-0 rounded-full overflow-hidden bg-surface-2',
  {
    variants: {
      size: {
        sm: 'h-6 w-6 text-[9px] font-semibold',
        md: 'h-8 w-8 text-[11px] font-semibold',
        lg: 'h-10 w-10 text-sm font-semibold',
      },
    },
    defaultVariants: { size: 'md' },
  }
);

export interface AvatarProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof avatarVariants> {
  src?: string;
  alt?: string;
  fallback?: string;
}

function getInitials(name?: string): string {
  if (!name) return '?';
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
}

export const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, size, src, alt, fallback, children, ...props }, ref) => (
    <div ref={ref} className={cn(avatarVariants({ size }), className)} {...props}>
      {src ? (
        <img
          src={src}
          alt={alt ?? fallback ?? ''}
          className="h-full w-full object-cover"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = 'none';
          }}
        />
      ) : children ? (
        children
      ) : (
        <span className="text-content-secondary select-none">
          {getInitials(fallback)}
        </span>
      )}
    </div>
  )
);
Avatar.displayName = 'Avatar';

export { avatarVariants };
