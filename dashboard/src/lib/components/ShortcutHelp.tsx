'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { X, Keyboard } from './Icon';
import { cn } from '../utils';

interface ShortcutHelpProps {
  open: boolean;
  onClose: () => void;
}

const SHORTCUTS: Array<{ keys: string[]; label: string }> = [
  { keys: ['g', 'd'], label: 'Go to Dashboard' },
  { keys: ['g', 'p'], label: 'Go to Progress' },
  { keys: ['g', 's'], label: 'Go to Settings' },
  { keys: ['g', 'l'], label: 'Go to Library' },
  { keys: ['g', 'q'], label: 'Go to Render Queue' },
  { keys: ['g', 'e'], label: 'Go to Experiments' },
  { keys: ['n'], label: 'New Channel' },
  { keys: ['?'], label: 'Show this help' },
  { keys: ['Esc'], label: 'Close dialog / help' },
];

export function ShortcutHelp({ open, onClose }: ShortcutHelpProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[200] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
        >
          <motion.div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="relative w-full max-w-md rounded-xl bg-surface-0 border border-border shadow-elevated"
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div className="flex items-center gap-2">
                <Keyboard size={16} className="text-accent" />
                <h2 className="text-sm font-semibold text-content-primary">Keyboard Shortcuts</h2>
              </div>
              <button
                onClick={onClose}
                aria-label="Close"
                className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-surface-2 text-content-tertiary hover:text-content-primary transition-colors"
              >
                <X size={14} />
              </button>
            </div>
            <ul className="px-5 py-4 space-y-2.5">
              {SHORTCUTS.map((s, i) => (
                <li key={i} className="flex items-center justify-between text-sm">
                  <span className="text-content-secondary">{s.label}</span>
                  <span className="flex items-center gap-1">
                    {s.keys.map((k, j) => (
                      <kbd
                        key={j}
                        className={cn(
                          'inline-flex items-center justify-center min-w-[1.5rem] h-6 px-1.5 rounded',
                          'border border-border bg-surface-2 text-[11px] font-mono text-content-primary',
                        )}
                      >
                        {k}
                      </kbd>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
            <div className="px-5 py-3 border-t border-border bg-surface-1/40 text-[11px] text-content-tertiary">
              Shortcuts are disabled while typing in input fields.
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
