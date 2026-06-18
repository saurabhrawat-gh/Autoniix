'use client';

/**
 * PageBreadcrumb — thin location strip rendered at the top of the floating
 * content card. Replaces the chrome-bar breadcrumb per locked feedback:
 *
 *   /dashboard                 → Default Workspace › Home
 *   /dashboard/notifications   → Default Workspace › Notifications
 *   /dashboard/channels        → Default Workspace › Create › Channels
 *   /dashboard/queue           → Default Workspace › Operate › Queue
 *   /dashboard/channels/123    → Default Workspace › Create › Channels › Detail
 *
 * "Dashboard" is dropped from the chain. The pillar (Create / Operate /
 * Measure / Configure) is injected between Workspace and the page name when
 * the leaf belongs to one. Workspace and Pillar labels are non-interactive.
 */

import { Fragment, useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronRight } from 'lucide-react';
import { authApi } from '../api-v2';

const SEGMENT_LABELS: Record<string, string> = {
  notifications: 'Notifications',
  channels: 'Channels',
  content: 'Content',
  library: 'Library',
  schedule: 'Schedule',
  queue: 'Queue',
  progress: 'Progress',
  review: 'Review',
  fleet: 'Fleet',
  analytics: 'Analytics',
  experiments: 'Experiments',
  workspace: 'Workspace',
  teams: 'Teams',
  users: 'Users',
  providers: 'Providers',
  settings: 'Settings',
  debug: 'Debug',
  profile: 'Profile',
  new: 'New',
  calendar: 'Calendar',
  jobs: 'Jobs',
  onboarding: 'Onboarding',
};

// Maps the first segment after /dashboard to the pillar it belongs to.
// Top-level pages (Home, Notifications) are not pillared.
const SEGMENT_TO_PILLAR: Record<string, string> = {
  channels: 'Create',
  content: 'Create',
  library: 'Create',
  schedule: 'Create',
  queue: 'Operate',
  progress: 'Operate',
  review: 'Operate',
  fleet: 'Operate',
  analytics: 'Measure',
  experiments: 'Measure',
  workspace: 'Configure',
  teams: 'Configure',
  users: 'Configure',
  providers: 'Configure',
  settings: 'Configure',
  debug: 'Configure',
};

function titlecase(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function labelFor(seg: string): string {
  if (/^\d+$/.test(seg) || /^[0-9a-f]{8}-/.test(seg)) return 'Detail';
  return SEGMENT_LABELS[seg] ?? titlecase(seg.replace(/-/g, ' '));
}

export function PageBreadcrumb() {
  const pathname = usePathname() || '';
  const [workspaceName, setWorkspaceName] = useState('Workspace');

  useEffect(() => {
    let mounted = true;
    authApi.listWorkspaces()
      .then((res: any) => {
        if (!mounted) return;
        const list = res?.data ?? [];
        const active = list.find((w: any) => w.active) ?? list[0];
        if (active?.name) setWorkspaceName(active.name);
      })
      .catch(() => { /* fall back to placeholder */ });
    return () => { mounted = false; };
  }, []);

  const segs = pathname.split('/').filter(Boolean);
  if (segs.length === 0 || segs[0] !== 'dashboard') return null;

  const sub = segs.slice(1);
  // Build the chain that follows "Workspace ›".
  type Crumb = { label: string; href?: string };
  const chain: Crumb[] = [];

  if (sub.length === 0) {
    chain.push({ label: 'Home' });
  } else {
    const firstSeg = sub[0];
    const pillar = SEGMENT_TO_PILLAR[firstSeg];
    if (pillar) {
      // Pillar label is purely contextual — not a route.
      chain.push({ label: pillar });
    }
    let href = '/dashboard';
    for (let i = 0; i < sub.length; i++) {
      const seg = sub[i];
      href += '/' + seg;
      const isLast = i === sub.length - 1;
      chain.push({ label: labelFor(seg), href: isLast ? undefined : href });
    }
  }

  return (
    <nav
      aria-label="Breadcrumb"
      className="shrink-0 flex items-center gap-1.5 px-5 pt-3 pb-2 text-[12px] text-content-tertiary"
    >
      {/* Workspace — not clickable */}
      <span className="truncate max-w-[200px] text-content-secondary font-medium" title={workspaceName}>
        {workspaceName}
      </span>
      {chain.map((c, i) => {
        const isLast = i === chain.length - 1;
        return (
          <Fragment key={`${c.label}-${i}`}>
            <ChevronRight size={11} className="shrink-0 text-content-tertiary opacity-60" aria-hidden />
            {c.href && !isLast ? (
              <Link
                href={c.href}
                className="hover:text-content-primary transition-colors truncate max-w-[180px]"
              >
                {c.label}
              </Link>
            ) : (
              <span
                aria-current={isLast ? 'page' : undefined}
                className={
                  isLast
                    ? 'text-content-primary font-medium truncate max-w-[220px]'
                    : 'text-content-tertiary truncate max-w-[160px]'
                }
              >
                {c.label}
              </span>
            )}
          </Fragment>
        );
      })}
    </nav>
  );
}
