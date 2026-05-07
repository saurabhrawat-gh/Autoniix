'use client';

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, XCircle, Info, X } from './components/Icon';
import { cn } from './utils';

type ToastVariant = 'error' | 'success' | 'info' | 'warning';

export interface ToastAction {
  label: string;
  /** Called when the user clicks the action. The toast is dismissed afterwards. */
  onAct: () => void | Promise<void>;
}

export interface ToastOptions {
  variant?: ToastVariant;
  /** Auto-dismiss timeout in ms. Default 4000. Pass 0 to disable. */
  duration?: number;
  action?: ToastAction;
}

interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
  action?: ToastAction;
}

interface ToastContextValue {
  /** Backwards-compatible: `showToast(message, variant?)` OR `showToast(message, options)`. */
  showToast: (message: string, variantOrOptions?: ToastVariant | ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue>({ showToast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

let _nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, variantOrOptions?: ToastVariant | ToastOptions) => {
    const id = ++_nextId;
    const opts: ToastOptions = typeof variantOrOptions === 'string' || variantOrOptions === undefined
      ? { variant: (variantOrOptions as ToastVariant | undefined) }
      : variantOrOptions;
    const variant: ToastVariant = opts.variant ?? 'info';
    const duration = opts.duration ?? 4000;
    setToasts(prev => [...prev, { id, message, variant, action: opts.action }]);
    if (duration > 0) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, duration);
    }
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        className="fixed bottom-4 right-4 z-[300] flex flex-col gap-2 max-w-sm pointer-events-none"
        role="region"
        aria-label="Notifications"
      >
        <AnimatePresence initial={false}>
          {toasts.map(t => (
            <motion.div
              key={t.id}
              layout
              role={t.variant === 'error' ? 'alert' : 'status'}
              aria-live={t.variant === 'error' ? 'assertive' : 'polite'}
              initial={{ opacity: 0, x: 40, scale: 0.96 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40, scale: 0.96 }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              className={cn(
                'pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg shadow-elevated border text-sm font-medium',
                t.variant === 'error' && 'bg-status-error/10 border-status-error/30 text-status-error',
                t.variant === 'success' && 'bg-status-success/10 border-status-success/30 text-status-success',
                t.variant === 'warning' && 'bg-status-warning/10 border-status-warning/30 text-status-warning',
                t.variant === 'info' && 'bg-surface-0 border-border text-content-primary',
              )}
            >
              <span className="shrink-0">
                {t.variant === 'error' ? <XCircle size={16} /> : t.variant === 'success' ? <CheckCircle2 size={16} /> : <Info size={16} />}
              </span>
              <span className="flex-1" onClick={() => !t.action && dismiss(t.id)}>{t.message}</span>
              {t.action && (
                <button
                  onClick={async () => {
                    try { await t.action!.onAct(); } finally { dismiss(t.id); }
                  }}
                  className="shrink-0 px-2 py-1 rounded-md text-xs font-semibold bg-current/10 hover:bg-current/20 transition-colors uppercase tracking-wide"
                >
                  {t.action.label}
                </button>
              )}
              <button
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss"
                className="shrink-0 text-content-tertiary hover:text-content-primary"
              >
                <X size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
