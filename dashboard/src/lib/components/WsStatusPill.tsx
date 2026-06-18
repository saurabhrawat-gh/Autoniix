'use client';

import { motion } from 'framer-motion';
import { useAppState } from './AppStateProvider';
import { Tip } from './Tooltip';
import { cn } from '../utils';

const LABEL: Record<string, string> = {
  live: 'Connected',
  connecting: 'Connecting',
  offline: 'Offline',
};
const TIP: Record<string, string> = {
  live: 'Realtime updates active',
  connecting: 'Establishing realtime connection…',
  offline: 'Realtime offline — falling back to polling',
};

export function WsStatusPill() {
  const { wsStatus } = useAppState();
  const color =
    wsStatus === 'live' ? 'bg-status-success'
      : wsStatus === 'connecting' ? 'bg-status-warning'
      : 'bg-status-error';
  // Dot-only indicator. Tooltip carries the verbose label.
  return (
    <Tip text={`${LABEL[wsStatus]} — ${TIP[wsStatus]}`} pos="bottom">
      <span
        className="inline-flex items-center justify-center w-7 h-7"
        aria-live="polite"
        aria-label={`Realtime status: ${LABEL[wsStatus]}`}
      >
        <span className="relative flex h-2 w-2">
          {wsStatus === 'live' && (
            <motion.span
              className={cn('absolute inline-flex h-full w-full rounded-full opacity-60', color)}
              animate={{ scale: [1, 1.8, 1], opacity: [0.6, 0, 0.6] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeOut' }}
            />
          )}
          <span className={cn('relative inline-flex rounded-full h-2 w-2', color)} />
        </span>
      </span>
    </Tip>
  );
}
