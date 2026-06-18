'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useHotkeys } from 'react-hotkeys-hook';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../utils';
import { Tip } from './Tooltip';
import { usePermissions } from '../hooks/usePermissions';
import { WorkspaceSwitcher } from './WorkspaceSwitcher';
import { AppBrand } from './AppBrand';
import {
  Home,
  Bell,
  Tv,
  Clapperboard,
  Archive,
  CalendarDays,
  ListChecks,
  Activity,
  ClipboardCheck,
  Cpu,
  BarChart2,
  FlaskConical,
  Boxes,
  UserCheck,
  Users,
  Plug,
  Settings,
  Terminal,
  ChevronLeft,
  ChevronDown,
} from './Icon';

const COLLAPSED_KEY = 'sidebar_collapsed_v1';

interface Leaf {
  href: string;
  label: string;
  icon: LucideIcon;
  shortcut?: string;
  permission?: string;
  requireGlobalRole?: 'superadmin';
}

interface Pillar {
  id: string;
  label: string;
  items: Leaf[];
}

// Top leaves — meta-navigation that sits above all pillars, no group label.
const TOP_LEAVES: Leaf[] = [
  { href: '/dashboard',               label: 'Home',          icon: Home, shortcut: 'g d' },
  { href: '/dashboard/notifications', label: 'Notifications', icon: Bell, shortcut: 'g n' },
];

// Pillars — four flat groups of work surfaces (Create / Operate / Measure / Configure).
// Per §9.4, pillars are NEVER expandable — every leaf is always visible.
const PILLARS: Pillar[] = [
  {
    id: 'create',
    label: 'Create',
    items: [
      { href: '/dashboard/channels',         label: 'Channels', icon: Tv,           shortcut: 'g c' },
      { href: '/dashboard/content',          label: 'Content',  icon: Clapperboard, shortcut: 'g v' },
      { href: '/dashboard/library',          label: 'Library',  icon: Archive,      shortcut: 'g l', permission: 'project.view' },
      { href: '/dashboard/content/calendar', label: 'Schedule', icon: CalendarDays, shortcut: 'g k' },
    ],
  },
  {
    id: 'operate',
    label: 'Operate',
    items: [
      { href: '/dashboard/queue',    label: 'Queue',    icon: ListChecks,     shortcut: 'g q' },
      { href: '/dashboard/progress', label: 'Progress', icon: Activity,       shortcut: 'g p' },
      { href: '/dashboard/review',   label: 'Review',   icon: ClipboardCheck, shortcut: 'g r' },
      { href: '/dashboard/fleet',    label: 'Fleet',    icon: Cpu,            shortcut: 'g f', permission: 'workspace.settings.edit' },
    ],
  },
  {
    id: 'measure',
    label: 'Measure',
    items: [
      { href: '/dashboard/analytics',   label: 'Analytics',   icon: BarChart2,    shortcut: 'g a' },
      { href: '/dashboard/experiments', label: 'Experiments', icon: FlaskConical, shortcut: 'g e', permission: 'workspace.settings.edit' },
    ],
  },
  {
    id: 'configure',
    label: 'Configure',
    items: [
      { href: '/dashboard/workspace', label: 'Workspace', icon: Boxes,     shortcut: 'g w', permission: 'workspace.view' },
      { href: '/dashboard/teams',     label: 'Teams',     icon: UserCheck, shortcut: 'g t', permission: 'workspace.members.view' },
      { href: '/dashboard/users',     label: 'Users',     icon: Users,     shortcut: 'g u', requireGlobalRole: 'superadmin' },
      { href: '/dashboard/providers', label: 'Providers', icon: Plug,      shortcut: 'g i', permission: 'credentials.view.labels' },
      { href: '/dashboard/settings',  label: 'Settings',  icon: Settings,  shortcut: 'g s', permission: 'workspace.settings.edit' },
      { href: '/dashboard/debug',     label: 'Debug',     icon: Terminal,  shortcut: 'g b', permission: 'workspace.settings.edit' },
    ],
  },
];

