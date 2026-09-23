"use client";

import type { ReactNode } from "react";
import { Brain, ShieldCheck, Layers3, UserCheck, LineChart, Blocks, Check } from "lucide-react";
import SectionHeading from "./ui/SectionHeading";
import Reveal from "./ui/Reveal";
import { C } from "@/lib/pipeline";
import { cn } from "@/lib/utils";

/* ─── Mini visuals ─────────────────────────────────────────────────── */
function OrchestrationVisual() {
  const models = ["Gemini", "Claude", "GPT-4o", "Fish", "Veo", "Remotion"];
  return (
    <div className="relative h-52 grid place-items-center overflow-hidden">
      <span className="absolute w-44 h-44 rounded-full border border-border animate-spin-slow" />
      <span className="absolute w-28 h-28 rounded-full border border-dashed border-border-hover animate-spin-slow [animation-direction:reverse]" />
      <span className="relative z-10 w-12 h-12 rounded-2xl bg-brand grid place-items-center text-white font-bold shadow-elevated">
        A
      </span>
      {models.map((m, i) => {
        const a = (i / models.length) * Math.PI * 2 - Math.PI / 2;
        return (
          <span
            key={m}
            className="absolute chip bg-surface-1 border border-border text-content-secondary normal-case tracking-normal"
            style={{ transform: `translate(${Math.cos(a) * 88}px, ${Math.sin(a) * 88}px)` }}
          >
            {m}
          </span>
        );
      })}
      <span className="absolute inset-x-6 top-1/2 h-px bg-gradient-to-r from-transparent via-border-hover to-transparent" />
    </div>
  );
}

function QualityVisual() {
  const gates = [
    ["Script composite", 9.1],
    ["Hook strength", 9.4],
    ["Fact-check", 10],
    ["Voice clarity", 9.0],
    ["Policy compliance", 10],
  ];
  return (
    <div className="space-y-2.5">
      {gates.map(([k, v]) => (
        <div key={k as string} className="flex items-center gap-3 text-[12px]">
          <span className="w-32 shrink-0 text-content-secondary truncate">{k}</span>
          <div className="flex-1 h-1.5 rounded-full bg-surface-2 overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${(v as number) * 10}%`, background: C.success }} />
          </div>
          <span className="font-mono text-content-primary w-8 text-right">{v}</span>
          <Check className="w-3.5 h-3.5" style={{ color: C.success }} />
        </div>
      ))}
    </div>
  );
}

