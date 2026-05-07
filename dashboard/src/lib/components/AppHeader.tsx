'use client';

import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import { useState } from 'react';
import { useHotkeys } from 'react-hotkeys-hook';
import type { LucideIcon } from 'lucide-react';
import { ThemeToggle } from '../theme';
import { clearToken } from '../api';
import { useToast } from '../toast';
import { cn } from '../utils';
import { useAppState } from './AppStateProvider';
import { Tip } from './Tooltip';
import { ShortcutHelp } from './ShortcutHelp';
import { EnvProductionDialog } from './EnvProductionDialog';
import { CommandPalette } from './CommandPalette';
import { NotificationBell } from './NotificationBell';
import { WsStatusPill } from './WsStatusPill';
import { MobileDrawer } from './MobileDrawer';
import {
  Video,
  Activity,
  Settings,
  Plus,
  LogOut,
  HelpCircle,
  Beaker,
  Rocket,
  Search,
  MoreHorizontal as MenuIcon,
} from './Icon';

interface NavLinkProps {
  href: string;
  label: string;
  icon: LucideIcon;
  active: boolean;
  shortcut?: string;
}

function NavLink({ href, label, icon: Icon, active, shortcut }: NavLinkProps) {
  return (
    <Tip text={shortcut ? `${label} · g ${shortcut}` : label} pos="bottom">
      <Link
        href={href}
        className={cn(
          'inline-flex items-center gap-1.5 h-8 px-2.5 rounded-lg text-xs font-medium transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40',
          active
            ? 'bg-accent/10 text-accent'
            : 'text-content-secondary hover:text-content-primary hover:bg-surface-2',
        )}
      >
        <Icon size={14} />
        <span className="hidden md:inline">{label}</span>
      </Link>
    </Tip>
  );
}

