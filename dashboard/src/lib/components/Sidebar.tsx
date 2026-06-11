'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHotkeys } from 'react-hotkeys-hook';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../utils';
import { Tip } from './Tooltip';
import { Button } from '../ui';
import { usePermissions } from '../hooks/usePermissions';
import { WorkspaceSwitcher } from './WorkspaceSwitcher';
import {
  Home,
  Tv,
  Archive,
  Activity,
  Plug,
  Settings,
  ChevronLeft,
  ChevronRight,
  Video,
  Clapperboard,
  ClipboardCheck,
  FlaskConical,
  Users,
  Bell,
  Cpu,
  Terminal,
  Boxes,
  CalendarDays,
  BarChart2,
  ListChecks,
  ChevronDown,
  UserCheck,
} from './Icon';

const COLLAPSED_KEY = 'sidebar_collapsed_v1';

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  shortcut?: string;
  permission?: string;
  requireGlobalRole?: 'superadmin';
}

interface NavGroup {
  id: string;
  label: string;
  icon: LucideIcon;
  href?: string;
  expandable?: boolean;
  defaultExpanded?: boolean;
  items?: NavItem[];
  permission?: string;
  requireGlobalRole?: 'superadmin';
  pinBottom?: boolean;
}

const NAV_STRUCTURE: NavGroup[] = [
  {
    id: 'home',
    label: 'Home',
    icon: Home,
    href: '/dashboard',
    shortcut: 'g d',
  } as NavGroup & { shortcut: string },
  {
    id: 'studio',
    label: 'Studio',
    icon: Clapperboard,
    expandable: true,
    defaultExpanded: true,
    items: [
      { href: '/dashboard/content',     label: 'Content',   icon: Clapperboard, shortcut: 'g v' },
      { href: '/dashboard/review',      label: 'Review',    icon: ClipboardCheck, shortcut: 'g r' },
      { href: '/dashboard/library',     label: 'Library',   icon: Archive, shortcut: 'g l', permission: 'project.view' },
      { href: '/dashboard/queue',       label: 'Queue',     icon: ListChecks, shortcut: 'g q' },
      { href: '/dashboard/fleet',       label: 'Fleet',     icon: Cpu, shortcut: 'g f', permission: 'workspace.settings.edit' },
      { href: '/dashboard/experiments', label: 'Experiments', icon: FlaskConical, shortcut: 'g e', permission: 'workspace.settings.edit' },
    ],
  },
  {
    id: 'channels',
    label: 'Channels',
    icon: Tv,
    href: '/dashboard/channels',
    shortcut: 'g c',
  } as NavGroup & { shortcut: string },
  {
    id: 'schedule',
    label: 'Schedule',
    icon: CalendarDays,
    href: '/dashboard/content/calendar',
    shortcut: 'g k',
  } as NavGroup & { shortcut: string },
  {
    id: 'analytics',
    label: 'Analytics',
    icon: BarChart2,
    href: '/dashboard/analytics',
    shortcut: 'g a',
  } as NavGroup & { shortcut: string },
  {
    id: 'notifications',
    label: 'Notifications',
    icon: Bell,
    href: '/dashboard/notifications',
    shortcut: 'g n',
  } as NavGroup & { shortcut: string },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    expandable: true,
    defaultExpanded: false,
    pinBottom: true,
    items: [
      { href: '/dashboard/workspace',  label: 'Workspace', icon: Boxes,      shortcut: 'g w', permission: 'workspace.view' },
      { href: '/dashboard/teams',      label: 'Teams',     icon: UserCheck,  shortcut: 'g t', permission: 'workspace.members.view' },
      { href: '/dashboard/users',      label: 'Users',     icon: Users,      shortcut: 'g u', requireGlobalRole: 'superadmin' },
      { href: '/dashboard/providers',  label: 'Providers', icon: Plug,       shortcut: 'g i', permission: 'credentials.view.labels' },
      { href: '/dashboard/settings',   label: 'General',   icon: Settings,   shortcut: 'g s', permission: 'workspace.settings.edit' },
      { href: '/dashboard/debug',      label: 'Debug',     icon: Terminal,   shortcut: 'g b', permission: 'workspace.settings.edit' },
    ],
  },
];