function ScaleVisual() {
  return (
    <div className="grid grid-cols-6 gap-1.5">
      {Array.from({ length: 24 }).map((_, i) => {
        const on = i % 5 !== 3;
        return (
          <div
            key={i}
            className={cn(
              "aspect-[4/3] rounded-md border",
              on ? "bg-surface-1 border-border-hover" : "bg-surface-0 border-border"
            )}
          >
            <div className="h-full p-1.5 flex flex-col justify-between">
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  background: on ? [C.success, C.warning, C.violet, C.info][i % 4] : C.muted,
                  opacity: on ? 1 : 0.3,
                }}
              />
              <span className="h-0.5 rounded-full bg-surface-3 w-3/4" />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ReviewVisual() {
  const steps = ["Research", "Script", "Voice", "Render", "Publish"];
  return (
    <div className="space-y-2">
      {steps.map((s, i) => {
        const mode = i === 1 || i === 4 ? "review" : "auto";
        return (
          <div key={s} className="card px-3 py-2 flex items-center justify-between text-[12px]">
            <span className="text-content-primary">{s}</span>
            <span
              className={cn(
                "chip",
                mode === "review"
                  ? "bg-status-warning/15 text-status-warning"
                  : "bg-status-success/15 text-status-success"
              )}
            >
              {mode === "review" ? "Needs approval" : "Autopilot"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function AnalyticsVisual() {
  const pts = [22, 28, 26, 35, 41, 39, 52, 58, 63, 71, 78, 92];
  const d = pts.map((p, i) => `${(i / (pts.length - 1)) * 100},${100 - p}`).join(" ");
  return (
    <div className="relative h-40">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full">
        <defs>
          <linearGradient id="fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={C.violet} stopOpacity="0.35" />
            <stop offset="100%" stopColor={C.violet} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={`0,100 ${d} 100,100`} fill="url(#fill)" />
        <polyline points={d} fill="none" stroke={C.violet} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="absolute top-2 left-2 chip bg-surface-1 text-content-secondary">Avg retention · +35%</div>
      <div className="absolute bottom-2 right-2 chip bg-surface-1" style={{ color: C.success }}>
        Feeding research loop
      </div>
    </div>
  );
}

function ComponentsVisual() {
  const comps = [
    "KineticTitle",
    "SplitCompare",
    "StatCounter",
    "MapZoom",
    "QuoteCard",
    "LowerThird",
    "ChartReveal",
    "Carousel",
  ];
  const layers: [string, number, number, string][] = [
    ["KineticTitle", 0, 22, C.warning],
    ["B-roll · veo", 10, 60, C.info],
    ["StatCounter", 34, 26, C.violet],
    ["Captions", 0, 100, C.cream],
    ["Voice · Marcus", 0, 100, C.pink],
  ];
  return (
    <div className="space-y-4">
      <div className="space-y-1.5 font-mono text-[10px]">
        {layers.map(([name, start, len, color]) => (
          <div key={name} className="flex items-center gap-3">
            <span className="w-24 shrink-0 text-content-tertiary truncate">{name}</span>
            <div className="flex-1 h-4 rounded bg-surface-2 relative overflow-hidden">
              <div
                className="absolute inset-y-0 rounded"
                style={{
                  left: `${start}%`,
                  width: `${len}%`,
                  background: `${color}66`,
                  boxShadow: `inset 0 0 0 1px ${color}99`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {comps.map((c, i) => (
          <span
            key={c}
            className="chip bg-surface-1 border border-border text-content-secondary normal-case tracking-normal"
            style={{ borderColor: i % 3 === 0 ? `${C.warning}55` : undefined }}
          >
            {`<${c} />`}
          </span>
        ))}
        <span className="chip text-content-tertiary">+40 more</span>
      </div>
    </div>
  );
}

/* ─── Cards ────────────────────────────────────────────────────────── */
type Feature = { icon: typeof Brain; title: string; body: string; visual: ReactNode; span?: string; color: string };

const FEATURES: Feature[] = [
  {
    icon: Brain,
    title: "Multi-model orchestration",
    body: "Ten specialist models, one brain. Each stage gets the model that is best at it — swappable without touching the pipeline.",
    visual: <OrchestrationVisual />,
    span: "md:col-span-2",
    color: C.violet,
  },
  {
    icon: ShieldCheck,
    title: "30+ automated quality gates",
    body: "Nothing publishes under an 8.0 composite. Scripts, voice, visuals and policy are scored before you ever see them.",
    visual: <QualityVisual />,
    color: C.success,
  },
  {
    icon: Layers3,
    title: "One setup, every channel",
    body: "Run 1 or 100 YouTube channels — Shorts and long-form — from one workspace. Same quality, same speed.",
    visual: <ScaleVisual />,
    color: C.info,
  },
  {
    icon: Blocks,
    title: "Code-driven rendering",
    body: "Remotion compositions — 48+ cinematic components — mean zero variability across thousands of renders.",
    visual: <ComponentsVisual />,
    span: "md:col-span-2",
    color: C.warning,
  },
  {
    icon: UserCheck,
    title: "Human-in-the-loop, per stage",
    body: "Autopilot everything or require sign-off before script, voice or publish. Every step pausable and reversible.",
    visual: <ReviewVisual />,
    color: C.warning,
  },
  {
    icon: LineChart,
    title: "Closed-loop analytics",
    body: "Retention, CTR and watch time feed straight back into research, so every next video is informed by the last.",
    visual: <AnalyticsVisual />,
    span: "md:col-span-2",
    color: C.violet,
  },
];

export default function Features() {
  return (
    <section id="features" className="section scroll-mt-20">
      <div className="container-x">
        <SectionHeading
          eyebrow="Why Autoniix"
          title={
            <>
              Built like infrastructure,
              <br />
              <span className="text-content-tertiary">not a prompt box.</span>
            </>
          }
          lead="Generating one video is easy. Shipping hundreds a month at broadcast quality, on schedule, without babysitting — that is what Autoniix is for."
        />

        <div className="mt-16 grid md:grid-cols-3 gap-4">
          {FEATURES.map((f, i) => (
            <Reveal key={f.title} delay={0.05 * i} className={cn("panel card-hover p-6 flex flex-col", f.span)}>
              <div className="flex items-center gap-3 mb-4">
                <span className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: `${f.color}1f` }}>
                  <f.icon className="w-4 h-4" style={{ color: f.color }} />
                </span>
                <h3 className="t-h3 text-content-primary">{f.title}</h3>
              </div>
              <p className="text-sm text-content-secondary leading-relaxed mb-6">{f.body}</p>
              <div className="mt-auto card p-4 bg-surface-bg/50">{f.visual}</div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
