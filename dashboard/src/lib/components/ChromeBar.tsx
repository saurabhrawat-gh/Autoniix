'use client';

/**
 * ChromeBar — slim 40px top strip rendered above the sidebar+content row.
 *
 * Per locked feedback (2026-06-18):
 *   • Breadcrumb moved out of the chrome → now rendered by `<PageBreadcrumb />`
 *     at the top of the floating content card.
 *   • Search button moved into the sidebar AppBrand row.
 *   • Help (?) and User menu moved into the sidebar bottom utility row.
 *   • WsStatus is now a dot-only indicator (no text pill).
 *   • Theme toggle is the right-most affordance.
 *
 * What stays here:
 *   • Mobile hamburger (md+ shows the sidebar instead).
 *   • Right cluster: status-dot, NotificationBell, ThemeToggle.
 *   • Global modals it anchors: ShortcutHelp, CommandPalette, MobileDrawer.
 *     Trigger state lives in AppStateProvider so the sidebar buttons can
 *     toggle them without prop-drilling.
 */

import { usePathname } from 'next/navigation';
import { useState } from 'react';
import { useHotkeys } from 'react-hotkeys-hook';
import { useAppState } from './AppStateProvider';
import { ShortcutHelp } from './ShortcutHelp';
import { CommandPalette } from './CommandPalette';
import { NotificationBell } from './NotificationBell';
import { WsStatusPill } from './WsStatusPill';
import { MobileDrawer } from './MobileDrawer';
import { ThemeToggle, ThemePicker } from '../theme';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Tip } from './Tooltip';
import {
  MoreHorizontal as MenuIcon,
  Home,
  Tv,
  Film,
  Archive,
  Zap,
  Plug,
  Activity,
  Settings,
  Plus,
  LogOut,
  HelpCircle,
  UserCircle,
} from './Icon';
import { clearToken } from '../api';
import { confirmDialog } from './ConfirmDialog';
import { authApi } from '../api-v2';
import { useRouter } from 'next/navigation';

export function ChromeBar() {
  const pathname = usePathname() || '';
  const router = useRouter();
  const { setPaletteOpen, helpOpen, setHelpOpen } = useAppState();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Global hotkeys are bound here because ChromeBar is mounted layout-wide.
  useHotkeys('shift+slash', (e) => { e.preventDefault(); setHelpOpen(!helpOpen); }, [helpOpen, setHelpOpen]);
  useHotkeys('escape', () => setHelpOpen(false), [setHelpOpen]);
  useHotkeys('mod+k', (e) => { e.preventDefault(); setPaletteOpen(true); }, [setPaletteOpen]);

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

  const chromeBtn =
    'inline-flex items-center justify-center w-7 h-7 rounded-md text-content-tertiary ' +
    'hover:bg-surface-2 hover:text-content-primary transition-colors ' +
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40';

  return (
    <>
      <header
        className="h-10 shrink-0 flex items-center px-3 bg-transparent select-none"
        aria-label="Application chrome"
      >
        {/* Mobile hamburger — sidebar is hidden below md so we need this here. */}
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          aria-label="Open menu"
          className={`md:hidden ${chromeBtn}`}
        >
          <MenuIcon size={14} />
        </button>

        {/* Spacer pushes the right cluster to the extreme right. */}
        <div className="flex-1" />

        {/* Right cluster — order is locked: status, notifications, help, user,
            theme. Theme toggle MUST be the right-most affordance.
            Help & user live here (not the sidebar bottom) so they remain easy
            to reach in collapsed-sidebar mode where the sidebar bottom would
            be too cramped. */}
        <div className="flex items-center gap-0.5 shrink-0">
          <WsStatusPill />
          <NotificationBell />
          <Tip text="Keyboard shortcuts · ?" pos="bottom">
            <button
              type="button"
              onClick={() => setHelpOpen(true)}
              aria-label="Keyboard shortcuts"
              className={chromeBtn}
            >
              <HelpCircle size={14} />
            </button>
          </Tip>
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button
                type="button"
                aria-label="User menu"
                className={chromeBtn}
              >
                <UserCircle size={14} />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="end"
                sideOffset={6}
                className="z-[200] min-w-[180px] bg-surface-0 border border-border rounded-xl shadow-elevated p-1 text-sm"
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
                  className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-status-error hover:bg-status-error/10 outline-none"
                >
                  <LogOut size={14} />
                  Sign out
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
          <ThemePicker />
          <ThemeToggle />
        </div>
      </header>

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
            type="button"
            onClick={() => { setDrawerOpen(false); handleLogout(); }}
            className="w-full h-9 inline-flex items-center justify-center gap-2 rounded-md bg-surface-2 text-content-secondary hover:text-content-primary text-sm font-medium"
          >
            <LogOut size={14} />
            Sign out
          </button>
        )}
      />
    </>
  );
}
