'use client';

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react';
import { motion, AnimatePresence, useAnimate, useReducedMotion } from 'framer-motion';
import { XCircle, Info, X } from './components/Icon';
import { AnimatedCheckmark } from './components/AnimatedCheckmark';
import { CountdownRing } from './components/CountdownRing';
import { cn } from './utils';
import { Button } from './ui';

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
  duration: number;
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

function ToastItem({ t, onDismiss }: { t: Toast; onDismiss: (id: number) => void }) {
  const reduce = useReducedMotion();
  const [scope, animate] = useAnimate();

  useEffect(() => {
    if (t.variant === 'error' && !reduce) {
      animate(scope.current, { x: [0, 8, -8, 4, -4, 0] }, { duration: 0.28 });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <motion.div
      ref={scope}
      layout
      role={t.variant === 'error' ? 'alert' : 'status'}
      aria-live={t.variant === 'error' ? 'assertive' : 'polite'}
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 20, scale: 0.96 }}
      animate={reduce ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1 }}
      exit={reduce ? { opacity: 0 } : { opacity: 0, y: 8, scale: 0.96, transition: { duration: 0.15, ease: [0.4, 0, 1, 1] } }}
      transition={{ type: 'spring', stiffness: 300, damping: 24 }}
      className={cn(
        'pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg shadow-elevated border text-sm font-medium',
        t.variant === 'error'   && 'bg-status-error/10 border-status-error/30 text-status-error',
        t.variant === 'success' && 'bg-status-success/10 border-status-success/30 text-status-success',
        t.variant === 'warning' && 'bg-status-warning/10 border-status-warning/30 text-status-warning',
        t.variant === 'info'    && 'bg-surface-0 border-border text-content-primary',
      )}
    >
      <span className="relative shrink-0 flex items-center justify-center">
        {t.variant === 'success' ? (
          <AnimatedCheckmark size={16} />
        ) : t.variant === 'error' ? (
          <XCircle size={16} />
        ) : (
          <Info size={16} />
        )}
        {t.duration > 0 && (
          <CountdownRing
            duration={t.duration}
            size={22}
            className="absolute -inset-[3px]"
          />
        )}
      </span>
      <span className="flex-1" onClick={() => !t.action && onDismiss(t.id)}>{t.message}</span>
      {t.action && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={async () => {
            try { await t.action!.onAct(); } finally { onDismiss(t.id); }
          }}
          className="shrink-0 h-auto px-2 py-1 text-xs font-semibold bg-current/10 hover:bg-current/20 uppercase tracking-wide"
        >
          {t.action.label}
        </Button>
      )}
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        onClick={() => onDismiss(t.id)}
        aria-label="Dismiss"
        className="shrink-0 w-6 h-6 text-content-tertiary hover:text-content-primary"
      >
        <X size={14} />
      </Button>
    </motion.div>
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, variantOrOptions?: ToastVariant | ToastOptions) => {
    const id = ++_nextId;
    const opts: ToastOptions = typeof variantOrOptions === 'string' || variantOrOptions === undefined
      ? { variant: (variantOrOptions as ToastVariant | undefined) }
      : variantOrOptions;
    const variant: ToastVariant = opts.variant ?? 'info';
    const duration = opts.duration ?? 4000;
    setToasts(prev => [...prev, { id, message, variant, duration, action: opts.action }]);
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
            <ToastItem key={t.id} t={t} onDismiss={dismiss} />
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