function LeafLink({
  leaf,
  active,
  collapsed,
}: {
  leaf: Leaf;
  active: boolean;
  collapsed: boolean;
}) {
  const Icon = leaf.icon;
  const link = (
    <Link
      href={leaf.href}
      className={cn(
        'group relative flex items-center rounded-md transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40',
        active
          ? 'bg-surface-2 text-content-primary font-medium'
          : 'text-content-secondary hover:bg-surface-1 hover:text-content-primary font-normal',
        collapsed
          ? 'w-9 h-9 justify-center mx-auto'
          : 'gap-2.5 px-2.5 py-1 w-full text-[13px]'
      )}
    >
      <Icon
        size={collapsed ? 16 : 15}
        className={cn('shrink-0', active ? 'text-accent' : 'opacity-80')}
      />
      {!collapsed && (
        <>
          <span className="truncate flex-1">{leaf.label}</span>
          {leaf.shortcut && (
            <span className="font-mono text-[10px] text-content-tertiary opacity-0 group-hover:opacity-100 transition-opacity">
              {leaf.shortcut}
            </span>
          )}
        </>
      )}
    </Link>
  );
  if (collapsed) {
    return (
      <Tip text={`${leaf.label}${leaf.shortcut ? ` · ${leaf.shortcut}` : ''}`} pos="right">
        {link}
      </Tip>
    );
  }
  return link;
}

