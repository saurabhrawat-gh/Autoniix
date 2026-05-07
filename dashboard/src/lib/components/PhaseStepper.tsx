'use client';

import { motion } from 'framer-motion';
import { Check, X, Pause as PauseIcon } from './Icon';
import { cn } from '../utils';
import { PHASE_ORDER, PHASE_LABELS } from '../utils';

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
  // Each phase occupies an equal flex-1 column; the dot is centered inside it.
  // Aligning the track endpoints to dot centers means insetting both sides by
  // half a column width — so the line truly *touches* the first and last dots
  // when fully filled.
  const insetPct = 50 / N; // half a column, in %
  // Fill fraction across the dot-to-dot span (0..1). For an in-progress phase
  // we fill halfway into its column; for a fully-complete run (currentIdx=N-1)
  // fillFrac=1 → bar reaches last dot center exactly.
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
          isFailed ? 'bg-status-error' : isStopped ? 'bg-orange-400' : 'bg-status-success',
        )}
        style={{ left: `${insetPct}%` }}
        initial={false}
        animate={{ width: fillWidthExpr }}
        transition={{ duration: 0.7, ease: 'easeOut' }}
      />

      <div className="relative flex items-start">
        {PHASE_ORDER.map((phase, idx) => {
          const isCurrent = currentPhase === phase;
          const isCompleted = currentIdx > idx;
          const isPhaseFailed = isCurrent && (phaseStatus === 'failed' || isFailed);
          const isPhasePaused = isCurrent && isPaused;

          return (
            <div key={phase} className="flex-1 flex flex-col items-center">
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
                {isPhaseFailed ? (
                  <X size={10} strokeWidth={3} />
                ) : isPhasePaused ? (
                  <PauseIcon size={8} strokeWidth={3} />
                ) : isCompleted ? (
                  <Check size={10} strokeWidth={3} />
                ) : null}
              </motion.div>
              <span
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
                {PHASE_LABELS[phase]}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
