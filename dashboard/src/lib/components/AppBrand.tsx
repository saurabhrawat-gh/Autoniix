'use client';

/**
 * AppBrand — the persistent Autoniix product identity at the top of the sidebar.
 *
 * Linear-style placement: a tiny gradient mark + the product name "Autoniix",
 * always visible regardless of which workspace is active. Sits ABOVE the
 * WorkspaceSwitcher so the user can always tell which app they're in (per
 * locked feedback: "I can't see the place to put 'Autoniix icon and name'").
 *
 * Clicking the brand row navigates to /dashboard (Home), matching the
 * convention of every other shell where the logo doubles as a home link.
 */

import Link from 'next/link';
import { Search } from 'lucide-react';
import { Tip } from './Tooltip';
import { useAppState } from './AppStateProvider';

export function AppBrandMark({ size = 20 }: { size?: number }) {
  return (
    <span
      aria-hidden="true"
      className="rounded-md shrink-0 grid place-items-center text-white font-bold select-none"
      style={{
        width: size,
        height: size,
        background: 'linear-gradient(135deg, #8A56FF 0%, #FF6FB5 100%)',
        fontSize: Math.max(10, Math.round(size * 0.52)),
        letterSpacing: '0.01em',
        boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.08)',
      }}
    >
      A
    </span>
  );
}

export function AppBrand({ collapsed }: { collapsed: boolean }) {
  const { setPaletteOpen } = useAppState();

  if (collapsed) {
    return (
      <Tip text="Autoniix · Home" pos="right">
        <Link
          href="/dashboard"
          aria-label="Autoniix — go to Home"
          className="group flex items-center justify-center mx-auto w-9 h-9 rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
        >
          <AppBrandMark size={22} />
        </Link>
      </Tip>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <Link
        href="/dashboard"
        aria-label="Autoniix — go to Home"
        className="group flex items-center gap-2 flex-1 min-w-0 rounded-md px-2 py-1 hover:bg-surface-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
      >
        <AppBrandMark size={20} />
        <span className="text-[13.5px] font-semibold tracking-tight text-content-primary truncate">
          Autoniix
        </span>
      </Link>
      <Tip text="Search & commands · ⌘K" pos="bottom">
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          aria-label="Open command palette"
          className="shrink-0 inline-flex items-center justify-center w-7 h-7 rounded-md text-content-tertiary hover:bg-surface-2 hover:text-content-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
        >
          <Search size={14} />
        </button>
      </Tip>
    </div>
  );
}
