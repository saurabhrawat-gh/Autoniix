'use client';

import Link from 'next/link';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../utils';
import {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogTitle,
} from '@/lib/ui';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';

export interface DrawerItem {
  href: string;
  label: string;
  icon: LucideIcon;
  active?: boolean;
}

interface Props {
  open: boolean;
  onClose: () => void;
  items: DrawerItem[];
  footer?: React.ReactNode;
}

export function MobileDrawer({ open, onClose, items, footer }: Props) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogPortal>
        <DialogOverlay className="md:hidden z-[150] bg-black/50" />
        <DialogPrimitive.Content
          aria-label="Navigation"
          className={cn(
            'fixed top-0 left-0 bottom-0 z-[160] w-[80vw] max-w-[300px]',
            'bg-surface-0 border-r border-border md:hidden flex flex-col',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left',
            'duration-200 focus:outline-none'
          )}
        >
          <VisuallyHidden>
            <DialogTitle>Navigation menu</DialogTitle>
          </VisuallyHidden>
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <span className="text-sm font-semibold text-content-primary">Menu</span>
            <DialogPrimitive.Close
              aria-label="Close menu"
              className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-surface-2 text-content-secondary"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </DialogPrimitive.Close>
          </div>
          <nav className="flex-1 overflow-y-auto p-2">
            {items.map(({ href, label, icon: Icon, active }) => (
              <Link
                key={href}
                href={href}
                onClick={onClose}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  active
                    ? 'bg-accent/10 text-accent'
                    : 'text-content-secondary hover:text-content-primary hover:bg-surface-2',
                )}
              >
                <Icon size={16} />
                <span>{label}</span>
              </Link>
            ))}
          </nav>
          {footer && <div className="border-t border-border p-3">{footer}</div>}
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  );
}
