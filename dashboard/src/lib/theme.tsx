'use client';

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Button } from './ui';

export type Theme = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';
export type ColorTheme = 'default' | 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j';

export const COLOR_THEMES: {
  id: ColorTheme;
  name: string;
  desc: string;
  accent: string;
  surface: string;
  fav?: boolean;
}[] = [
  { id: 'default', name: 'V5 Default',     desc: 'Moss green · Cream',          accent: '#3d5c1a', surface: '#f5f5f5' },
  { id: 'a',       name: 'Void + Indigo',  desc: 'Ultra-premium precision',      accent: '#5B4CF5', surface: '#F8F8FC' },
  { id: 'b',       name: 'Evolved',        desc: 'Green/cream DNA · refined',    accent: '#2D6A2D', surface: '#F5F6F2', fav: true },
  { id: 'c',       name: 'Studio Ember',   desc: 'Creator-first · warm orange',  accent: '#C2410C', surface: '#FAFAF8' },
  { id: 'd',       name: 'Abyss + Teal',  desc: 'B2B enterprise · data-forward', accent: '#0D9488', surface: '#F7FAFB' },
  { id: 'e',       name: 'Pastel Aurora', desc: 'Dream-like · Arc energy',       accent: '#7C5CF0', surface: '#FAF8FF' },
  { id: 'f',       name: 'Warm Carbon',   desc: 'Cozy peach · carbon shell',     accent: '#C06030', surface: '#FFFAF7' },
  { id: 'g',       name: 'Deep Navy',     desc: 'Navy + gold · premium B2B',     accent: '#8C6800', surface: '#F8F8FF' },
  { id: 'h',       name: 'Electric Lime', desc: 'Charcoal · neon lime',          accent: '#4A8800', surface: '#F8F8F8' },
  { id: 'i',       name: 'Rose Quartz',   desc: 'Warm pastel · blush tones',     accent: '#C04070', surface: '#FFF8FA' },
  { id: 'j',       name: 'Slate + Copper',desc: 'Neutral slate · warm copper',   accent: '#8B4513', surface: '#F8F9FA' },
];

const ThemeContext = createContext<{
  theme: Theme;
  resolved: ResolvedTheme;
  colorTheme: ColorTheme;
  setTheme: (t: Theme) => void;
  setColorTheme: (c: ColorTheme) => void;
  toggle: () => void;
}>({ theme: 'system', resolved: 'light', colorTheme: 'default', setTheme: () => {}, setColorTheme: () => {}, toggle: () => {} });

function resolve(theme: Theme): ResolvedTheme {
  if (theme === 'system') {
    if (typeof window === 'undefined') return 'light';
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return theme;
}

const VALID_COLOR_THEMES: ColorTheme[] = ['default','a','b','c','d','e','f','g','h','i','j'];

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('system');
  const [resolved, setResolved] = useState<ResolvedTheme>('light');
  const [colorTheme, setColorThemeState] = useState<ColorTheme>('default');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem('theme') as Theme | null;
    const initial: Theme = stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
    setThemeState(initial);
    const r = resolve(initial);
    setResolved(r);
    document.documentElement.classList.toggle('dark', r === 'dark');

    const storedColor = localStorage.getItem('color-theme') as ColorTheme | null;
    const initialColor: ColorTheme = storedColor && VALID_COLOR_THEMES.includes(storedColor) ? storedColor : 'default';
    setColorThemeState(initialColor);
    if (initialColor === 'default') {
      document.documentElement.removeAttribute('data-color-theme');
    } else {
      document.documentElement.setAttribute('data-color-theme', initialColor);
    }

    setMounted(true);
  }, []);

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

  function setColorTheme(next: ColorTheme) {
    setColorThemeState(next);
    localStorage.setItem('color-theme', next);
    if (next === 'default') {
      document.documentElement.removeAttribute('data-color-theme');
    } else {
      document.documentElement.setAttribute('data-color-theme', next);
    }
  }

  function toggle() {
    const next: Theme = theme === 'light' ? 'dark' : theme === 'dark' ? 'system' : 'light';
    setTheme(next);
  }

  if (!mounted) return null;

  return (
    <ThemeContext.Provider value={{ theme, resolved, colorTheme, setTheme, setColorTheme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}

export function ThemePicker() {
  const { colorTheme, setColorTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const active = COLOR_THEMES.find(t => t.id === colorTheme) ?? COLOR_THEMES[0];

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="inline-flex items-center gap-1.5 h-7 px-2 rounded-md text-content-tertiary hover:bg-surface-2 hover:text-content-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 text-xs font-medium"
        title="Change color theme"
        aria-label="Color theme picker"
      >
        <span
          className="w-3 h-3 rounded-full flex-shrink-0 ring-1 ring-black/10"
          style={{ background: active.accent }}
        />
        <span className="hidden sm:inline">{active.name}</span>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" className="opacity-50">
          <path d="M1 3l4 4 4-4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-72 rounded-xl border border-border bg-surface-0 shadow-elevated p-3 z-50">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-content-tertiary mb-2.5 px-0.5">Color theme</p>
          <div className="grid grid-cols-2 gap-1.5">
            {COLOR_THEMES.map(t => {
              const isActive = colorTheme === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => { setColorTheme(t.id); setOpen(false); }}
                  className={[
                    'flex items-center gap-2 px-2.5 py-2 rounded-lg text-left transition-all border text-xs',
                    isActive
                      ? 'border-accent/40 bg-accent/8 text-content-primary'
                      : 'border-transparent hover:bg-surface-1 text-content-secondary hover:text-content-primary',
                  ].join(' ')}
                >
                  <span className="flex gap-0.5 flex-shrink-0">
                    <span className="w-4 h-4 rounded-md ring-1 ring-black/10" style={{ background: t.surface }} />
                    <span className="w-4 h-4 rounded-md ring-1 ring-black/10" style={{ background: t.accent }} />
                  </span>
                  <span className="flex flex-col min-w-0">
                    <span className="font-medium truncate leading-tight flex items-center gap-1">
                      {t.name}
                      {t.fav && <span className="text-[9px] text-yellow-500">★</span>}
                    </span>
                  </span>
                  {isActive && (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="ml-auto flex-shrink-0 text-accent">
                      <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
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
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  ) : (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  );

  return (
    <button
      type="button"
      onClick={toggle}
      className="inline-flex items-center justify-center w-7 h-7 rounded-md text-content-tertiary hover:bg-surface-2 hover:text-content-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
      aria-label={`Theme: ${theme}. Click to switch to ${next}.`}
      title={`Theme: ${theme} — click for ${next}`}
    >
      {icon}
    </button>
  );
}
