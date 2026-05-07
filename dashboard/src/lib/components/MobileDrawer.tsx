'use client';

import Link from 'next/link';
import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../utils';
import { X } from './Icon';

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
  // Lock body scroll when open
  useEffect(() => {
    if (!open) return;
    const orig = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = orig; };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="drawer-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-[150] bg-black/50 backdrop-blur-sm md:hidden"
            onClick={onClose}
          />
          <motion.aside
            key="drawer-panel"
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="fixed top-0 left-0 bottom-0 z-[160] w-[80vw] max-w-[300px] bg-surface-0 border-r border-border md:hidden flex flex-col"
            role="dialog"
            aria-label="Navigation"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <span className="text-sm font-semibold text-content-primary">Menu</span>
              <button
                onClick={onClose}
                aria-label="Close menu"
                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-surface-2 text-content-secondary"
              >
                <X size={16} />
              </button>
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
            {footer && (
              <div className="border-t border-border p-3">{footer}</div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