export function Sidebar() {
  const pathname = usePathname() || '';
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [gPressed, setGPressed] = useState(false);
  const { hasPermission, globalRole, loading: permsLoading, error: permsError } = usePermissions();

  useEffect(() => {
    try {
      const stored = localStorage.getItem(COLLAPSED_KEY);
      if (stored !== null) setCollapsed(stored === 'true');
    } catch {}
  }, []);

  function toggleCollapsed() {
    setCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem(COLLAPSED_KEY, String(next)); } catch {}
      return next;
    });
  }

  const isActive = (href: string) => {
    if (href === '/dashboard') return pathname === '/dashboard';
    return pathname.startsWith(href);
  };

  const isItemVisible = (item: { permission?: string; requireGlobalRole?: string }) => {
    if (item.requireGlobalRole && !permsLoading && !permsError && globalRole !== item.requireGlobalRole) return false;
    if (item.permission && !permsLoading && !permsError && !hasPermission(item.permission)) return false;
    return true;
  };

  // Keyboard sequence shortcuts (`g <letter>`)
  useHotkeys('g', () => { setGPressed(true); setTimeout(() => setGPressed(false), 1200); }, []);
  const shortcuts: Record<string, string> = {
    d: '/dashboard',
    n: '/dashboard/notifications',
    c: '/dashboard/channels',
    v: '/dashboard/content',
    l: '/dashboard/library',
    k: '/dashboard/content/calendar',
    q: '/dashboard/queue',
    p: '/dashboard/progress',
    r: '/dashboard/review',
    f: '/dashboard/fleet',
    a: '/dashboard/analytics',
    e: '/dashboard/experiments',
    w: '/dashboard/workspace',
    t: '/dashboard/teams',
    u: '/dashboard/users',
    i: '/dashboard/providers',
    s: '/dashboard/settings',
    b: '/dashboard/debug',
  };
  Object.entries(shortcuts).forEach(([key, path]) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useHotkeys(key, () => { if (gPressed) { setGPressed(false); router.push(path); } }, [gPressed]);
  });

  return (
    <motion.aside
      className="hidden md:flex flex-col shrink-0 h-full bg-transparent overflow-hidden"
      animate={{ width: collapsed ? 56 : 232 }}
      transition={{ duration: 0.22, ease: [0.2, 0.7, 0.3, 1] }}
    >
      {/* Persistent Autoniix brand — always visible. Visibly separated from
          the workspace switcher below so the two reads as distinct groups. */}
      <div className={cn('shrink-0', collapsed ? 'px-1.5 pt-0' : 'px-2 pt-0')}>
        <AppBrand collapsed={collapsed} />
      </div>

      {/* Workspace switcher — secondary identity. Small gap above. */}
      <div className={cn('shrink-0', collapsed ? 'px-1.5 pt-1.5' : 'px-2 pt-1.5')}>
        <WorkspaceSwitcher collapsed={collapsed} />
      </div>

      {/* Top leaves — Home, Notifications. Visible gap above so it's a
          separate group from the identity rows. */}
      <div className={cn('shrink-0 space-y-px', collapsed ? 'px-1.5 pt-3' : 'px-2 pt-3')}>
        {TOP_LEAVES.filter(isItemVisible).map(item => (
          <LeafLink key={item.href} leaf={item} active={isActive(item.href)} collapsed={collapsed} />
        ))}
      </div>

      {/* Pillars (Create / Operate / Measure / Configure) — flat, never expandable.
          Tight vertical rhythm so the full IA fits without a scrollbar at common
          viewport heights (≥ 720px). */}
      <nav className={cn('flex-1 overflow-y-auto overflow-x-hidden pt-2 pb-1', collapsed ? 'px-1.5' : 'px-2')}>
        {PILLARS.map(pillar => {
          const items = pillar.items.filter(isItemVisible);
          if (items.length === 0) return null;
          return (
            <div
              key={pillar.id}
              className={cn(
                'pt-2.5 first:pt-1.5',
                collapsed && 'mt-2 pt-2 border-t border-border/70 first:border-t-0 first:mt-1 first:pt-0'
              )}
            >
              {!collapsed && (
                /* Linear-style section header — tiny uppercase, faded grey,
                   trailed by a chevron so it reads as a "collapsible group"
                   (visual cue only at the moment). */
                <div className="flex items-center gap-1 px-2.5 pb-1 text-[10px] font-medium text-content-tertiary/80 uppercase tracking-wider">
                  <span>{pillar.label}</span>
                  <ChevronDown size={9} className="opacity-60" aria-hidden />
                </div>
              )}
              <div className="space-y-px">
                {items.map(item => (
                  <LeafLink key={item.href} leaf={item} active={isActive(item.href)} collapsed={collapsed} />
                ))}
              </div>
            </div>
          );
        })}
      </nav>

      {/* Bottom utility row — Collapse only. Help (?) and User menu live in
          the chrome top-right cluster so they remain reachable in collapsed
          mode without crowding the 56px-wide sidebar. */}
      <div className={cn('shrink-0 pt-1 pb-1.5', collapsed ? 'px-1.5' : 'px-2')}>
        {collapsed ? (
          <Tip text="Expand sidebar · [" pos="right">
            <button
              type="button"
              onClick={toggleCollapsed}
              className="w-9 h-9 flex items-center justify-center mx-auto rounded-md text-content-tertiary hover:text-content-primary hover:bg-surface-2 transition-colors"
              aria-label="Expand sidebar"
            >
              <ChevronLeft size={14} className="rotate-180 opacity-80" />
            </button>
          </Tip>
        ) : (
          <button
            type="button"
            onClick={toggleCollapsed}
            className="group flex items-center gap-2.5 px-2.5 py-1 w-full text-[13px] font-normal text-content-tertiary hover:bg-surface-2 hover:text-content-primary rounded-md transition-colors"
            aria-label="Collapse sidebar"
          >
            <ChevronLeft size={14} className="shrink-0 opacity-80" />
            <span className="truncate flex-1 text-left">Collapse</span>
            <span className="font-mono text-[10px] opacity-0 group-hover:opacity-100 transition-opacity">[</span>
          </button>
        )}
      </div>
    </motion.aside>
  );
}
