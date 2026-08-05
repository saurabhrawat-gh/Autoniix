'use client';

import { useReducedMotion } from 'framer-motion';

type EcgState = 'healthy' | 'warning' | 'stopped';

const W = 120;
const H = 30;
const MID = H / 2;

const PATHS: Record<EcgState, string> = {
  healthy: [
    `M0,${MID}`, `L18,${MID}`,
    `L22,${MID - 3}`, `L25,${MID}`,
    `L28,${MID + 2}`, `L30,${MID - 12}`, `L32,${MID + 8}`, `L34,${MID}`,
    `L40,${MID - 4}`, `L46,${MID}`,
    `L66,${MID}`, `L84,${MID}`,
    `L88,${MID - 3}`, `L91,${MID}`,
    `L94,${MID + 2}`, `L96,${MID - 12}`, `L98,${MID + 8}`, `L100,${MID}`,
    `L106,${MID - 4}`, `L112,${MID}`,
    `L${W},${MID}`,
  ].join(' '),
  warning: [
    `M0,${MID}`, `L12,${MID}`,
    `L15,${MID - 8}`, `L17,${MID + 5}`, `L19,${MID}`,
    `L32,${MID}`, `L35,${MID - 2}`,
    `L37,${MID - 14}`, `L39,${MID + 10}`, `L41,${MID}`,
    `L52,${MID - 1}`, `L55,${MID + 3}`, `L57,${MID}`,
    `L72,${MID}`, `L75,${MID - 6}`,
    `L77,${MID - 14}`, `L79,${MID + 10}`, `L81,${MID}`,
    `L92,${MID}`, `L95,${MID - 2}`, `L98,${MID + 2}`,
    `L${W},${MID}`,
  ].join(' '),
  stopped: `M0,${MID} L${W},${MID}`,
};

interface EcgLineProps {
  state: EcgState;
  className?: string;
}

export function EcgLine({ state, className }: EcgLineProps) {
  const reduce = useReducedMotion();

  const color =
    state === 'stopped'
      ? 'rgb(var(--status-error) / 0.5)'
      : state === 'warning'
      ? 'rgb(var(--status-warning) / 0.8)'
      : 'rgb(var(--status-success) / 0.8)';

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      height={H}
      className={className}
      aria-hidden="true"
      preserveAspectRatio="none"
    >
      <path
        d={PATHS[state]}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={
          reduce || state === 'stopped'
            ? undefined
            : {
                strokeDasharray: 200,
                animationName: 'ecg-draw',
                animationDuration: state === 'healthy' ? '1.8s' : '2.4s',
                animationTimingFunction: 'linear',
                animationIterationCount: 'infinite',
              }
        }
      />
    </svg>
  );
}
