'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { cn } from '../utils';

const PHASE_GROUPS = [
  { label: 'Research', phases: ['researching', 'brand_check'] },
  { label: 'Script',   phases: ['scripting', 'directing'] },
  { label: 'Voice',    phases: ['generating_voice'] },
  { label: 'Assets',   phases: ['generating_assets', 'post_production'] },
  { label: 'Render',   phases: ['rendering', 'delivering', 'analytics'] },
];

interface PipelineBarVisualizerProps {
  jobs: any[];
  className?: string;
}

export function PipelineBarVisualizer({ jobs, className }: PipelineBarVisualizerProps) {
  const reduce = useReducedMotion();

  const counts = PHASE_GROUPS.map((g) =>
    jobs.filter((j) => g.phases.includes(j.current_phase || j.phase || '')).length,
  );
  const maxCount = Math.max(1, ...counts);

  return (
    <div className={cn('flex items-end gap-1', className)} style={{ height: 32 }}>
      {PHASE_GROUPS.map((g, i) => {
        const count = counts[i];
        const hPct  = Math.max(10, (count > 0 ? count / maxCount : 0) * 100);
        return (
          <motion.div
            key={g.label}
            title={`${g.label}: ${count} job${count !== 1 ? 's' : ''}`}
            className="flex-1 rounded-full"
            style={{
              background: count > 0 ? 'rgb(var(--accent))' : 'rgb(var(--border))',
              opacity: count > 0 ? 1 : 0.35,
            }}
            animate={{ height: reduce ? '10%' : `${hPct}%` }}
            transition={{ duration: 0.4, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
          />
        );
      })}
    </div>
  );
}
