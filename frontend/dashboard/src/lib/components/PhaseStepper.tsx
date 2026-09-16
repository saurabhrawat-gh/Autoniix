'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { Check, X, Pause as PauseIcon } from './Icon';
import { cn } from '../utils';
import { PHASE_ORDER, PHASE_LABELS } from '../utils';
import { ease, dur } from '../motion';

function ScrambleText({ text, active }: { text: string; active: boolean }) {
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(text);
  const prevActiveRef = useRef(false);

  useEffect(() => {
    if (!active) {
      prevActiveRef.current = false;
      setDisplay(text);
      return;
    }
    if (prevActiveRef.current) return;
    prevActiveRef.current = true;

    if (reduce) { setDisplay(text); return; }

    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789·-';
    let frame = 0;
    const total = 8;
    const id = setInterval(() => {
      frame++;
      if (frame >= total) { setDisplay(text); clearInterval(id); return; }
      setDisplay(
        text.split('').map((c, i) =>
          i < Math.floor((frame / total) * text.length)
            ? c
            : chars[Math.floor(Math.random() * chars.length)]
        ).join(''),
      );
    }, 35);
    return () => clearInterval(id);
  }, [active, text, reduce]);

  return <>{display}</>;
}

interface PhaseStepperProps {
  currentPhase: string | null;
  isFailed?: boolean;
  isStopped?: boolean;
  isPaused?: boolean;
  phaseStatus?: string;
  jobId: string;
}

export function PhaseStepper({
  currentPhase,
  isFailed,
  isStopped,
  isPaused,
  phaseStatus,
  jobId,
}: PhaseStepperProps) {
  const currentIdx = currentPhase ? PHASE_ORDER.indexOf(currentPhase) : -1;
  const N = PHASE_ORDER.length;
  const insetPct = 50 / N;
  const fillFrac =
    currentIdx < 0
      ? 0
      : Math.min(
          1,
          (currentIdx + (isFailed || isStopped ? 0 : 0.5)) / Math.max(1, N - 1),
        );
  const fillWidthExpr = `calc((100% - ${insetPct * 2}%) * ${fillFrac})`;

  return (
    <div className="relative mt-4">
      {/* Background track — endpoints align with first/last dot centers */}
      <div
        className="absolute top-2 h-0.5 bg-surface-3 rounded-full"
        style={{ left: `${insetPct}%`, right: `${insetPct}%` }}
      />
      {/* Animated fill */}
      <motion.div
        className={cn(
          'absolute top-2 h-0.5 rounded-full',
          isFailed ? 'bg-status-error' : isStopped ? 'bg-status-warning' : 'bg-status-success',
        )}
        style={{ left: `${insetPct}%` }}
        initial={false}
        animate={{ width: fillWidthExpr }}
        transition={{ duration: dur.base, ease: ease.standard }}
      />

      <div className="relative flex items-start" role="group" aria-label="Pipeline phases">
        {PHASE_ORDER.map((phase, idx) => {
          const isCurrent = currentPhase === phase;
          const isCompleted = currentIdx > idx;
          const isPhaseFailed = isCurrent && (phaseStatus === 'failed' || isFailed);
          const isPhasePaused = isCurrent && isPaused;

          return (
            <div key={phase} className="flex-1 flex flex-col items-center">
              <div className="relative flex items-center justify-center">
                {isCurrent && !isPhaseFailed && !isPhasePaused && (
                  <>
                    <span className="radar-ring-1 absolute w-4 h-4 rounded-full bg-accent pointer-events-none" />
                    <span className="radar-ring-2 absolute w-4 h-4 rounded-full bg-accent pointer-events-none" />
                  </>
                )}
              <motion.div
                layoutId={isCurrent ? `phase-active-${jobId}` : undefined}
                className={cn(
                  'w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold shrink-0 z-10',
                  isPhaseFailed
                    ? 'bg-status-error text-white'
                    : isPhasePaused
                    ? 'bg-status-warning text-white'
                    : isCompleted
                    ? 'bg-status-success text-white'
                    : isCurrent
                    ? 'bg-accent text-white ring-2 ring-accent/30'
                    : 'bg-surface-3 text-content-tertiary',
                )}
                animate={
                  isCurrent && !isPhaseFailed && !isPhasePaused
                    ? { scale: [1, 1.12, 1] }
                    : { scale: 1 }
                }
                transition={
                  isCurrent && !isPhaseFailed && !isPhasePaused
                    ? { duration: 1.6, repeat: Infinity, ease: 'easeInOut' }
                    : { duration: 0.2 }
                }
              >
                <AnimatePresence mode="wait" initial={false}>
                  {isPhaseFailed ? (
                    <motion.span key="x" initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.8, opacity: 0 }} transition={{ duration: dur.fast, ease: ease.emphasis }}>
                      <X size={10} strokeWidth={3} />
                    </motion.span>
                  ) : isPhasePaused ? (
                    <motion.span key="pause" initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.8, opacity: 0 }} transition={{ duration: dur.fast, ease: ease.emphasis }}>
                      <PauseIcon size={8} strokeWidth={3} />
                    </motion.span>
                  ) : isCompleted ? (
                    <motion.span key="check" initial={{ scale: 0.96, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.96, opacity: 0 }} transition={{ duration: 0.14, ease: ease.emphasis }}>
                      <Check size={10} strokeWidth={3} />
                    </motion.span>
                  ) : null}
                </AnimatePresence>
              </motion.div>
              </div>
              <span
                aria-current={isCurrent ? 'step' : undefined}
                aria-live={isCurrent ? 'polite' : undefined}
                className={cn(
                  'text-[8px] mt-1 font-medium text-center leading-tight',
                  isPhaseFailed
                    ? 'text-status-error'
                    : isPhasePaused
                    ? 'text-status-warning'
                    : isCurrent
                    ? 'text-accent'
                    : isCompleted
                    ? 'text-status-success'
                    : 'text-content-tertiary/50',
                )}
              >
                <ScrambleText text={PHASE_LABELS[phase]} active={isCurrent} />
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
