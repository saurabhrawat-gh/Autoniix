'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { Button } from './ui';

export type Theme = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

const ThemeContext = createContext<{
  theme: Theme;
  resolved: ResolvedTheme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
}>({ theme: 'system', resolved: 'light', setTheme: () => {}, toggle: () => {} });

function resolve(theme: Theme): ResolvedTheme {
  if (theme === 'system') {
    if (typeof window === 'undefined') return 'light';
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return theme;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('system');
  const [resolved, setResolved] = useState<ResolvedTheme>('light');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem('theme') as Theme | null;
    const initial: Theme = stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
    setThemeState(initial);
    const r = resolve(initial);
    setResolved(r);
    document.documentElement.classList.toggle('dark', r === 'dark');
    setMounted(true);
  }, []);

  // Re-resolve on OS preference change while in 'system' mode
  useEffect(() => {
    if (theme !== 'system' || typeof window === 'undefined') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => {
      const r: ResolvedTheme = mq.matches ? 'dark' : 'light';
      setResolved(r);
      document.documentElement.classList.toggle('dark', r === 'dark');
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [theme]);

  function setTheme(next: Theme) {
    setThemeState(next);
    localStorage.setItem('theme', next);
    const r = resolve(next);
    setResolved(r);
    document.documentElement.classList.toggle('dark', r === 'dark');
  }

  function toggle() {
    // Cycle: light → dark → system → light
    const next: Theme = theme === 'light' ? 'dark' : theme === 'dark' ? 'system' : 'light';
    setTheme(next);
  }

  if (!mounted) return null;

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}

export function HomeLogo() {
  return (
    <a href="/dashboard" className="flex items-center gap-2 group" title="Back to Dashboard">
      <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center group-hover:bg-accent/20 transition-colors">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="text-accent">
          <path d="M23 7l-7 5 7 5V7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <rect x="1" y="5" width="15" height="14" rx="2" stroke="currentColor" strokeWidth="2"/>
        </svg>
      </div>
    </a>
  );
}

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const next: Theme = theme === 'light' ? 'dark' : theme === 'dark' ? 'system' : 'light';

  const icon = theme === 'light' ? (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  ) : theme === 'dark' ? (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  ) : (
    // System (monitor) icon
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  );

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      onClick={toggle}
      className="w-8 h-8 bg-surface-2 hover:bg-surface-3 text-content-secondary hover:text-content-primary"
      aria-label={`Theme: ${theme}. Click to switch to ${next}.`}
      title={`Theme: ${theme} — click for ${next}`}
    >
      {icon}
    </Button>
  );
}
