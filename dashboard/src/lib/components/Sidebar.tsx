'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import { useHotkeys } from 'react-hotkeys-hook';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../utils';
import { Tip } from './Tooltip';
import {
  Home,
  Tv,
  Film,
  Archive,
  Activity,
  Zap,
  Plug,
  Settings,
  ChevronLeft,
  ChevronRight,
  Video,
} from './Icon';

const COLLAPSED_KEY = 'sidebar_collapsed_v1';

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  shortcut?: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Main',
    items: [
      { href: '/dashboard', label: 'Home', icon: Home, shortcut: 'g d' },
      { href: '/dashboard/channels', label: 'Channels', icon: Tv, shortcut: 'g c' },
    ],
  },
  {
    label: 'Content',
    items: [
      { href: '/dashboard/content', label: 'Content', icon: Film, shortcut: 'g v' },
      { href: '/dashboard/library', label: 'Library', icon: Archive, shortcut: 'g l' },
    ],
  },
  {
    label: 'Operations',
    items: [
      { href: '/dashboard/progress', label: 'Progress', icon: Activity, shortcut: 'g p' },
      { href: '/dashboard/experiments', label: 'Experiments', icon: Zap, shortcut: 'g e' },
      { href: '/dashboard/providers', label: 'Providers', icon: Plug, shortcut: 'g i' },
    ],
  },
  {
    label: 'System',
    items: [
      { href: '/dashboard/settings', label: 'Settings', icon: Settings, shortcut: 'g s' },
    ],
  },
];

function NavLink({
  item,
  active,
  collapsed,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
}) {
  const Icon = item.icon;
  const link = (
    <Link
      href={item.href}
      className={cn(
        'relative flex items-center rounded-md text-sm font-medium transition-colors',
        collapsed ? 'outline-none' : 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40',
        active
          ? 'bg-accent/10 text-accent'
          : 'text-content-secondary hover:text-content-primary hover:bg-surface-2',
        collapsed
          ? 'w-10 h-10 justify-center mx-auto'
          : 'gap-3 px-2.5 py-2 w-full'
      )}
      title={collapsed ? item.label : undefined}
    >
      {active && collapsed && (
        <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-accent" />
      )}
      <Icon size={collapsed ? 18 : 16} className="shrink-0" />
      {!collapsed && <span className="truncate">{item.label}</span>}
    </Link>
  );
  // Tip wraps with inline-flex which breaks vertical stacking — only wrap in collapsed mode where we need the tooltip
  if (collapsed) {
    return (
      <Tip text={`${item.label}${item.shortcut ? ` · ${item.shortcut}` : ''}`} pos="right">
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

  // Keyboard nav shortcuts
  useHotkeys('g', () => { setGPressed(true); setTimeout(() => setGPressed(false), 1200); }, []);
  useHotkeys('d', () => { if (gPressed) { setGPressed(false); router.push('/dashboard'); } }, [gPressed]);
  useHotkeys('c', () => { if (gPressed) { setGPressed(false); router.push('/dashboard/channels'); } }, [gPressed]);
  useHotkeys('v', () => { if (gPressed) { setGPressed(false); router.push('/dashboard/content'); } }, [gPressed]);
  useHotkeys('l', () => { if (gPressed) { setGPressed(false); router.push('/dashboard/library'); } }, [gPressed]);
  useHotkeys('p', () => { if (gPressed) { setGPressed(false); router.push('/dashboard/progress'); } }, [gPressed]);
  useHotkeys('e', () => { if (gPressed) { setGPressed(false); router.push('/dashboard/experiments'); } }, [gPressed]);
  useHotkeys('i', () => { if (gPressed) { setGPressed(false); router.push('/dashboard/providers'); } }, [gPressed]);
  useHotkeys('s', () => { if (gPressed) { setGPressed(false); router.push('/dashboard/settings'); } }, [gPressed]);

  return (
    <>
      <aside
        className={cn(
          'hidden md:flex flex-col shrink-0 h-full',
          'bg-surface-0 border-r border-border',
          'transition-all duration-200 ease-in-out',
          collapsed ? 'w-[60px]' : 'w-[220px]'
        )}
      >
        {/* Logo */}
        <div className={cn(
          'flex items-center h-12 px-3 border-b border-border shrink-0',
          collapsed ? 'justify-center' : 'gap-2.5'
        )}>
          <Link href="/dashboard" aria-label="Home">
            <div className="w-7 h-7 rounded-md bg-accent/10 flex items-center justify-center">
              <Video size={14} className="text-accent" />
            </div>
          </Link>
          {!collapsed && (
            <span className="text-sm font-semibold text-content-primary truncate">
              YT Automation
            </span>
          )}
        </div>

        {/* Nav groups */}
        <nav className={cn(
          'flex-1 overflow-y-auto overflow-x-hidden py-3',
          collapsed ? 'px-1.5 space-y-3' : 'px-2 space-y-4'
        )}>
          {NAV_GROUPS.map((group, gIdx) => (
            <div key={group.label}>
              {!collapsed ? (
                <div className="px-2.5 mb-1 text-[10px] uppercase tracking-widest font-semibold text-content-tertiary">
                  {group.label}
                </div>
              ) : gIdx > 0 ? (
                <div className="mx-3 mb-2 h-px bg-border" />
              ) : null}
              <div className={collapsed ? 'space-y-1' : 'space-y-0.5'}>
                {group.items.map(item => (
                  <NavLink
                    key={item.href}
                    item={item}
                    active={isActive(item.href)}
                    collapsed={collapsed}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Bottom controls — collapse toggle only */}
        <div className={cn(
          'border-t border-border shrink-0',
          collapsed ? 'py-2 px-1.5' : 'py-3 px-2'
        )}>
          <button
            onClick={toggleCollapsed}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className={cn(
              'flex items-center rounded-md text-xs text-content-tertiary',
              'hover:text-content-primary hover:bg-surface-2 transition-colors',
              collapsed ? 'w-10 h-8 justify-center mx-auto' : 'w-full px-2.5 py-1.5 gap-2'
            )}
          >
            {collapsed ? <ChevronRight size={14} /> : (
              <>
                <ChevronLeft size={13} />
                <span>Collapse</span>
              </>
            )}
          </button>
        </div>
      </aside>
    </>
  );
}
