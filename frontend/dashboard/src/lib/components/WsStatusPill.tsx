'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { useAppState } from './AppStateProvider';
import { Tip } from './Tooltip';
import { cn } from '../utils';

const LABEL: Record<string, string> = {
  live:       'Connected',
  connecting: 'Connecting',
  offline:    'Offline',
};

const TIP: Record<string, string> = {
  live:       'Realtime updates active',
  connecting: 'Establishing realtime connection…',
  offline:    'Realtime offline — falling back to polling',
};

const RECONNECTING = 'Reconnecting...';

export function WsStatusPill() {
  const { wsStatus } = useAppState();
  const reduce = useReducedMotion();
  const prevStatus = useRef(wsStatus);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (prevStatus.current !== 'live' && wsStatus === 'live') {
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 800);
      return () => clearTimeout(t);
    }
    prevStatus.current = wsStatus;
  }, [wsStatus]);

  const dotColor =
    wsStatus === 'live'       ? 'bg-status-success'
    : wsStatus === 'connecting' ? 'bg-status-warning'
    : 'bg-status-error';

  const isReconnecting = wsStatus === 'connecting' || wsStatus === 'offline';

  return (
    <Tip text={`${LABEL[wsStatus]} — ${TIP[wsStatus]}`} pos="bottom">
      <span
        className={cn(
          'inline-flex items-center gap-1.5 h-7 px-2 rounded-full bg-surface-1 border border-border text-[10px] font-medium transition-colors',
          flash ? 'text-status-success border-status-success/30' : 'text-content-secondary',
        )}
        aria-live="polite"
        aria-label={`Realtime status: ${wsStatus}`}
      >
        {/* dot */}
        <span className="relative flex h-2 w-2 shrink-0">
          {wsStatus === 'live' && (
            <motion.span
              className={cn('absolute inline-flex h-full w-full rounded-full opacity-60', dotColor)}
              animate={{ scale: [1, 1.8, 1], opacity: [0.6, 0, 0.6] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeOut' }}
            />
          )}
          {isReconnecting && !reduce && (
            <motion.span
              className={cn('absolute inline-flex h-full w-full rounded-full', dotColor)}
              animate={{ scale: [1, 1.6, 1], opacity: [1, 0.3, 1] }}
              transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
            />
          )}
          <span className={cn('relative inline-flex rounded-full h-2 w-2', dotColor)} />
        </span>

        {/* label */}
        <span className="hidden md:inline overflow-hidden">
          <AnimatePresence mode="wait" initial={false}>
            {flash ? (
              <motion.span
                key="connected-flash"
                className="text-status-success font-semibold"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                Connected
              </motion.span>
            ) : isReconnecting ? (
              <motion.span
                key="reconnecting"
                className="inline-flex"
                initial="hidden"
                animate="visible"
                exit={{ opacity: 0 }}
              >
                {reduce ? (
                  RECONNECTING
                ) : (
                  RECONNECTING.split('').map((ch, i) => (
                    <motion.span
                      key={i}
                      variants={{
                        hidden: { opacity: 0, y: 4 },
                        visible: { opacity: 1, y: 0 },
                      }}
                      transition={{ delay: i * 0.04, duration: 0.15 }}
                    >
                      {ch}
                    </motion.span>
                  ))
                )}
              </motion.span>
            ) : (
              <motion.span
                key="live"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                Connected
              </motion.span>
            )}
          </AnimatePresence>
        </span>
      </span>
    </Tip>
  );
}
