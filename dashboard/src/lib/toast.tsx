'use client';

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { cn } from './utils';

type ToastVariant = 'error' | 'success' | 'info';

interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  showToast: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue>({ showToast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

let _nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, variant: ToastVariant = 'info') => {
    const id = ++_nextId;
    setToasts(prev => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {toasts.length > 0 && (
        <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
          {toasts.map(t => (
            <div
              key={t.id}
              onClick={() => dismiss(t.id)}
              className={cn(
                'px-4 py-3 rounded-lg shadow-elevated border text-sm font-medium cursor-pointer',
                'animate-in slide-in-from-right-full fade-in duration-200',
                t.variant === 'error' && 'bg-status-error/10 border-status-error/30 text-status-error',
                t.variant === 'success' && 'bg-status-success/10 border-status-success/30 text-status-success',
                t.variant === 'info' && 'bg-surface-0 border-border text-content-primary',
              )}
            >
              <span className="mr-2">
                {t.variant === 'error' ? '✕' : t.variant === 'success' ? '✓' : 'ℹ'}
              </span>
              {t.message}
            </div>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}
