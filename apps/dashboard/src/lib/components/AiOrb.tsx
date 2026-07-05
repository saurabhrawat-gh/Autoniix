'use client';

import dynamic from 'next/dynamic';
import { useReducedMotion } from 'framer-motion';
import { useTheme } from '../theme';
import { SimpleTooltip, TooltipProvider } from '../ui';
import type { AgentState } from '../../components/ui/orb';

const OrbCanvas = dynamic(
  () => import('../../components/ui/orb').then((m) => ({ default: m.Orb })),
  {
    ssr: false,
    loading: () => <div className="w-20 h-20 rounded-full bg-accent/20 animate-pulse" />,
  },
);

const PHASE_THINKING = new Set(['scripting', 'researching', 'brand_check', 'directing']);
const PHASE_LISTENING = new Set(['generating_voice', 'generating_assets', 'post_production', 'rendering']);
const PHASE_TALKING   = new Set(['delivering', 'analytics']);

function mapState(jobs: any[], systemStopped: boolean): AgentState {
  if (systemStopped) return null;
  const phases = jobs.map((j) => j.current_phase || j.phase || j.status || '');
  if (phases.some((p) => PHASE_TALKING.has(p)))   return 'speaking';
  if (phases.some((p) => PHASE_LISTENING.has(p))) return 'listening';
  if (phases.some((p) => PHASE_THINKING.has(p)))  return 'thinking';
  return null;
}

interface AiOrbProps {
  jobs: any[];
  systemStopped: boolean;
}

export function AiOrb({ jobs, systemStopped }: AiOrbProps) {
  const reduce = useReducedMotion();
  const { resolved } = useTheme();

  const state = mapState(jobs, systemStopped);
  const count = jobs.length;
  const label = state ?? 'idle';
  const tip   = `${label} — ${count} active job${count !== 1 ? 's' : ''}`;

  const colors: [string, string] = resolved === 'dark'
    ? ['#fcffe1', '#3d5c1a']
    : ['#3d5c1a', '#fcffe1'];

  return (
    <TooltipProvider delayDuration={300}>
      <SimpleTooltip content={tip} side="right">
        {reduce ? (
          <div className="w-20 h-20 rounded-full bg-accent/20" />
        ) : (
          <div
            className="w-20 h-20 cursor-default"
            style={systemStopped ? { filter: 'grayscale(1) opacity(0.5)' } : undefined}
          >
            <OrbCanvas agentState={state} colors={colors} />
          </div>
        )}
      </SimpleTooltip>
    </TooltipProvider>
  );
}
