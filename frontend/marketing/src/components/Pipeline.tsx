"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Search, PenLine, AudioLines, Clapperboard, Send } from "lucide-react";
import SectionHeading from "./ui/SectionHeading";
import Reveal from "./ui/Reveal";
import { STAGES, C } from "@/lib/pipeline";
import { cn } from "@/lib/utils";

const ICONS = [Search, PenLine, AudioLines, Clapperboard, Send];

const DETAIL = [
  {
    out: "12 ranked topic angles",
    body: "Gemini scans trends, competitor uploads and your channel's own retention data, then ranks angles by expected CTR.",
    metric: ["Signals", "1.2k / run"],
  },
  {
    out: "Fact-checked script · 9.1 hook",
    body: "Claude writes hook-first, retention-shaped scripts. GPT-4o fact-checks every claim and scores the draft before it moves on.",
    metric: ["Quality gate", "≥ 8.0 / 10"],
  },
  {
    out: "Broadcast narration · -14 LUFS",
    body: "Each channel gets its own consistent voice via Fish Audio. Loudness-normalised, paced to the script's beats.",
    metric: ["Voices", "per channel"],
  },
  {
    out: "1080p60 · captions · thumbnail",
    body: "Remotion composes scenes from 48+ cinematic components, matches b-roll, burns captions and renders A/B thumbnails.",
    metric: ["Components", "48+"],
  },
  {
    out: "Scheduled · SEO · chapters",
    body: "Uploads at the best slot for your audience with optimised title, tags, description and chapters. Analytics feed back into research.",
    metric: ["Platforms", "YouTube"],
  },
];

export default function Pipeline() {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return;
    const id = setInterval(() => setActive((a) => (a + 1) % STAGES.length), 3000);
    return () => clearInterval(id);
  }, [paused]);

  const stage = STAGES[active];
  const Icon = ICONS[active];
  const detail = DETAIL[active];

  return (
    <section id="pipeline" className="section scroll-mt-20">
      <div className="container-x">
        <SectionHeading
          eyebrow="The pipeline"
          title={
            <>
              Five stages. Zero hand-offs.
              <br />
              <span className="text-content-tertiary">Every video, every time.</span>
            </>
          }
          lead="Each stage is run by the model best suited for it, gated by automated quality checks, and visible in your dashboard in real time."
        />

        {/* Stage rail */}
        <Reveal delay={0.1} className="mt-16">
          <div
            className="relative grid grid-cols-5 gap-2 md:gap-4"
            onMouseEnter={() => setPaused(true)}
            onMouseLeave={() => setPaused(false)}
          >
            {/* Connector line */}
            <svg className="absolute left-0 right-0 top-7 h-px w-full pointer-events-none" preserveAspectRatio="none">
              <line x1="10%" y1="0.5" x2="90%" y2="0.5" stroke="rgb(var(--border-hover))" strokeWidth="1" />
              <line
                x1="10%"
                y1="0.5"
                x2="90%"
                y2="0.5"
                stroke={stage.color}
                strokeWidth="1.5"
                strokeDasharray="6 8"
                className="animate-flow-dash"
                style={{ opacity: 0.8 }}
              />
            </svg>

            {STAGES.map((s, i) => {
              const StageIcon = ICONS[i];
              const isActive = i === active;
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setActive(i)}
                  className="relative flex flex-col items-center gap-3 group focus-visible:outline-none"
                  aria-pressed={isActive}
                >
                  <span
                    className={cn(
                      "relative z-10 w-14 h-14 rounded-2xl grid place-items-center border transition-all duration-300",
                      isActive
                        ? "bg-surface-1 border-border-hover shadow-elevated scale-105"
                        : "bg-surface-0 border-border group-hover:border-border-hover"
                    )}
                    style={isActive ? { boxShadow: `0 0 0 1px ${s.color}55, 0 0 28px ${s.color}33` } : undefined}
                  >
                    <StageIcon className="w-5 h-5 transition-colors" style={{ color: isActive ? s.color : C.muted }} />
                    {isActive && (
                      <span
                        className="absolute -inset-1 rounded-[20px] border animate-pulse-soft"
                        style={{ borderColor: `${s.color}66` }}
                      />
                    )}
                  </span>
                  <span className="text-center">
                    <span
                      className={cn(
                        "block text-sm font-semibold transition-colors",
                        isActive ? "text-content-primary" : "text-content-secondary"
                      )}
                    >
                      {s.label}
                    </span>
                    <span className="hidden sm:block font-mono text-[10px] text-content-tertiary mt-0.5">
                      {s.model}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </Reveal>

        {/* Detail panel */}
        <Reveal delay={0.2} className="mt-12">
          <motion.div
            key={stage.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="panel p-6 md:p-8 grid md:grid-cols-[1fr_auto] gap-8 items-center"
          >
            <div>
              <div className="flex items-center gap-3 mb-3">
                <span className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: `${stage.color}22` }}>
                  <Icon className="w-4 h-4" style={{ color: stage.color }} />
                </span>
                <span className="eyebrow">
                  Stage {String(active + 1).padStart(2, "0")} · {stage.model}
                </span>
              </div>
              <h3 className="t-h2 text-content-primary">{detail.out}</h3>
              <p className="mt-3 text-content-secondary max-w-xl leading-relaxed">{detail.body}</p>
            </div>
            <div className="card px-6 py-5 md:min-w-[200px]">
              <p className="eyebrow mb-2">{detail.metric[0]}</p>
              <p className="text-3xl font-bold tracking-tight text-content-primary">{detail.metric[1]}</p>
              <div className="mt-4 flex items-center gap-2">
                {STAGES.map((s, i) => (
                  <span
                    key={s.id}
                    className="h-1 flex-1 rounded-full transition-colors duration-300"
                    style={{ background: i <= active ? s.color : "rgb(var(--surface-3))" }}
                  />
                ))}
              </div>
            </div>
          </motion.div>
        </Reveal>
      </div>
    </section>
  );
}
