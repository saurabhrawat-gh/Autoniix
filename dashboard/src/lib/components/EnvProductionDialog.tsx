'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { ShieldAlert, X } from './Icon';

interface EnvProductionDialogProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  switching?: boolean;
}

export function EnvProductionDialog({ open, onCancel, onConfirm, switching }: EnvProductionDialogProps) {
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
          <motion.div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onCancel} />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="relative w-full max-w-md rounded-xl bg-surface-0 border border-border shadow-elevated"
          >
            <div className="flex items-start justify-between px-5 py-4 border-b border-border">
              <div className="flex items-center gap-2">
                <ShieldAlert size={18} className="text-status-error" />
                <h2 className="text-sm font-semibold text-content-primary">Switch to Production?</h2>
              </div>
              <button
                onClick={onCancel}
                aria-label="Cancel"
                className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-surface-2 text-content-tertiary hover:text-content-primary transition-colors"
              >
                <X size={14} />
              </button>
            </div>
            <div className="px-5 py-4 space-y-3 text-sm">
              <p className="text-content-secondary">
                Production mode uses <span className="font-semibold text-content-primary">paid APIs</span> and
                <span className="font-semibold text-content-primary"> uploads to YouTube</span>.
              </p>
              <ul className="text-xs text-content-tertiary list-disc list-inside space-y-0.5">
                <li>Each video may cost $0.12–$0.35.</li>
                <li>Daily budget &amp; per-day limits apply.</li>
                <li>Generated videos are real and visible.</li>
              </ul>
            </div>
            <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border bg-surface-1/40">
              <button onClick={onCancel} className="btn-ghost !py-1.5 !text-xs">Cancel</button>
              <button
                onClick={onConfirm}
                disabled={switching}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-status-error text-white hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {switching ? 'Switching…' : 'Switch to Production'}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
