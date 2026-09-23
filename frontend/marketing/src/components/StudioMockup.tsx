"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Play, Pause, Volume2, Maximize2, Check, Loader2, Clock, Sparkles, Youtube } from "lucide-react";
import { STAGES, JOBS, C } from "@/lib/pipeline";
import { cn } from "@/lib/utils";

/* ─── Scenes shown in the preview — cycles with the render ─────────── */
const SCENES = [
  {
    caption: "Compound interest is the eighth wonder of the world.",
    hue: "from-[#1c1740] via-[#2a2160] to-[#0e0c1c]",
    tag: "Hook · 0:00",
  },
  {
    caption: "A $100 investment at 8% doubles roughly every nine years.",
    hue: "from-[#0f1f2f] via-[#1b3552] to-[#0b1219]",
    tag: "Scene 2 · 0:14",
  },
  {
    caption: "Time matters more than the amount you start with.",
    hue: "from-[#2a1526] via-[#4a2140] to-[#150a12]",
    tag: "Scene 3 · 0:31",
  },
  {
    caption: "Start now. Your future self is watching.",
    hue: "from-[#1a2414] via-[#2b3d1f] to-[#0c110a]",
    tag: "CTA · 0:48",
  },
];

const LOG_POOL = [
  { who: "research", text: "12 trending angles ranked · picked #2 (score 8.7)" },
  { who: "script", text: "draft v3 · hook strength 9.1 · 612 words · fact-check ✓" },
  { who: "qc", text: "policy compliance ✓ · retention model +32% vs baseline" },
  { who: "voice", text: "narration synthesised · 3:42 · profile “Marcus” · -14 LUFS" },
  { who: "render", text: "Remotion · 1080p60 · 47 comps · scene 3/4 compositing" },
  { who: "render", text: "b-roll matched 11/11 · captions burned · thumbnail A/B ready" },
  { who: "publish", text: "scheduled 18:00 local · SEO title + tags · chapters added" },
];

const WHO_COLOR: Record<string, string> = {
  research: C.info,
  script: C.violet,
  qc: C.cream,
  voice: C.pink,
  render: C.warning,
  publish: C.success,
};

function useTicker(ms: number) {
  const [t, setT] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setT((v) => v + 1), ms);
    return () => clearInterval(id);
  }, [ms]);
  return t;
}

/* ─── Left: job queue ──────────────────────────────────────────────── */
function JobQueue({ tick }: { tick: number }) {
  const jobs = useMemo(
    () =>
      JOBS.slice(0, 5).map((j, i) => ({
        ...j,
        progress: Math.min(99, (j.progress + tick * (3 + i)) % 100),
      })),
    [tick]
  );

  return (
    <aside className="hidden lg:flex flex-col w-60 shrink-0 border-r border-border bg-surface-bg/40">
      <div className="px-4 h-10 flex items-center justify-between border-b border-border">
        <span className="eyebrow">Queue</span>
        <span className="chip bg-status-success/15 text-status-success">
          <span className="w-1.5 h-1.5 rounded-full bg-status-success animate-pulse" />
          {jobs.length} live
        </span>
      </div>
      <ul className="p-2 space-y-1">
        {jobs.map((job, i) => {
          const stage = STAGES[job.stage];
          const active = i === 0;
          return (
            <li
              key={job.title}
              className={cn(
                "rounded-lg px-3 py-2.5 border transition-colors",
                active ? "bg-surface-1 border-border-hover" : "border-transparent hover:bg-surface-1/60"
              )}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: stage.color }} />
                <p className="text-[12px] font-medium text-content-primary truncate">{job.title}</p>
              </div>
              <div className="flex items-center justify-between text-[10px] font-mono text-content-tertiary mb-1.5">
                <span className="truncate">{job.channel}</span>
                <span style={{ color: stage.color }}>{stage.label}</span>
              </div>
              <div className="h-[3px] rounded-full bg-surface-2 overflow-hidden">
                <div
                  className="h-full rounded-full transition-[width] duration-1000 ease-out"
                  style={{ width: `${job.progress}%`, background: stage.color }}
                />
              </div>
            </li>
          );
        })}
      </ul>
      <div className="mt-auto p-3 border-t border-border grid grid-cols-2 gap-2">
        {[
          ["Today", "47 published"],
          ["Avg QC", "9.4 / 10"],
        ].map(([k, v]) => (
          <div key={k} className="card px-2.5 py-2">
            <p className="text-[10px] font-mono text-content-tertiary">{k}</p>
            <p className="text-[12px] font-semibold text-content-primary">{v}</p>
          </div>
        ))}
      </div>
    </aside>
  );
}

