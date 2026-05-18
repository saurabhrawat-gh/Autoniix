'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
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
  UserCircle,
  Boxes,
  ChevronDown,
  Check,
} from './Icon';
import { clearToken } from '../api';
import { authApi } from '../api-v2';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { confirmDialog } from './ConfirmDialog';
import { Button } from '../ui';

type Workspace = { id: number; name: string; slug: string; plan: string; role: string; active: boolean };

export function AppHeader() {
  const pathname = usePathname() || '';
  const router = useRouter();
  const { systemStopped, setPaletteOpen, envMode, envSwitching, switchEnv } = useAppState();
  const { showToast } = useToast();
  const [helpOpen, setHelpOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [envConfirmOpen, setEnvConfirmOpen] = useState(false);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [switchingWs, setSwitchingWs] = useState(false);

  useEffect(() => {
    authApi.listWorkspaces()
      .then((res: any) => setWorkspaces(res?.data ?? []))
      .catch(() => {});
  }, []);

  useHotkeys('shift+slash', (e) => { e.preventDefault(); setHelpOpen(v => !v); }, []);
  useHotkeys('escape', () => setHelpOpen(false), []);
  useHotkeys('mod+k', (e) => { e.preventDefault(); setPaletteOpen(true); }, [setPaletteOpen]);
  useHotkeys('n', () => { if (!systemStopped) router.push('/dashboard/channels/new'); }, [systemStopped]);

  async function handleLogout() {
    const ok = await confirmDialog({
      title: 'Sign out?',
      description: 'You will be returned to the login page.',
      destructive: true,
      confirmLabel: 'Sign out',
    });
    if (!ok) return;
    clearToken();
    try { await authApi.logout(); } catch { /* ignore — redirect regardless */ }
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

  async function handleSwitchWorkspace(id: number) {
    if (switchingWs) return;
    setSwitchingWs(true);
    try {
      await authApi.switchWorkspace(id);
      showToast('Workspace switched', 'success');
      window.location.reload();
    } catch (e: any) {
      showToast(e?.message || 'Failed to switch workspace', 'error');
    } finally {
      setSwitchingWs(false);
    }
  }

  return (
    <>
      {/* Thin top bar — logo area (md+: just brand text since sidebar shows logo) + right controls */}
      <header className="shrink-0 h-12 bg-surface-0 border-b border-border px-3 flex items-center gap-3 sticky top-0 z-30">
        {/* Mobile hamburger */}
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={() => setDrawerOpen(true)}
          aria-label="Open menu"
          className="md:hidden w-8 h-8 text-content-secondary"
        >
          <MenuIcon size={18} />
        </Button>

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
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleEnvToggle}
            disabled={envSwitching}
            className={cn(
              'h-7 px-2.5 text-[11px] font-semibold tracking-wider',
              envMode === 'test'
                ? 'border-status-warning/30 bg-status-warning/10 text-status-warning hover:bg-status-warning/15'
                : 'border-status-success/30 bg-status-success/10 text-status-success hover:bg-status-success/15',
              envSwitching && 'cursor-wait'
            )}
          >
            {envMode === 'test' ? <Beaker size={12} /> : <Rocket size={12} />}
            <span className="hidden sm:inline">{envMode === 'test' ? 'TEST' : 'LIVE'}</span>
          </Button>
        </Tip>

        {/* WS status */}
        <WsStatusPill />

        {/* Command palette — icon button only */}
        <Tip text="Search & commands (⌘K)" pos="bottom">
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            onClick={() => setPaletteOpen(true)}
            aria-label="Open command palette"
            className="w-8 h-8 bg-surface-1 hover:bg-surface-2 text-content-secondary hover:text-content-primary"
          >
            <Search size={14} />
          </Button>
        </Tip>

        {/* Theme toggle */}
        <ThemeToggle />

        <NotificationBell />

        <Tip text="Keyboard shortcuts (?)" pos="bottom">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => setHelpOpen(true)}
            aria-label="Keyboard shortcuts"
            className="w-8 h-8 bg-surface-2 hover:bg-surface-3 text-content-secondary hover:text-content-primary"
          >
            <HelpCircle size={14} />
          </Button>
        </Tip>

        {/* Workspace switcher — only visible when user belongs to >1 workspace */}
        {workspaces.length > 1 && (
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-label="Switch workspace"
                disabled={switchingWs}
                className="h-7 px-2 gap-1 text-[11px] font-medium text-content-secondary hover:text-content-primary max-w-[140px]"
              >
                <Boxes size={12} className="shrink-0" />
                <span className="truncate hidden sm:inline">
                  {workspaces.find(w => w.active)?.name ?? 'Workspace'}
                </span>
                <ChevronDown size={10} className="shrink-0" />
              </Button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="end"
                sideOffset={6}
                className="z-[200] min-w-[200px] bg-surface-0 border border-border rounded-xl shadow-lg p-1 text-sm"
              >
                <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-content-tertiary">
                  Your workspaces
                </div>
                {workspaces.map(ws => (
                  <DropdownMenu.Item
                    key={ws.id}
                    onSelect={() => !ws.active && handleSwitchWorkspace(ws.id)}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-content-primary hover:bg-surface-2 outline-none"
                  >
                    <div className="w-5 h-5 rounded bg-accent/10 flex items-center justify-center text-[9px] font-bold text-accent shrink-0">
                      {ws.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="truncate text-xs font-medium">{ws.name}</p>
                      <p className="text-[10px] text-content-tertiary">{ws.role}</p>
                    </div>
                    {ws.active && <Check size={12} className="text-accent shrink-0" />}
                  </DropdownMenu.Item>
                ))}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        )}

        {/* User menu */}
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="User menu"
              className="w-8 h-8 bg-surface-2 hover:bg-surface-3 text-content-secondary hover:text-content-primary"
            >
              <UserCircle size={16} />
            </Button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={6}
              className="z-[200] min-w-[180px] bg-surface-0 border border-border rounded-xl shadow-lg p-1 text-sm"
            >
              <DropdownMenu.Item
                onSelect={() => router.push('/dashboard/profile')}
                className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-content-primary hover:bg-surface-2 outline-none"
              >
                <UserCircle size={14} className="text-content-secondary" />
                Profile &amp; Security
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item
                onSelect={(e) => { e.preventDefault(); handleLogout(); }}
                className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-status-danger hover:bg-status-danger/10 outline-none"
              >
                <LogOut size={14} />
                Sign out
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

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
          <Button
            type="button"
            variant="secondary"
            onClick={() => { setDrawerOpen(false); handleLogout(); }}
            leftIcon={<LogOut size={14} />}
            className="w-full h-9 text-sm font-medium text-content-secondary"
          >
            Sign out
          </Button>
        )}
      />
    </>
  );
}
