'use client';

import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Command } from 'cmdk';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { useHotkeys } from 'react-hotkeys-hook';
import { api, isLoggedIn } from '../api';
import { useAppState } from './AppStateProvider';
import {
  Home, Activity, Settings as SettingsIcon, Plus, Video, Inbox, Search,
  Beaker, Rocket, Power, PowerOff, Sparkles,
  Archive, Zap, Film, ClipboardCheck, Tv, Plug,
} from './Icon';
import { Kbd } from '@/lib/ui';

const TYPEWRITER_PHRASES = [
  'Search channels...',
  'Find failed jobs...',
  'Trigger content...',
  'Check queue...',
] as const;

interface ChannelLite { channel_id: string; channel_name: string; status: string }
interface JobLite { content_id: string; title?: string; channel_name?: string; status?: string }

export function CommandPalette() {
  const router = useRouter();
  const reduce = useReducedMotion();
  const { paletteOpen, setPaletteOpen, envMode, switchEnv, systemStopped, setSystemStopped } = useAppState();
  const [channels, setChannels] = useState<ChannelLite[]>([]);
  const [jobs, setJobs] = useState<JobLite[]>([]);
  const [search, setSearch] = useState('');

  const [phIdx, setPhIdx]   = useState(0);
  const [phChars, setPhChars] = useState(0);
  const [inputFocused, setInputFocused] = useState(false);

  const [ripplingId, setRipplingId] = useState<string | null>(null);
  const pendingAction = useRef<(() => void) | null>(null);

  useHotkeys('mod+k', (e) => { e.preventDefault(); setPaletteOpen(!paletteOpen); }, { enableOnFormTags: true });
  useHotkeys('escape', () => { if (paletteOpen) setPaletteOpen(false); }, { enableOnFormTags: true });

  useEffect(() => {
    if (!paletteOpen || !isLoggedIn()) return;
    let cancelled = false;
    (async () => {
      try {
        const [chRes, jobsRes] = await Promise.all([
          api.channels().catch(() => null),
          api.activeJobs().catch(() => null),
        ]);
        if (cancelled) return;
        if (chRes?.data) setChannels(chRes.data);
        if (jobsRes?.data) setJobs(jobsRes.data);
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [paletteOpen]);

  useEffect(() => {
    if (!paletteOpen || search !== '' || inputFocused || reduce) return;
    const phrase = TYPEWRITER_PHRASES[phIdx];
    if (phChars < phrase.length) {
      const t = setTimeout(() => setPhChars((c) => c + 1), 38);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => {
      setPhIdx((i) => (i + 1) % TYPEWRITER_PHRASES.length);
      setPhChars(0);
    }, 2500);
    return () => clearTimeout(t);
  }, [paletteOpen, phIdx, phChars, search, inputFocused, reduce]);

  useEffect(() => {
    if (!paletteOpen) { setPhIdx(0); setPhChars(0); setSearch(''); }
  }, [paletteOpen]);

  const twPlaceholder = search !== '' || inputFocused
    ? ''
    : TYPEWRITER_PHRASES[phIdx].slice(0, phChars);

  function withRipple(id: string, action: () => void) {
    if (reduce) { action(); return; }
    setRipplingId(id);
    pendingAction.current = action;
    setTimeout(() => {
      setRipplingId(null);
      pendingAction.current?.();
      pendingAction.current = null;
    }, 280);
  }

  const go = useCallback((href: string) => {
    setPaletteOpen(false);
    setSearch('');
    router.push(href);
  }, [router, setPaletteOpen]);

  const runAction = useCallback(async (fn: () => Promise<void> | void) => {
    setPaletteOpen(false);
    setSearch('');
    try { await fn(); } catch {}
  }, [setPaletteOpen]);

  const navItems = useMemo(() => ([
    { id: 'nav-dashboard', label: 'Go to Home', icon: Home, run: () => go('/dashboard'), keywords: 'home overview dashboard' },
    { id: 'nav-channels', label: 'Go to Channels', icon: Tv, run: () => go('/dashboard/channels'), keywords: 'channels list manage trigger' },
    { id: 'nav-content', label: 'Go to Content', icon: Film, run: () => go('/dashboard/content'), keywords: 'videos pipeline kanban calendar review approve' },
    { id: 'nav-library', label: 'Go to Library', icon: Archive, run: () => go('/dashboard/library'), keywords: 'assets music brand stock media files' },
    { id: 'nav-progress', label: 'Go to Progress', icon: Activity, run: () => go('/dashboard/progress'), keywords: 'jobs running active queue render' },
    { id: 'nav-experiments', label: 'Go to Experiments', icon: Zap, run: () => go('/dashboard/experiments'), keywords: 'ab test experiments variants split test' },
    { id: 'nav-providers', label: 'Go to Providers', icon: Plug, run: () => go('/dashboard/providers'), keywords: 'providers credentials api keys vault' },
    { id: 'nav-settings', label: 'Go to Settings', icon: SettingsIcon, run: () => go('/dashboard/settings'), keywords: 'config emergency stop budget' },
    { id: 'nav-new-channel', label: 'Add new channel', icon: Plus, run: () => go('/dashboard/channels/new'), keywords: 'create channel new' },
  ]), [go]);

  const actionItems = useMemo(() => {
    const items: Array<{ id: string; label: string; icon: any; run: () => any; keywords?: string }> = [];
    if (envMode === 'production') {
      items.push({ id: 'env-test', label: 'Switch to TEST mode', icon: Beaker, run: () => runAction(() => switchEnv('test')), keywords: 'environment mock free' });
    } else {
      items.push({ id: 'env-prod', label: 'Switch to PRODUCTION mode (paid APIs)', icon: Rocket, run: () => runAction(() => switchEnv('production', true)), keywords: 'environment paid live youtube upload' });
    }
    if (systemStopped) {
      items.push({ id: 'sys-resume', label: 'Resume system', icon: Power, run: () => runAction(async () => {
        await api.emergencyResume();
        setSystemStopped(false);
      }), keywords: 'unfreeze restart' });
    } else {
      items.push({ id: 'sys-stop', label: 'Emergency Stop (freeze system)', icon: PowerOff, run: () => runAction(async () => {
        await api.emergencyStop();
        setSystemStopped(true);
      }), keywords: 'freeze halt panic' });
    }
    return items;
  }, [envMode, systemStopped, switchEnv, setSystemStopped, runAction]);

  return (
    <AnimatePresence>
      {paletteOpen && (
        <motion.div
          key="palette-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12, ease: [0.2, 0, 0, 1] }}
          className="fixed inset-0 z-[200] bg-black/60 backdrop-blur-sm flex items-start justify-center pt-[15vh] px-4"
          onClick={() => setPaletteOpen(false)}
        >
          <motion.div
            key="palette-shell"
            initial={{ opacity: 0, scale: 0.98, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: -8 }}
            transition={{ duration: 0.12, ease: [0.12, 0, 0.1, 1] }}
            className="w-full max-w-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <Command
              loop
              label="Command Palette"
              className="bg-surface-0 border border-border rounded-xl shadow-elevated overflow-hidden"
            >
              <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border bg-surface-0">
                <Search size={18} className="text-content-tertiary shrink-0 ml-1" />
                <Command.Input
                  value={search}
                  onValueChange={setSearch}
                  placeholder={twPlaceholder || 'Search channels, jobs, actions…'}
                  onFocus={() => setInputFocused(true)}
                  onBlur={() => setInputFocused(false)}
                  className="flex-1 bg-transparent text-[15px] text-content-primary placeholder:text-content-tertiary outline-none font-normal"
                />
                <Kbd className="hidden sm:inline-flex h-6 px-2 text-[11px]">ESC</Kbd>
              </div>

              <Command.List className="max-h-[60vh] overflow-y-auto p-2 scrollbar-hide">
                <Command.Empty className="px-3 py-8 text-center text-xs text-content-tertiary">
                  No matches for &ldquo;{search}&rdquo;
                </Command.Empty>

                <Command.Group heading="Navigation" className="text-[10px] uppercase tracking-wider text-content-tertiary px-2 pt-2 pb-1">
                  {navItems.map(({ id, label, icon: Icon, run, keywords }, i) => (
                    <Command.Item
                      key={id}
                      value={`${label} ${keywords || ''}`}
                      onSelect={() => withRipple(id, run)}
                      className="relative overflow-hidden flex items-center gap-2 px-3 py-2 rounded-md text-sm text-content-primary cursor-pointer aria-selected:bg-accent/10 aria-selected:text-accent"
                    >
                      <motion.span
                        className="contents"
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.12, delay: i * 0.02 }}
                      >
                        <Icon size={14} className="shrink-0" />
                        <span>{label}</span>
                      </motion.span>
                      <AnimatePresence>
                        {ripplingId === id && (
                          <motion.span
                            className="absolute inset-0 rounded-md bg-accent/20"
                            initial={{ opacity: 0.6, scale: 0.6 }}
                            animate={{ opacity: 0, scale: 2 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.28 }}
                          />
                        )}
                      </AnimatePresence>
                    </Command.Item>
                  ))}
                </Command.Group>

                {actionItems.length > 0 && (
                  <Command.Group heading="Actions" className="text-[10px] uppercase tracking-wider text-content-tertiary px-2 pt-3 pb-1">
                    {actionItems.map(({ id, label, icon: Icon, run, keywords }, i) => (
                      <Command.Item
                        key={id}
                        value={`${label} ${keywords || ''}`}
                        onSelect={() => withRipple(id, run)}
                        className="relative overflow-hidden flex items-center gap-2 px-3 py-2 rounded-md text-sm text-content-primary cursor-pointer aria-selected:bg-accent/10 aria-selected:text-accent"
                      >
                        <motion.span
                          className="contents"
                          initial={{ opacity: 0, y: 4 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.12, delay: i * 0.02 }}
                        >
                          <Icon size={14} className="shrink-0" />
                          <span>{label}</span>
                        </motion.span>
                        <AnimatePresence>
                          {ripplingId === id && (
                            <motion.span
                              className="absolute inset-0 rounded-md bg-accent/20"
                              initial={{ opacity: 0.6, scale: 0.6 }}
                              animate={{ opacity: 0, scale: 2 }}
                              exit={{ opacity: 0 }}
                              transition={{ duration: 0.28 }}
                            />
                          )}
                        </AnimatePresence>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}

                {channels.length > 0 && (
                  <Command.Group heading="Channels" className="text-[10px] uppercase tracking-wider text-content-tertiary px-2 pt-3 pb-1">
                    {channels.slice(0, 30).map((ch, i) => (
                      <Command.Item
                        key={`ch-${ch.channel_id}`}
                        value={`channel ${ch.channel_name} ${ch.channel_id}`}
                        onSelect={() => withRipple(`ch-${ch.channel_id}`, () => go(`/dashboard/channels/${ch.channel_id}`))}
                        className="relative overflow-hidden flex items-center gap-2 px-3 py-2 rounded-md text-sm text-content-primary cursor-pointer aria-selected:bg-accent/10 aria-selected:text-accent"
                      >
                        <motion.span
                          className="contents"
                          initial={{ opacity: 0, y: 4 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.12, delay: i * 0.02 }}
                        >
                          <Video size={14} className="shrink-0" />
                          <span className="truncate">{ch.channel_name}</span>
                          <span className="ml-auto text-[10px] text-content-tertiary">{ch.status}</span>
                        </motion.span>
                        <AnimatePresence>
                          {ripplingId === `ch-${ch.channel_id}` && (
                            <motion.span
                              className="absolute inset-0 rounded-md bg-accent/20"
                              initial={{ opacity: 0.6, scale: 0.6 }}
                              animate={{ opacity: 0, scale: 2 }}
                              exit={{ opacity: 0 }}
                              transition={{ duration: 0.28 }}
                            />
                          )}
                        </AnimatePresence>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}

                {jobs.length > 0 && (
                  <Command.Group heading="Active Jobs" className="text-[10px] uppercase tracking-wider text-content-tertiary px-2 pt-3 pb-1">
                    {jobs.slice(0, 30).map((j, i) => (
                      <Command.Item
                        key={`job-${j.content_id}`}
                        value={`job ${j.title || ''} ${j.content_id} ${j.channel_name || ''}`}
                        onSelect={() => withRipple(`job-${j.content_id}`, () => go(`/dashboard/jobs/${j.content_id}`))}
                        className="relative overflow-hidden flex items-center gap-2 px-3 py-2 rounded-md text-sm text-content-primary cursor-pointer aria-selected:bg-accent/10 aria-selected:text-accent"
                      >
                        <motion.span
                          className="contents"
                          initial={{ opacity: 0, y: 4 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.12, delay: i * 0.02 }}
                        >
                          <Inbox size={14} className="shrink-0" />
                          <span className="truncate">{j.title || j.content_id}</span>
                          {j.channel_name && (
                            <span className="ml-auto text-[10px] text-content-tertiary truncate max-w-[40%]">{j.channel_name}</span>
                          )}
                        </motion.span>
                        <AnimatePresence>
                          {ripplingId === `job-${j.content_id}` && (
                            <motion.span
                              className="absolute inset-0 rounded-md bg-accent/20"
                              initial={{ opacity: 0.6, scale: 0.6 }}
                              animate={{ opacity: 0, scale: 2 }}
                              exit={{ opacity: 0 }}
                              transition={{ duration: 0.28 }}
                            />
                          )}
                        </AnimatePresence>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}
              </Command.List>

              <div className="flex items-center justify-between px-4 py-2.5 border-t border-border text-xs text-content-secondary bg-surface-1/40 font-medium">
                <div className="flex items-center gap-2">
                  <Sparkles size={13} />
                  <span>Command Palette</span>
                </div>
                <div className="flex items-center gap-4">
                  <span><Kbd>↑↓</Kbd> navigate</span>
                  <span><Kbd>↵</Kbd> select</span>
                </div>
              </div>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
