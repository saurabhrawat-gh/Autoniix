'use client';

import Link from 'next/link';
import type { LucideIcon } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../utils';
import {
  Dialog,
  DialogPortal,
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
        <AnimatePresence>
          {open && (
            <>
              {/* Backdrop */}
              <motion.div
                key="drawer-backdrop"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.16, ease: [0.2, 0, 0, 1] }}
                className="fixed inset-0 z-[150] bg-black/50 md:hidden"
                onClick={onClose}
                aria-hidden="true"
              />
              {/* Panel */}
              <DialogPrimitive.Content
                forceMount
                aria-label="Navigation"
                className="fixed top-0 left-0 bottom-0 z-[160] w-[80vw] max-w-[300px] md:hidden focus:outline-none"
              >
                <VisuallyHidden>
                  <DialogTitle>Navigation menu</DialogTitle>
                </VisuallyHidden>
                <motion.div
                  key="drawer-panel"
                  initial={{ x: '-100%' }}
                  animate={{ x: 0 }}
                  exit={{ x: '-100%' }}
                  transition={{ duration: 0.26, ease: [0.12, 0, 0.1, 1] }}
                  className="h-full bg-surface-0 border-r border-border flex flex-col"
                >
                  <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                    <span className="text-sm font-semibold text-content-primary">Menu</span>
                    <DialogPrimitive.Close
                      aria-label="Close menu"
                      className={cn(
                        'w-8 h-8 flex items-center justify-center rounded-lg',
                        'text-content-secondary hover:text-content-primary hover:bg-surface-2',
                        'transition-colors duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)]',
                      )}
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
                          'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium',
                          'transition-colors duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)]',
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
                </motion.div>
              </DialogPrimitive.Content>
            </>
          )}
        </AnimatePresence>
      </DialogPortal>
    </Dialog>
  );
}