function NavLeaf({
  item,
  active,
  collapsed,
  indent = false,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
  indent?: boolean;
}) {
  const Icon = item.icon;
  const link = (
    <Link
      href={item.href}
      className={cn(
        'relative flex items-center text-sm font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40',
        active
          ? 'bg-surface-1 text-accent rounded-full'
          : 'text-content-secondary hover:text-content-primary hover:bg-surface-1 rounded-full',
        collapsed
          ? 'w-10 h-10 justify-center mx-auto'
          : cn('gap-2.5 px-3 py-2 w-full', indent && 'pl-8')
      )}
    >
      <Icon size={collapsed ? 17 : 15} className="shrink-0" />
      {!collapsed && <span className="truncate">{item.label}</span>}
    </Link>
  );

  if (collapsed) {
    return (
      <Tip text={`${item.label}${(item as any).shortcut ? ` · ${(item as any).shortcut}` : ''}`} pos="right">
        {link}
      </Tip>
    );
  }
  return link;
}

function ExpandableGroup({
  group,
  isAnyChildActive,
  collapsed,
  items = [],
  isActiveItem,
  children,
}: {
  group: NavGroup;
  isAnyChildActive: boolean;
  collapsed: boolean;
  items?: NavItem[];
  isActiveItem?: (href: string) => boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(group.defaultExpanded ?? false);
  const [floatTop, setFloatTop] = useState<number | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const Icon = group.icon;

  useEffect(() => { if (!collapsed) setFloatTop(null); }, [collapsed]);

  if (collapsed) {
    return (
      <div>
        <Tip text={group.label} pos="right">
          <button
            ref={btnRef}
            type="button"
            onClick={() => {
              if (floatTop !== null) { setFloatTop(null); return; }
              const rect = btnRef.current?.getBoundingClientRect();
              if (rect) setFloatTop(rect.top);
            }}
            className={cn(
              'w-10 h-10 flex items-center justify-center mx-auto rounded-full transition-colors',
              isAnyChildActive
                ? 'bg-surface-1 text-accent'
                : 'text-content-secondary hover:text-content-primary hover:bg-surface-1'
            )}
            aria-label={group.label}
          >
            <Icon size={17} className="shrink-0" />
          </button>
        </Tip>
        {floatTop !== null && items.length > 0 && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setFloatTop(null)} />
            <div
              className="fixed left-[60px] z-50 w-52 bg-surface-0 border border-border rounded-xl shadow-elevated py-1 overflow-hidden"
              style={{ top: floatTop }}
            >
              <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-content-tertiary border-b border-border mb-1">
                {group.label}
              </div>
              {items.map((item) => {
                const active = isActiveItem?.(item.href) ?? false;
                const ItemIcon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setFloatTop(null)}
                    className={cn(
                      'flex items-center gap-2.5 px-3 py-2 text-sm font-medium transition-colors',
                      active
                        ? 'text-accent bg-surface-1'
                        : 'text-content-secondary hover:text-content-primary hover:bg-surface-1'
                    )}
                  >
                    <ItemIcon size={14} className="shrink-0" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </>
        )}
      </div>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'flex items-center gap-2.5 px-3 py-2 w-full rounded-full text-sm font-medium transition-colors',
          isAnyChildActive
            ? 'text-accent'
            : 'text-content-secondary hover:text-content-primary hover:bg-surface-1'
        )}
      >
        <Icon size={15} className="shrink-0" />
        <span className="flex-1 truncate text-left">{group.label}</span>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.15, ease: [0.2, 0, 0, 1] }}
          style={{ display: 'inline-flex' }}
        >
          <ChevronDown size={13} className="text-content-tertiary" />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="children"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18, ease: [0.2, 0, 0, 1] }}
            className="overflow-hidden"
          >
            <div className="pl-2 mt-0.5 space-y-0.5 border-l border-border ml-4">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
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

  // Keyboard shortcuts
  useHotkeys('g', () => { setGPressed(true); setTimeout(() => setGPressed(false), 1200); }, []);
  const shortcuts: Record<string, string> = {
    d: '/dashboard', c: '/dashboard/channels', v: '/dashboard/content',
    r: '/dashboard/review', l: '/dashboard/library', q: '/dashboard/queue',
    e: '/dashboard/experiments', i: '/dashboard/providers', a: '/dashboard/analytics',
    k: '/dashboard/content/calendar', f: '/dashboard/fleet',
    u: '/dashboard/users', s: '/dashboard/settings', n: '/dashboard/notifications',
    w: '/dashboard/workspace', t: '/dashboard/teams', b: '/dashboard/debug',
  };
  Object.entries(shortcuts).forEach(([key, path]) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useHotkeys(key, () => { if (gPressed) { setGPressed(false); router.push(path); } }, [gPressed]);
  });

  const topGroups = NAV_STRUCTURE.filter((g) => !g.pinBottom);
  const bottomGroups = NAV_STRUCTURE.filter((g) => g.pinBottom);

  function renderGroup(group: NavGroup) {
    if (group.href) {
      const active = isActive(group.href);
      const Icon = group.icon;
      const link = (
        <Link
          href={group.href}
          className={cn(
            'flex items-center text-sm font-medium transition-colors rounded-full',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40',
            active
              ? 'bg-surface-1 text-accent'
              : 'text-content-secondary hover:text-content-primary hover:bg-surface-1',
            collapsed
              ? 'w-10 h-10 justify-center mx-auto'
              : 'gap-2.5 px-3 py-2 w-full'
          )}
        >
          <Icon size={collapsed ? 17 : 15} className="shrink-0" />
          {!collapsed && <span className="truncate">{group.label}</span>}
        </Link>
      );
      if (collapsed) {
        return (
          <Tip key={group.id} text={group.label} pos="right">{link}</Tip>
        );
      }
      return <div key={group.id}>{link}</div>;
    }

    if (group.expandable && group.items) {
      const visibleItems = group.items.filter(isItemVisible);
      if (visibleItems.length === 0) return null;
      const anyActive = visibleItems.some((item) => isActive(item.href));
      return (
        <ExpandableGroup key={group.id} group={group} isAnyChildActive={anyActive} collapsed={collapsed} items={visibleItems} isActiveItem={isActive}>
          {visibleItems.map((item) => (
            <NavLeaf key={item.href} item={item} active={isActive(item.href)} collapsed={collapsed} indent />
          ))}
        </ExpandableGroup>
      );
    }

    return null;
  }

  return (
    <motion.aside
      className="hidden md:flex flex-col shrink-0 h-full bg-surface-sidebar border-r border-border overflow-hidden"
      animate={{ width: collapsed ? 56 : 240 }}
      transition={{ duration: 0.26, ease: [0.2, 0, 0, 1] }}
    >
      {/* Logo */}
      <div className={cn(
        'flex items-center h-topbar px-3 border-b border-border shrink-0',
        collapsed ? 'justify-center' : 'gap-2.5'
      )}>
        <Link href="/dashboard" aria-label="Home">
          <div className="w-7 h-7 rounded-md bg-accent/10 flex items-center justify-center">
            <Video size={14} className="text-accent" />
          </div>
        </Link>
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.span
              key="brand"
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -6 }}
              transition={{ duration: 0.12, ease: [0.2, 0, 0, 1] }}
              className="text-sm font-semibold text-content-primary truncate"
            >
              Autoniix
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      {/* Workspace switcher */}
      <div className={cn('border-b border-border shrink-0', collapsed ? 'px-1.5 py-2' : 'px-2 py-2')}>
        <WorkspaceSwitcher collapsed={collapsed} />
      </div>

      {/* Top nav */}
      <nav className={cn(
        'flex-1 overflow-y-auto overflow-x-hidden py-3',
        collapsed ? 'px-1.5 space-y-1' : 'px-2 space-y-0.5'
      )}>
        {topGroups.map(renderGroup)}
      </nav>

      {/* Bottom groups (Settings) */}
      {bottomGroups.length > 0 && (
        <div className={cn(
          'border-t border-border shrink-0 pt-2',
          collapsed ? 'px-1.5 pb-2 space-y-1' : 'px-2 pb-2 space-y-0.5'
        )}>
          {bottomGroups.map(renderGroup)}
        </div>
      )}

      {/* Collapse toggle */}
      <div className={cn(
        'border-t border-border shrink-0',
        collapsed ? 'py-2 px-1.5' : 'py-3 px-2'
      )}>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={toggleCollapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={cn(
            'text-xs text-content-tertiary hover:text-content-primary hover:bg-surface-2',
            collapsed ? 'w-10 h-8 justify-center mx-auto' : 'w-full justify-start gap-2 px-2.5 py-1.5 h-auto'
          )}
        >
          <motion.span
            animate={{ rotate: collapsed ? 0 : 180 }}
            transition={{ duration: 0.12, ease: [0.16, 1, 0.3, 1] }}
            style={{ display: 'inline-flex' }}
          >
            <ChevronRight size={14} />
          </motion.span>
          <AnimatePresence initial={false}>
            {!collapsed && (
              <motion.span
                key="collapse-label"
                initial={{ opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -4 }}
                transition={{ duration: 0.12, ease: [0.2, 0, 0, 1] }}
              >
                Collapse
              </motion.span>
            )}
          </AnimatePresence>
        </Button>
      </div>
    </motion.aside>
  );
}