/* ─── Centre: video preview + timeline ─────────────────────────────── */
function Preview({ tick }: { tick: number }) {
  const scene = SCENES[tick % SCENES.length];
  const playhead = ((tick % SCENES.length) + 0.5) / SCENES.length;
  const [playing, setPlaying] = useState(true);

  return (
    <div className="flex-1 min-w-0 flex flex-col">
      {/* Phase stepper — mirrors the dashboard's PhaseStepper */}
      <div className="h-10 px-4 flex items-center gap-1 border-b border-border overflow-x-auto">
        {STAGES.map((s, i) => {
          const state = i < 3 ? "done" : i === 3 ? "active" : "todo";
          return (
            <div key={s.id} className="flex items-center">
              <div
                className={cn(
                  "flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium",
                  state === "active" ? "bg-surface-1 text-content-primary" : "text-content-tertiary"
                )}
              >
                {state === "done" ? (
                  <Check className="w-3 h-3" style={{ color: C.success }} />
                ) : state === "active" ? (
                  <Loader2 className="w-3 h-3 animate-spin" style={{ color: s.color }} />
                ) : (
                  <Clock className="w-3 h-3 opacity-50" />
                )}
                {s.label}
              </div>
              {i < STAGES.length - 1 && <span className="w-4 h-px bg-border mx-0.5" />}
            </div>
          );
        })}
      </div>

      {/* Frame */}
      <div className="p-4 md:p-5 flex-1 flex flex-col gap-3">
        <div className="relative aspect-video rounded-xl overflow-hidden border border-border bg-black shadow-elevated">
          <AnimatePresence mode="wait">
            <motion.div
              key={scene.caption}
              initial={{ opacity: 0, scale: 1.04 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              className={cn("absolute inset-0 bg-gradient-to-br", scene.hue)}
            >
              <div className="absolute inset-0 dot-bg opacity-30" />
              <div className="absolute -right-10 -top-10 w-56 h-56 rounded-full bg-brand opacity-25 blur-3xl animate-float-slow" />
              <div
                className="absolute left-8 bottom-16 w-40 h-40 rounded-full opacity-20 blur-3xl"
                style={{ background: C.info }}
              />
            </motion.div>
          </AnimatePresence>

          {/* Scanline sweep */}
          <div className="absolute inset-x-0 h-24 bg-gradient-to-b from-transparent via-white/[0.04] to-transparent animate-scan pointer-events-none" />

          {/* Overlays */}
          <div className="absolute top-3 left-3 flex items-center gap-2">
            <span className="chip bg-black/50 text-content-primary backdrop-blur">{scene.tag}</span>
            <span className="chip bg-black/50 backdrop-blur" style={{ color: C.warning }}>
              <Sparkles className="w-3 h-3" /> AI B-roll
            </span>
          </div>
          <div className="absolute top-3 right-3 chip bg-black/50 text-content-secondary backdrop-blur">
            1080p · 60fps
          </div>

          <AnimatePresence mode="wait">
            <motion.p
              key={scene.caption}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.45 }}
              className="absolute left-1/2 -translate-x-1/2 bottom-12 md:bottom-14 max-w-[85%] text-center text-white font-bold text-sm md:text-xl leading-snug tracking-tight drop-shadow-[0_2px_12px_rgba(0,0,0,0.6)]"
            >
              {scene.caption}
            </motion.p>
          </AnimatePresence>

          {/* Player controls */}
          <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-black/70 to-transparent">
            <div className="h-1 rounded-full bg-white/15 overflow-hidden mb-2">
              <div
                className="h-full bg-white rounded-full transition-[width] duration-1000"
                style={{ width: `${playhead * 100}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-white/80">
              <div className="flex items-center gap-3">
                <button type="button" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "Pause" : "Play"}>
                  {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </button>
                <Volume2 className="w-4 h-4" />
                <span className="font-mono text-[11px]">
                  0:{String(14 * (tick % SCENES.length)).padStart(2, "0")} / 3:42
                </span>
              </div>
              <Maximize2 className="w-4 h-4" />
            </div>
          </div>
        </div>

        {/* Timeline */}
        <div className="card p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="eyebrow">Timeline</span>
            <span className="font-mono text-[10px] text-content-tertiary">
              4 scenes · 11 b-roll · 1 voice · 1 music
            </span>
          </div>
          <div className="relative space-y-1.5">
            <div
              className="absolute top-0 bottom-0 w-px bg-accent z-10 transition-[left] duration-1000"
              style={{ left: `${playhead * 100}%` }}
            >
              <span className="absolute -top-1 -translate-x-1/2 w-2 h-2 rounded-full bg-accent" />
            </div>
            {/* Video track */}
            <div className="grid grid-cols-4 gap-1 h-7">
              {SCENES.map((s, i) => (
                <div
                  key={s.tag}
                  className={cn(
                    "rounded-md bg-gradient-to-br border border-white/5",
                    s.hue,
                    i === tick % SCENES.length && "ring-1 ring-accent/60"
                  )}
                />
              ))}
            </div>
            {/* Voice waveform */}
            <div className="h-6 rounded-md bg-surface-2 flex items-center gap-[2px] px-2 overflow-hidden">
              {Array.from({ length: 64 }).map((_, i) => (
                <span
                  key={i}
                  className="flex-1 rounded-sm"
                  style={{
                    height: `${20 + Math.abs(Math.sin(i * 0.7 + tick)) * 80}%`,
                    background: C.pink,
                    opacity: i / 64 < playhead ? 0.9 : 0.3,
                    transition: "height 0.8s ease",
                  }}
                />
              ))}
            </div>
            {/* Music */}
            <div className="h-3 rounded-md bg-surface-2 relative overflow-hidden">
              <div
                className="absolute inset-y-0 left-0 w-full opacity-40"
                style={{ background: `linear-gradient(90deg, ${C.info}, transparent)` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Right: agent activity log ────────────────────────────────────── */
function AgentLog({ tick }: { tick: number }) {
  const lines = useMemo(() => {
    const n = Math.min(LOG_POOL.length, 4 + (tick % 4));
    return LOG_POOL.slice(0, n).map((l, i) => ({ ...l, i }));
  }, [tick]);

  return (
    <aside className="hidden xl:flex flex-col w-72 shrink-0 border-l border-border bg-surface-bg/40 font-mono">
      <div className="px-4 h-10 flex items-center justify-between border-b border-border">
        <span className="eyebrow">Agent log</span>
        <span className="text-[10px] text-content-tertiary">job #4821</span>
      </div>
      <ul className="p-3 space-y-2.5 text-[11px] leading-relaxed">
        <AnimatePresence initial={false}>
          {lines.map((l) => (
            <motion.li
              key={l.i}
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.35 }}
              className="flex gap-2"
            >
              <span className="shrink-0 w-14 text-right" style={{ color: WHO_COLOR[l.who] }}>
                {l.who}
              </span>
              <span className="text-content-secondary">{l.text}</span>
            </motion.li>
          ))}
        </AnimatePresence>
        <li className="flex gap-2 text-content-tertiary">
          <span className="w-14" />
          <span className="inline-block w-1.5 h-3.5 bg-accent/70 animate-pulse" />
        </li>
      </ul>
      <div className="mt-auto p-3 border-t border-border">
        <div className="card p-3 flex items-center gap-3">
          <span className="w-8 h-8 rounded-lg grid place-items-center bg-status-error/15">
            <Youtube className="w-4 h-4 text-status-error" />
          </span>
          <div className="min-w-0">
            <p className="text-[11px] text-content-primary truncate">Money Simplified</p>
            <p className="text-[10px] text-content-tertiary">publishes in 02:14:36</p>
          </div>
        </div>
      </div>
    </aside>
  );
}

/* ─── Shell ────────────────────────────────────────────────────────── */
export default function StudioMockup() {
  const tick = useTicker(2600);

  return (
    <div className="window relative text-left">
      <div className="window-bar">
        <span className="window-dot" />
        <span className="window-dot" />
        <span className="window-dot" />
        <div className="ml-3 hidden sm:flex items-center gap-1.5 font-mono text-[11px] text-content-tertiary">
          <span>Money Simplified</span>
          <span className="opacity-40">/</span>
          <span>Jobs</span>
          <span className="opacity-40">/</span>
          <span className="text-content-secondary">#4821</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="chip bg-status-warning/15 text-status-warning">
            <Loader2 className="w-3 h-3 animate-spin" /> Rendering · 78%
          </span>
          <span className="hidden sm:inline chip bg-surface-1 text-content-secondary">Autopilot on</span>
        </div>
      </div>
      <div className="flex min-h-[420px]">
        <JobQueue tick={tick} />
        <Preview tick={tick} />
        <AgentLog tick={tick} />
      </div>
    </div>
  );
}
