import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const PHASE_ORDER = [
  'researching', 'brand_check', 'scripting', 'generating_voice',
  'generating_assets', 'directing', 'post_production', 'rendering',
  'pending_review', 'delivering', 'analytics', 'delivered',
];

export const PHASE_LABELS: Record<string, string> = {
  researching: 'Research',
  brand_check: 'Brand Check',
  scripting: 'Script',
  generating_voice: 'Voice',
  generating_assets: 'Assets + Thumbnail',
  directing: 'Direction',
  post_production: 'Post-Production',
  rendering: 'Render',
  pending_review: 'Review',
  delivering: 'Delivery',
  analytics: 'Analytics',
  delivered: 'Delivered',
  test_delivered: 'Delivered (Test)',
  retrying: 'Retrying',
  stopped: 'Stopped',
  superseded: 'Superseded',
  failed: 'Failed',
  rejected: 'Rejected',
};

export function statusColor(status: string): string {
  if (status === 'completed' || status === 'delivered' || status === 'test_delivered') return 'text-status-success';
  if (status === 'failed' || status === 'rejected') return 'text-status-error';
  if (status === 'stopped') return 'text-orange-400';
  if (status === 'superseded') return 'text-content-tertiary';
  if (status === 'started' || status === 'retrying') return 'text-accent';
  if (status === 'pending_review') return 'text-status-warning';
  return 'text-content-tertiary';
}

export function statusIcon(status: string): string {
  if (status === 'completed' || status === 'delivered' || status === 'test_delivered') return '✓';
  if (status === 'failed' || status === 'rejected') return '✕';
  if (status === 'stopped') return '■';
  if (status === 'superseded') return '⊘';
  if (status === 'retrying') return '↻';
  if (status === 'started') return '●';
  if (status === 'pending_review') return '◐';
  return '○';
}

export function statusDot(status: string): string {
  if (status === 'active') return 'bg-status-success';
  if (status === 'disabled') return 'bg-content-tertiary';
  if (status === 'archived') return 'bg-surface-3';
  if (status === 'failed' || status === 'rejected') return 'bg-status-error';
  if (status === 'stopped') return 'bg-orange-400';
  if (status === 'superseded') return 'bg-surface-3';
  return 'bg-status-warning';
}

export function isTerminalStatus(status: string): boolean {
  return ['failed', 'stopped', 'superseded', 'delivered', 'test_delivered', 'rejected'].includes(status);
}

export function isStopped(status: string): boolean {
  return status === 'stopped';
}

export function isSuperseded(status: string): boolean {
  return status === 'superseded';
}
