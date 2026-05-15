'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';
import { useHotkeys } from 'react-hotkeys-hook';
import { useAppState } from './AppStateProvider';
import { useToast } from '../toast';
import { Tip } from './Tooltip';
import { ShortcutHelp } from './ShortcutHelp';
import { CommandPalette } from './CommandPalette';
import { NotificationBell } from './NotificationBell';
import { WsStatusPill } from './WsStatusPill';
import { MobileDrawer } from './MobileDrawer';
import { EnvProductionDialog } from './EnvProductionDialog';
import { ThemeToggle } from '../theme';
import { cn } from '../utils';
import {
  Video,
  Activity,
  Settings,
  Plus,
  HelpCircle,
  Search,
  MoreHorizontal as MenuIcon,
  Tv,
  Film,
  ClipboardCheck,
  Plug,
  Bell,
  Home,
  Archive,
  Zap,
  LogOut,
  Beaker,
  Rocket,
} from './Icon';
import { clearToken } from '../api';

export function AppHeader() {
  const pathname = usePathname() || '';
  const router = useRouter();
  const { systemStopped, setPaletteOpen, envMode, envSwitching, switchEnv } = useAppState();
  const { showToast } = useToast();
  const [helpOpen, setHelpOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [envConfirmOpen, setEnvConfirmOpen] = useState(false);

  useHotkeys('shift+slash', (e) => { e.preventDefault(); setHelpOpen(v => !v); }, []);
  useHotkeys('escape', () => setHelpOpen(false), []);
  useHotkeys('mod+k', (e) => { e.preventDefault(); setPaletteOpen(true); }, [setPaletteOpen]);
  useHotkeys('n', () => { if (!systemStopped) router.push('/dashboard/channels/new'); }, [systemStopped]);

  function logout() { clearToken(); router.push('/login'); }

  async function handleEnvToggle() {
    if (envMode === 'test') {
      setEnvConfirmOpen(true);
      return;
    }
    try {
      await switchEnv('test');
      showToast('Switched to TEST mode', 'success');
    } catch (e: any) {
      showToast(e?.message || 'Failed to switch mode', 'error');
    }
  }

  async function confirmProduction() {
    try {
      await switchEnv('production', true);
      setEnvConfirmOpen(false);
      showToast('Switched to PRODUCTION mode', 'success');
    } catch (e: any) {
      showToast(e?.message || 'Failed to switch mode', 'error');
    }
  }

  return (
    <>
      {/* Thin top bar — logo area (md+: just brand text since sidebar shows logo) + right controls */}
      <header className="shrink-0 h-12 bg-surface-0 border-b border-border px-3 flex items-center gap-3 sticky top-0 z-30">
        {/* Mobile hamburger */}
        <button
          onClick={() => setDrawerOpen(true)}
          aria-label="Open menu"
          className="md:hidden w-8 h-8 flex items-center justify-center rounded-md hover:bg-surface-2 text-content-secondary"
        >
          <MenuIcon size={18} />
        </button>

        {/* Mobile brand (visible only on mobile since sidebar has it on desktop) */}
        <Link href="/dashboard" className="md:hidden flex items-center gap-2" aria-label="Home">
          <div className="w-7 h-7 rounded-md bg-accent/10 flex items-center justify-center">
            <Video size={14} className="text-accent" />
          </div>
          <span className="text-sm font-semibold text-content-primary">YT Automation</span>
        </Link>

        {/* Spacer */}
        <div className="flex-1" />

        {/* ENV mode pill */}
        <Tip text={envMode === 'test' ? 'TEST mode — click to switch to Production' : 'PRODUCTION mode — click to switch to Test'} pos="bottom">
          <button
            onClick={handleEnvToggle}
            disabled={envSwitching}
            className={cn(
              'inline-flex items-center gap-1.5 h-7 px-2.5 rounded-md text-[11px] font-semibold tracking-wider transition-colors border',
              envMode === 'test'
                ? 'border-status-warning/30 bg-status-warning/10 text-status-warning hover:bg-status-warning/15'
                : 'border-status-success/30 bg-status-success/10 text-status-success hover:bg-status-success/15',
              envSwitching && 'opacity-50 cursor-wait'
            )}
          >
            {envMode === 'test' ? <Beaker size={12} /> : <Rocket size={12} />}
            <span className="hidden sm:inline">{envMode === 'test' ? 'TEST' : 'LIVE'}</span>
          </button>
        </Tip>

        {/* WS status */}
        <WsStatusPill />

        {/* Command palette — icon button only */}
        <Tip text="Search & commands (⌘K)" pos="bottom">
          <button
            onClick={() => setPaletteOpen(true)}
            aria-label="Open command palette"
            className="w-8 h-8 flex items-center justify-center rounded-md bg-surface-1 hover:bg-surface-2 border border-border text-content-secondary hover:text-content-primary transition-colors"
          >
            <Search size={14} />
          </button>
        </Tip>

        {/* Theme toggle */}
        <ThemeToggle />

        <NotificationBell />

        <Tip text="Keyboard shortcuts (?)" pos="bottom">
          <button
            onClick={() => setHelpOpen(true)}
            aria-label="Keyboard shortcuts"
            className="w-8 h-8 flex items-center justify-center rounded-md bg-surface-2 hover:bg-surface-3 text-content-secondary hover:text-content-primary transition-colors"
          >
            <HelpCircle size={14} />
          </button>
        </Tip>

        {/* Sign out */}
        <Tip text="Sign out" pos="bottom">
          <button
            onClick={logout}
            aria-label="Sign out"
            className="w-8 h-8 flex items-center justify-center rounded-md bg-surface-2 hover:bg-surface-3 text-content-secondary hover:text-content-primary transition-colors"
          >
            <LogOut size={14} />
          </button>
        </Tip>

        {/* Add Channel — styled like Long/Short buttons */}
        {systemStopped ? (
          <Tip text="Resume system from Settings to add channels" pos="bottom">
            <span className="inline-flex items-center justify-center gap-1.5 h-8 w-8 lg:w-auto lg:px-3 rounded-md text-xs font-medium opacity-50 cursor-not-allowed border text-content-tertiary bg-surface-2 border-border">
              <Plus size={14} /> <span className="hidden lg:inline">Add Channel</span>
            </span>
          </Tip>
        ) : (
          <Tip text="Create a new channel (n)" pos="bottom">
            <Link
              href="/dashboard/channels/new"
              aria-label="Add channel"
              className="inline-flex items-center justify-center gap-1.5 h-8 w-8 lg:w-auto lg:px-3 rounded-md text-xs font-medium border text-accent bg-accent/5 border-accent/15 hover:bg-accent/10 transition-colors"
            >
              <Plus size={14} /> <span className="hidden lg:inline">Add Channel</span>
            </Link>
          </Tip>
        )}
      </header>

      <EnvProductionDialog
        open={envConfirmOpen}
        switching={envSwitching}
        onCancel={() => setEnvConfirmOpen(false)}
        onConfirm={confirmProduction}
      />

      <ShortcutHelp open={helpOpen} onClose={() => setHelpOpen(false)} />
      <CommandPalette />
      <MobileDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        items={[
          { href: '/dashboard', label: 'Home', icon: Home, active: pathname === '/dashboard' },
          { href: '/dashboard/channels', label: 'Channels', icon: Tv, active: pathname.startsWith('/dashboard/channels') },
          { href: '/dashboard/content', label: 'Content', icon: Film, active: pathname.startsWith('/dashboard/content') },
          { href: '/dashboard/library', label: 'Library', icon: Archive, active: pathname.startsWith('/dashboard/library') },
          { href: '/dashboard/experiments', label: 'Experiments', icon: Zap, active: pathname.startsWith('/dashboard/experiments') },
          { href: '/dashboard/providers', label: 'Providers', icon: Plug, active: pathname.startsWith('/dashboard/providers') },
          { href: '/dashboard/progress', label: 'Progress', icon: Activity, active: pathname.startsWith('/dashboard/progress') || pathname.startsWith('/dashboard/jobs') },
          { href: '/dashboard/settings', label: 'Settings', icon: Settings, active: pathname.startsWith('/dashboard/settings') },
          { href: '/dashboard/channels/new', label: 'Add Channel', icon: Plus },
        ]}
        footer={(
          <button
            onClick={() => { setDrawerOpen(false); logout(); }}
            className="w-full inline-flex items-center justify-center gap-2 h-9 rounded-md bg-surface-2 hover:bg-surface-3 text-sm font-medium text-content-secondary"
          >
            <LogOut size={14} /> Sign out
          </button>
        )}
      />
    </>
  );
}
