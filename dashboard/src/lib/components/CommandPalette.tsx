'use client';

import { useEffect, useState, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Command } from 'cmdk';
import { motion, AnimatePresence } from 'framer-motion';
import { useHotkeys } from 'react-hotkeys-hook';
import { api, isLoggedIn } from '../api';
import { useAppState } from './AppStateProvider';
import {
  Home, Activity, Settings as SettingsIcon, Plus, Video, Inbox, Search,
  Beaker, Rocket, Power, PowerOff, Sparkles,
} from './Icon';

interface ChannelLite { channel_id: string; channel_name: string; status: string }
interface JobLite { content_id: string; title?: string; channel_name?: string; status?: string }

export function CommandPalette() {
  const router = useRouter();
  const { paletteOpen, setPaletteOpen, envMode, switchEnv, systemStopped, setSystemStopped } = useAppState();
  const [channels, setChannels] = useState<ChannelLite[]>([]);
  const [jobs, setJobs] = useState<JobLite[]>([]);
  const [search, setSearch] = useState('');

  // Toggle on ⌘K / Ctrl+K
  useHotkeys('mod+k', (e) => { e.preventDefault(); setPaletteOpen(!paletteOpen); }, { enableOnFormTags: true });
  useHotkeys('escape', () => { if (paletteOpen) setPaletteOpen(false); }, { enableOnFormTags: true });

  // Lazy-load context when opened
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
    { id: 'nav-dashboard', label: 'Go to Dashboard', icon: Home, run: () => go('/dashboard'), keywords: 'home channels overview' },
    { id: 'nav-progress', label: 'Go to Progress', icon: Activity, run: () => go('/dashboard/progress'), keywords: 'jobs running active queue' },
    { id: 'nav-settings', label: 'Go to Settings', icon: SettingsIcon, run: () => go('/dashboard/settings'), keywords: 'config emergency stop budget' },
    { id: 'nav-new-channel', label: 'Add new channel', icon: Plus, run: () => go('/dashboard/channels/new'), keywords: 'create channel' },
    { id: 'nav-fleet', label: 'Fleet health', icon: Activity, run: () => go('/dashboard/fleet'), keywords: 'fleet health services workers db pool render queue scale' },
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
          transition={{ duration: 0.12 }}
          className="fixed inset-0 z-[200] bg-black/60 backdrop-blur-sm flex items-start justify-center pt-[15vh] px-4"
          onClick={() => setPaletteOpen(false)}
        >
          <motion.div
            key="palette-shell"
            initial={{ opacity: 0, scale: 0.96, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -8 }}
            transition={{ duration: 0.14, ease: 'easeOut' }}
            className="w-full max-w-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <Command
              loop
              label="Command Palette"
              className="bg-surface-0 border border-border rounded-xl shadow-elevated overflow-hidden"
            >
              <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
                <Search size={16} className="text-content-tertiary shrink-0" />
                <Command.Input
                  value={search}
                  onValueChange={setSearch}
                  placeholder="Search channels, jobs, actions…"
                  className="flex-1 bg-transparent text-sm text-content-primary placeholder:text-content-tertiary outline-none"
                />
                <kbd className="hidden sm:inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] text-content-tertiary border border-border bg-surface-1">
                  ESC
                </kbd>
              </div>

              <Command.List className="max-h-[60vh] overflow-y-auto p-2">
                <Command.Empty className="px-3 py-8 text-center text-xs text-content-tertiary">
                  No matches for &ldquo;{search}&rdquo;
                </Command.Empty>

                <Command.Group heading="Navigation" className="text-[10px] uppercase tracking-wider text-content-tertiary px-2 pt-2 pb-1">
                  {navItems.map(({ id, label, icon: Icon, run, keywords }) => (
                    <Command.Item
                      key={id}
                      value={`${label} ${keywords || ''}`}
                      onSelect={run}
                      className="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-content-primary cursor-pointer aria-selected:bg-accent/10 aria-selected:text-accent"
                    >
                      <Icon size={14} className="shrink-0" />
                      <span>{label}</span>
                    </Command.Item>
                  ))}
                </Command.Group>

                {actionItems.length > 0 && (
                  <Command.Group heading="Actions" className="text-[10px] uppercase tracking-wider text-content-tertiary px-2 pt-3 pb-1">
                    {actionItems.map(({ id, label, icon: Icon, run, keywords }) => (
                      <Command.Item
                        key={id}
                        value={`${label} ${keywords || ''}`}
                        onSelect={run}
                        className="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-content-primary cursor-pointer aria-selected:bg-accent/10 aria-selected:text-accent"
                      >
                        <Icon size={14} className="shrink-0" />
                        <span>{label}</span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}

                {channels.length > 0 && (
                  <Command.Group heading="Channels" className="text-[10px] uppercase tracking-wider text-content-tertiary px-2 pt-3 pb-1">
                    {channels.slice(0, 30).map((ch) => (
                      <Command.Item
                        key={`ch-${ch.channel_id}`}
                        value={`channel ${ch.channel_name} ${ch.channel_id}`}
                        onSelect={() => go(`/dashboard/channels/${ch.channel_id}`)}
                        className="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-content-primary cursor-pointer aria-selected:bg-accent/10 aria-selected:text-accent"
                      >
                        <Video size={14} className="shrink-0" />
                        <span className="truncate">{ch.channel_name}</span>
                        <span className="ml-auto text-[10px] text-content-tertiary">{ch.status}</span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}

                {jobs.length > 0 && (
                  <Command.Group heading="Active Jobs" className="text-[10px] uppercase tracking-wider text-content-tertiary px-2 pt-3 pb-1">
                    {jobs.slice(0, 30).map((j) => (
                      <Command.Item
                        key={`job-${j.content_id}`}
                        value={`job ${j.title || ''} ${j.content_id} ${j.channel_name || ''}`}
                        onSelect={() => go(`/dashboard/jobs/${j.content_id}`)}
                        className="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-content-primary cursor-pointer aria-selected:bg-accent/10 aria-selected:text-accent"
                      >
                        <Inbox size={14} className="shrink-0" />
                        <span className="truncate">{j.title || j.content_id}</span>
                        {j.channel_name && (
                          <span className="ml-auto text-[10px] text-content-tertiary truncate max-w-[40%]">{j.channel_name}</span>
                        )}
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}
              </Command.List>

              <div className="flex items-center justify-between px-3 py-2 border-t border-border text-[10px] text-content-tertiary bg-surface-1/40">
                <div className="flex items-center gap-2">
                  <Sparkles size={11} />
                  <span>Command Palette</span>
                </div>
                <div className="flex items-center gap-3">
                  <span><kbd className="px-1 py-0.5 rounded border border-border bg-surface-0">↑↓</kbd> navigate</span>
                  <span><kbd className="px-1 py-0.5 rounded border border-border bg-surface-0">↵</kbd> select</span>
                </div>
              </div>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
