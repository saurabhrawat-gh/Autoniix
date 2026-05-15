'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useAppState } from './AppStateProvider';
import { Bell, CheckCircle2, XCircle, Info, AlertTriangle, Trash2 } from './Icon';
import { cn } from '../utils';
import { Popover, PopoverTrigger, PopoverContent, SimpleTooltip, TooltipProvider } from '@/lib/ui';

const VARIANT_ICON = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
} as const;
const VARIANT_COLOR = {
  success: 'text-status-success',
  error: 'text-status-error',
  warning: 'text-status-warning',
  info: 'text-content-secondary',
} as const;

function relTime(ts: number) {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function NotificationBell() {
  const { notifications, markAllNotificationsRead, clearNotifications } = useAppState();
  const [open, setOpen] = useState(false);

  const unread = notifications.filter(n => !n.read).length;

  // Mark read on open
  useEffect(() => {
    if (open && unread > 0) {
      const t = setTimeout(() => markAllNotificationsRead(), 600);
      return () => clearTimeout(t);
    }
  }, [open, unread, markAllNotificationsRead]);

  return (
    <TooltipProvider delayDuration={300}>
      <Popover open={open} onOpenChange={setOpen}>
        <SimpleTooltip content="Notifications" side="bottom">
          <PopoverTrigger
            aria-label={`Notifications${unread > 0 ? ` (${unread} unread)` : ''}`}
            className="relative w-8 h-8 flex items-center justify-center rounded-lg bg-surface-2 hover:bg-surface-3 text-content-secondary hover:text-content-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
          >
            <Bell size={14} />
            {unread > 0 && (
              <motion.span
                key={unread}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 500, damping: 25 }}
                className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-accent text-content-inverse text-[9px] font-semibold flex items-center justify-center"
              >
                {unread > 9 ? '9+' : unread}
              </motion.span>
            )}
          </PopoverTrigger>
        </SimpleTooltip>
        <PopoverContent
          align="end"
          sideOffset={8}
          className="w-[340px] max-w-[90vw] p-0 overflow-hidden"
        >
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
            <span className="text-xs font-semibold text-content-primary">Notifications</span>
            {notifications.length > 0 && (
              <button
                onClick={clearNotifications}
                className="inline-flex items-center gap-1 text-[10px] text-content-tertiary hover:text-status-error transition-colors"
                aria-label="Clear all notifications"
              >
                <Trash2 size={11} /> Clear
              </button>
            )}
          </div>
          <div className="max-h-[60vh] overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-xs text-content-tertiary">
                No notifications yet.
                <p className="mt-1 text-[10px]">Job lifecycle events will appear here.</p>
              </div>
            ) : (
              <ul className="divide-y divide-border/60">
                {notifications.map(n => {
                  const Icon = VARIANT_ICON[n.variant] || Info;
                  const body = (
                    <div className={cn('flex items-start gap-2.5 px-4 py-2.5 hover:bg-surface-1/60 transition-colors', !n.read && 'bg-accent/5')}>
                      <Icon size={14} className={cn('mt-0.5 shrink-0', VARIANT_COLOR[n.variant])} />
                      <div className="min-w-0 flex-1">
                        <div className="text-xs font-medium text-content-primary truncate">{n.title}</div>
                        {n.body && <div className="text-[11px] text-content-tertiary truncate">{n.body}</div>}
                        <div className="text-[10px] text-content-tertiary mt-0.5">{relTime(n.createdAt)}</div>
                      </div>
                    </div>
                  );
                  return (
                    <li key={n.id}>
                      {n.href ? (
                        <Link href={n.href} onClick={() => setOpen(false)} className="block">{body}</Link>
                      ) : body}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </PopoverContent>
      </Popover>
    </TooltipProvider>
  );
}