export function AppHeader() {
  const router = useRouter();
  const pathname = usePathname() || '';
  const { envMode, envSwitching, systemStopped, switchEnv, setPaletteOpen } = useAppState();
  const { showToast } = useToast();
  const [helpOpen, setHelpOpen] = useState(false);
  const [envConfirmOpen, setEnvConfirmOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [gPressed, setGPressed] = useState(false);

  const isActive = (path: string) => {
    if (path === '/dashboard') return pathname === '/dashboard';
    return pathname.startsWith(path);
  };

  // ── Keyboard shortcuts ────────────────────────────────────────────
  useHotkeys('shift+slash', (e) => { e.preventDefault(); setHelpOpen((v) => !v); }, []);
  useHotkeys('escape', () => { setHelpOpen(false); setEnvConfirmOpen(false); }, []);
  useHotkeys('g', () => { setGPressed(true); setTimeout(() => setGPressed(false), 1200); }, []);
  useHotkeys('d', () => { if (gPressed) { setGPressed(false); router.push('/dashboard'); } }, [gPressed, router]);
  useHotkeys('p', () => { if (gPressed) { setGPressed(false); router.push('/dashboard/progress'); } }, [gPressed, router]);
  useHotkeys('s', () => { if (gPressed) { setGPressed(false); router.push('/dashboard/settings'); } }, [gPressed, router]);
  useHotkeys('n', () => { if (!systemStopped) router.push('/dashboard/channels/new'); }, [systemStopped, router]);

  // Close drawer on route change
  // (covered by Link onClick in MobileDrawer; nothing to do here)

  function logout() {
    clearToken();
    router.push('/login');
  }

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
      <header className="shrink-0 bg-surface-0 border-b border-border px-4 sm:px-6 py-3 sticky top-0 z-30">
        <div className="max-w-[1400px] mx-auto flex items-center justify-between gap-3">
          {/* Mobile hamburger */}
          <button
            onClick={() => setDrawerOpen(true)}
            aria-label="Open menu"
            className="md:hidden w-8 h-8 flex items-center justify-center rounded-lg hover:bg-surface-2 text-content-secondary"
          >
            <MenuIcon size={18} />
          </button>

          {/* Brand */}
          <Link href="/dashboard" className="flex items-center gap-2 group shrink-0" aria-label="YouTube Automation home">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center group-hover:bg-accent/20 transition-colors">
              <Video size={16} className="text-accent" />
            </div>
            <span className="text-sm font-semibold text-content-primary hidden lg:inline">
              YouTube Automation
            </span>
          </Link>

          {/* Primary nav (desktop) */}
          <nav className="hidden md:flex items-center gap-1 ml-2">
            <NavLink href="/dashboard" label="Dashboard" icon={Video} active={isActive('/dashboard') && !pathname.startsWith('/dashboard/progress') && !pathname.startsWith('/dashboard/settings') && !pathname.startsWith('/dashboard/channels') && !pathname.startsWith('/dashboard/jobs')} shortcut="d" />
            <NavLink href="/dashboard/progress" label="Progress" icon={Activity} active={pathname.startsWith('/dashboard/progress') || pathname.startsWith('/dashboard/jobs')} shortcut="p" />
            <NavLink href="/dashboard/settings" label="Settings" icon={Settings} active={pathname.startsWith('/dashboard/settings')} shortcut="s" />
          </nav>

          {/* WS status (always on right of nav) */}
          <div className="hidden sm:block ml-2">
            <WsStatusPill />
          </div>

          {/* Right side */}
          <div className="flex items-center gap-2 ml-auto">
            {/* Command palette trigger */}
            <Tip text="Search & commands (⌘K)" pos="bottom">
              <button
                onClick={() => setPaletteOpen(true)}
                aria-label="Open command palette"
                className="hidden sm:inline-flex items-center gap-2 h-8 px-2.5 rounded-lg text-xs text-content-tertiary bg-surface-1 hover:bg-surface-2 border border-border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
              >
                <Search size={12} />
                <span className="hidden lg:inline">Search…</span>
                <kbd className="hidden lg:inline-flex items-center px-1 py-0.5 rounded text-[9px] border border-border bg-surface-0">⌘K</kbd>
              </button>
            </Tip>
            <Tip text="Search & commands (⌘K)" pos="bottom">
              <button
                onClick={() => setPaletteOpen(true)}
                aria-label="Open command palette"
                className="sm:hidden w-8 h-8 flex items-center justify-center rounded-lg bg-surface-2 hover:bg-surface-3 text-content-secondary"
              >
                <Search size={14} />
              </button>
            </Tip>

            <NotificationBell />
            <Tip
              text={envMode === 'test'
                ? 'Test mode: free/mock providers, no uploads'
                : 'Production mode: paid APIs, YouTube uploads'}
              pos="bottom"
            >
              <div className="flex items-center gap-2">
                <span className={cn('text-[10px] font-semibold flex items-center gap-1', envMode === 'test' ? 'text-amber-400' : 'text-content-tertiary')}>
                  <Beaker size={11} />
                  <span className="hidden sm:inline">TEST</span>
                </span>
                <button
                  onClick={handleEnvToggle}
                  disabled={envSwitching}
                  className={cn(
                    'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                    envMode === 'production' ? 'bg-emerald-500' : 'bg-amber-500',
                    envSwitching && 'opacity-50 cursor-wait',
                  )}
                  role="switch"
                  aria-checked={envMode === 'production'}
                  aria-label="Toggle environment mode"
                >
                  <span
                    className={cn(
                      'inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform',
                      envMode === 'production' ? 'translate-x-[18px]' : 'translate-x-[3px]',
                    )}
                  />
                </button>
                <span className={cn('text-[10px] font-semibold flex items-center gap-1', envMode === 'production' ? 'text-emerald-400' : 'text-content-tertiary')}>
                  <Rocket size={11} />
                  <span className="hidden sm:inline">PROD</span>
                </span>
              </div>
            </Tip>

            <ThemeToggle />

            <Tip text="Keyboard shortcuts (?)" pos="bottom">
              <button
                onClick={() => setHelpOpen(true)}
                aria-label="Keyboard shortcuts"
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface-2 hover:bg-surface-3 text-content-secondary hover:text-content-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
              >
                <HelpCircle size={14} />
              </button>
            </Tip>

            {systemStopped ? (
              <Tip text="Resume system from Settings to add channels" pos="bottom">
                <span className="inline-flex items-center gap-1 h-8 px-3 rounded-lg text-xs font-medium opacity-50 cursor-not-allowed bg-accent text-white">
                  <Plus size={14} /> <span className="hidden sm:inline">Add Channel</span>
                </span>
              </Tip>
            ) : (
              <Tip text="Create a new channel (n)" pos="bottom">
                <Link
                  href="/dashboard/channels/new"
                  className="inline-flex items-center gap-1 h-8 px-3 rounded-lg text-xs font-medium bg-accent text-white hover:opacity-90 transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
                >
                  <Plus size={14} /> <span className="hidden sm:inline">Add Channel</span>
                </Link>
              </Tip>
            )}

            <Tip text="Sign out" pos="bottom">
              <button
                onClick={logout}
                aria-label="Logout"
                className="w-8 h-8 flex items-center justify-center rounded-lg text-content-tertiary hover:text-content-primary hover:bg-surface-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
              >
                <LogOut size={14} />
              </button>
            </Tip>
          </div>
        </div>
      </header>

      <ShortcutHelp open={helpOpen} onClose={() => setHelpOpen(false)} />
      <EnvProductionDialog
        open={envConfirmOpen}
        switching={envSwitching}
        onCancel={() => setEnvConfirmOpen(false)}
        onConfirm={confirmProduction}
      />
      <CommandPalette />
      <MobileDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        items={[
          { href: '/dashboard', label: 'Dashboard', icon: Video, active: isActive('/dashboard') && !pathname.startsWith('/dashboard/progress') && !pathname.startsWith('/dashboard/settings') && !pathname.startsWith('/dashboard/channels') && !pathname.startsWith('/dashboard/jobs') },
          { href: '/dashboard/progress', label: 'Progress', icon: Activity, active: pathname.startsWith('/dashboard/progress') || pathname.startsWith('/dashboard/jobs') },
          { href: '/dashboard/settings', label: 'Settings', icon: Settings, active: pathname.startsWith('/dashboard/settings') },
          { href: '/dashboard/channels/new', label: 'Add Channel', icon: Plus },
        ]}
        footer={(
          <button
            onClick={() => { setDrawerOpen(false); logout(); }}
            className="w-full inline-flex items-center justify-center gap-2 h-9 rounded-lg bg-surface-2 hover:bg-surface-3 text-sm font-medium text-content-secondary"
          >
            <LogOut size={14} /> Sign out
          </button>
        )}
      />
    </>
  );
}
