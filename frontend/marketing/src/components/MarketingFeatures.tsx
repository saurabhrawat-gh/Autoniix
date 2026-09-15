"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";

/* ─── Visual: Orchestration diagram (Ten Models, One Brain) ────── */
function AutopilotVisual({ accent }: { accent: string }) {
  const models = [
    { name: "Gemini", role: "Research", color: "#00D89F", angle: -90 },
    { name: "Claude", role: "Script", color: "#7C3AED", angle: -30 },
    { name: "GPT-4o", role: "Fact-check", color: "#06B6D4", angle: 30 },
    { name: "Fish", role: "Voice", color: "#F59E0B", angle: 90 },
    { name: "Veo", role: "Render", color: "#EC4899", angle: 150 },
    { name: "FFmpeg", role: "Encode", color: "#3B82F6", angle: 210 },
  ];
  const cx = 200,
    cy = 180,
    r = 120;

  return (
    <div className="relative w-full" style={{ aspectRatio: "1.1 / 1" }}>
      <svg viewBox="0 0 400 360" className="w-full h-full">
        <defs>
          <radialGradient id="brainGrad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={accent} stopOpacity="0.55" />
            <stop offset="60%" stopColor={accent} stopOpacity="0.18" />
            <stop offset="100%" stopColor={accent} stopOpacity="0" />
          </radialGradient>
          <linearGradient id="edgeGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={accent} stopOpacity="0.05" />
            <stop offset="50%" stopColor={accent} stopOpacity="0.45" />
            <stop offset="100%" stopColor={accent} stopOpacity="0.05" />
          </linearGradient>
        </defs>

        {/* Outer glow ring */}
        <circle cx={cx} cy={cy} r={r + 30} fill="url(#brainGrad)" opacity="0.6" />

        {/* Connection lines + flowing particles */}
        {models.map((m, i) => {
          const rad = (m.angle * Math.PI) / 180;
          const x = cx + Math.cos(rad) * r;
          const y = cy + Math.sin(rad) * r;
          return (
            <g key={m.name}>
              <line
                x1={cx}
                y1={cy}
                x2={x}
                y2={y}
                stroke="url(#edgeGrad)"
                strokeWidth="1.2"
                strokeDasharray="3 4"
                style={{ animation: `flowDash 2.4s linear infinite ${i * 0.3}s` }}
              />
              <circle r="2.5" fill={m.color} opacity="0.85">
                <animateMotion
                  dur="3s"
                  repeatCount="indefinite"
                  begin={`${i * 0.5}s`}
                  path={`M${cx},${cy} L${x},${y}`}
                />
              </circle>
            </g>
          );
        })}

        {/* Central brain */}
        <circle cx={cx} cy={cy} r="44" fill={`${accent}10`} stroke={accent} strokeWidth="1.2" />
        <circle cx={cx} cy={cy} r="28" fill={`${accent}22`} />
        <circle cx={cx} cy={cy} r="14" fill={accent}>
          <animate attributeName="r" values="14;18;14" dur="2.8s" repeatCount="indefinite" />
        </circle>
        <text
          x={cx}
          y={cy + 4}
          textAnchor="middle"
          fontSize="10"
          fontFamily="var(--font-mono)"
          fontWeight="600"
          fill="#FFFFFF"
        >
          BRAIN
        </text>

        {/* Outer model nodes */}
        {models.map((m) => {
          const rad = (m.angle * Math.PI) / 180;
          const x = cx + Math.cos(rad) * r;
          const y = cy + Math.sin(rad) * r;
          return (
            <g key={m.name}>
              <circle
                cx={x}
                cy={y}
                r="22"
                stroke={m.color}
                strokeWidth="1.5"
                style={{ fill: "var(--bg-card-elevated)" }}
              />
              <circle cx={x} cy={y} r="6" fill={m.color}>
                <animate attributeName="opacity" values="1;0.4;1" dur="2.4s" repeatCount="indefinite" />
              </circle>
              <text
                x={x}
                y={y + 38}
                textAnchor="middle"
                fontSize="10"
                fontWeight="500"
                fontFamily="var(--font-google-sans)"
                style={{ fill: "var(--text-primary)" }}
              >
                {m.name}
              </text>
              <text
                x={x}
                y={y + 50}
                textAnchor="middle"
                fontSize="8"
                fontFamily="var(--font-mono)"
                letterSpacing="0.05em"
                style={{ fill: "var(--text-muted)" }}
              >
                {m.role.toUpperCase()}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Floating status pill */}
      <div
        className="absolute bottom-2 left-1/2 -translate-x-1/2 inline-flex items-center gap-2 px-3 py-1.5 rounded-full t-micro border"
        style={{
          background: "var(--bg-card)",
          borderColor: "var(--border)",
          color: "var(--text-muted)",
          backdropFilter: "blur(8px)",
        }}
      >
        <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: accent }} />
        ALL MODELS NOMINAL · 99.9% UPTIME
      </div>
    </div>
  );
}

/* ─── Visual: Quality dial + comparison bars ──────────────── */
function ContentQualityVisual({ accent }: { accent: string }) {
  const score = 9.4;
  const circumference = 2 * Math.PI * 60;
  const offset = circumference - (score / 10) * circumference;

  const metrics = [
    { label: "Avg retention", before: 38, after: 73, suffix: "%" },
    { label: "Click-through", before: 21, after: 87, suffix: "%" },
    { label: "Quality score", before: 41, after: 94, suffix: "%" },
  ];

  return (
    <div className="relative w-full">
      <div className="grid grid-cols-2 gap-6 items-center">
        {/* Big circular dial */}
        <div className="relative flex items-center justify-center" style={{ minHeight: 180 }}>
          <svg viewBox="0 0 160 160" className="w-44 h-44">
            <defs>
              <linearGradient id="dialGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor={accent} />
                <stop offset="100%" stopColor={accent} stopOpacity="0.65" />
              </linearGradient>
            </defs>
            <circle cx="80" cy="80" r="60" fill="none" strokeWidth="6" style={{ stroke: "var(--border-strong)" }} />
            <motion.circle
              cx="80"
              cy="80"
              r="60"
              fill="none"
              stroke="url(#dialGrad)"
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              whileInView={{ strokeDashoffset: offset }}
              viewport={{ once: true }}
              transition={{ duration: 1.6, ease: [0.16, 1, 0.3, 1] }}
              transform="rotate(-90 80 80)"
            />
          </svg>
          <div className="absolute flex flex-col items-center">
            <span className="t-micro" style={{ color: "var(--text-muted)" }}>
              QUALITY
            </span>
            <span
              style={{
                color: "var(--text-primary)",
                fontSize: "2.5rem",
                fontWeight: 500,
                letterSpacing: "-0.04em",
                lineHeight: 1,
              }}
            >
              9.4
            </span>
            <span className="t-micro" style={{ color: accent }}>
              OUT OF 10
            </span>
          </div>
        </div>

        {/* Comparison bars */}
        <div className="space-y-4">
          <div className="t-eyebrow" style={{ color: "var(--text-muted)" }}>
            AI vs Manual
          </div>
          {metrics.map((m, i) => (
            <div key={m.label}>
              <div className="flex items-center justify-between mb-1.5 t-micro">
                <span style={{ color: "var(--text-muted)" }}>{m.label}</span>
                <span style={{ color: accent }}>
                  +{m.after - m.before}
                  {m.suffix}
                </span>
              </div>
              <div className="relative h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                <div
                  className="absolute inset-y-0 left-0 rounded-full"
                  style={{ width: `${m.before}%`, background: "var(--text-faint)" }}
                />
                <motion.div
                  className="absolute inset-y-0 left-0 rounded-full"
                  style={{ background: `linear-gradient(90deg, ${accent}, var(--accent))` }}
                  initial={{ width: 0 }}
                  whileInView={{ width: `${m.after}%` }}
                  viewport={{ once: true }}
                  transition={{ duration: 1.2, delay: 0.2 + i * 0.1, ease: [0.16, 1, 0.3, 1] }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─── Visual: Scale stack ─────────────────────────────────── */
function ScaleDemoVisual({ accent }: { accent: string }) {
  const tiers = [
    { label: "1 channel", videos: 4, color: "#00D89F" },
    { label: "10 channels", videos: 40, color: "#7C3AED" },
    { label: "50 channels", videos: 200, color: "#06B6D4" },
    { label: "100 channels", videos: 400, color: "#F59E0B" },
  ];
  return (
    <div>
      <div className="t-eyebrow mb-4" style={{ color: "var(--text-muted)" }}>
        OUTPUT VOLUME · MONTHLY VIDEOS
      </div>
      <div className="space-y-3">
        {tiers.map((tier, i) => (
          <motion.div
            key={tier.label}
            initial={{ opacity: 0, x: -12 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
            className="rounded-xl border p-3"
            style={{ borderColor: "var(--border)", background: "var(--bg-card)" }}
          >
            <div className="flex items-center justify-between mb-1.5 t-body-sm">
              <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>{tier.label}</span>
              <span className="t-micro" style={{ color: tier.color }}>
                {tier.videos} VIDEOS / MO
              </span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
              <motion.div
                className="h-full rounded-full"
                style={{ background: `linear-gradient(90deg, ${tier.color}99, ${tier.color})` }}
                initial={{ width: "0%" }}
                whileInView={{ width: `${(tier.videos / 400) * 100}%` }}
                viewport={{ once: true }}
                transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1], delay: 0.2 + i * 0.1 }}
              />
            </div>
          </motion.div>
        ))}
      </div>
      <div
        className="mt-4 rounded-xl px-4 py-3 border flex items-center gap-3"
        style={{
          borderColor: `${accent}40`,
          background: `${accent}0A`,
        }}
      >
        <div style={{ fontSize: "2rem", color: accent, fontWeight: 500, lineHeight: 1 }}>∞</div>
        <div>
          <p className="t-body-sm" style={{ color: "var(--text-primary)", fontWeight: 500 }}>
            No hard limit
          </p>
          <p className="t-micro" style={{ color: "var(--text-muted)" }}>
            SCALE ANY VOLUME ON ENTERPRISE
          </p>
        </div>
      </div>
    </div>
  );
}

/* ─── Visual: Approval workflow ring ──────────────────────── */
function HumanLoopVisual({ accent }: { accent: string }) {
  const steps = [
    { label: "AI generates", status: "done", color: "#00D89F" },
    { label: "Quality gate ≥ 8.5", status: "done", color: "#00D89F" },
    { label: "Human review (opt.)", status: "pending", color: accent },
    { label: "Render + publish", status: "queued", color: "#7C3AED" },
  ];
  return (
    <div>
      <div className="t-eyebrow mb-4" style={{ color: "var(--text-muted)" }}>
        APPROVAL WORKFLOW · CONFIGURABLE
      </div>
      <div className="relative">
        <div className="absolute left-3.5 top-4 bottom-4 w-px" style={{ background: "var(--border)" }} />
        <div className="space-y-4">
          {steps.map((step, i) => (
            <motion.div
              key={step.label}
              initial={{ opacity: 0, x: -12 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.12 }}
              className="flex items-center gap-4"
            >
              <div
                className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center border z-10 relative"
                style={{
                  background: step.status === "queued" ? "var(--bg-card)" : `${step.color}20`,
                  borderColor: step.status === "queued" ? "var(--border-strong)" : `${step.color}60`,
                }}
              >
                {step.status === "done" && (
                  <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                    <path
                      d="M2.5 6L5 8.5L9.5 3.5"
                      stroke={step.color}
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                )}
                {step.status === "pending" && (
                  <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: step.color }} />
                )}
                {step.status === "queued" && (
                  <div className="w-2 h-2 rounded-full" style={{ background: "var(--text-faint)" }} />
                )}
              </div>
              <div className="flex-1">
                <p
                  className="t-body-sm"
                  style={{
                    color: step.status === "queued" ? "var(--text-muted)" : "var(--text-primary)",
                    fontWeight: 500,
                  }}
                >
                  {step.label}
                </p>
              </div>
              <span
                className="t-micro px-2 py-0.5 rounded"
                style={{ color: step.color, background: `${step.color}15` }}
              >
                {step.status}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
      <div className="mt-4 t-micro pt-4 border-t" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
        HUMAN REVIEW IS <span style={{ color: accent }}>OPTIONAL</span> — DISABLE IT AND EVERYTHING SHIPS AUTOMATICALLY.
      </div>
    </div>
  );
}

/* ─── Section data ───────────────────────────────────────── */
const SECTIONS = [
  {
    id: "autopilot",
    eyebrow: "AI Orchestration",
    headline: "Ten models.",
    headline2: "One brain.",
    subtext:
      "Autoniix doesn't use a single AI — it orchestrates a team of specialist models, each best-in-class for its role. Result: content no single model could produce alone.",
    accent: "#00A876",
    accentDark: "#00D89F",
    visual: AutopilotVisual,
    reverse: false,
    stat: { value: "10+", label: "Specialist models" },
  },
  {
    id: "quality",
    eyebrow: "Content Quality",
    headline: "Not just fast.",
    headline2: "Actually good.",
    subtext:
      "Every script is fact-checked, hook-optimised, and quality-scored before it touches your audience. Average score: 9.4/10. Average retention lift: +35%.",
    accent: "#6D28D9",
    accentDark: "#7C3AED",
    visual: ContentQualityVisual,
    reverse: true,
    stat: { value: "9.4 / 10", label: "Avg quality score" },
  },
  {
    id: "scale",
    eyebrow: "YouTube at Scale",
    headline: "One setup.",
    headline2: "Every channel.",
    subtext:
      "Go from 1 YouTube channel to 100 overnight. Autoniix handles every channel identically — same quality, same speed, same reliability — whether you run 5 or 500 jobs.",
    accent: "#0891B2",
    accentDark: "#06B6D4",
    visual: ScaleDemoVisual,
    reverse: false,
    stat: { value: "400+", label: "Videos / month / 100 channels" },
  },
  {
    id: "control",
    eyebrow: "Full Control",
    headline: "Autopilot on.",
    headline2: "You still fly.",
    subtext:
      "Set a quality threshold and let everything through automatically — or require human sign-off before anything publishes. Every step is configurable, pausable, reversible.",
    accent: "#D97706",
    accentDark: "#F59E0B",
    visual: HumanLoopVisual,
    reverse: true,
    stat: { value: "100%", label: "Reversible at any step" },
  },
];

/* ─── MarketingSection ────────────────────────────────────── */
function MarketingSection({ section, index }: { section: (typeof SECTIONS)[0]; index: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const yVisual = useTransform(scrollYProgress, [0, 1], [40, -40]);
  const Visual = section.visual;

  return (
    <div ref={ref} className="relative py-28 md:py-36" style={{ overflowX: "clip" }}>
      {/* SS3-style aurora + rainbow mesh combo */}
      <div className="section-glow-aurora" style={{ opacity: 0.95 }} />
      <div className="rainbow-glow" style={{ opacity: 0.55 }} />
      <div className="noise-texture" />
      <div className="section-blend section-blend-top" />
      <div className="section-blend section-blend-bottom" />

      {/* Decorative number watermark */}
      <div
        aria-hidden
        className="absolute font-mono select-none pointer-events-none hidden xl:block"
        style={{
          top: "8%",
          [section.reverse ? "right" : "left"]: "4%",
          fontSize: "clamp(8rem, 14vw, 16rem)",
          fontWeight: 600,
          color: "transparent",
          WebkitTextStroke: "1px var(--border-strong)",
          lineHeight: 1,
          letterSpacing: "-0.05em",
        }}
      >
        {String(index + 1).padStart(2, "0")}
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        <div
          className={`grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center ${section.reverse ? "lg:[&>*:first-child]:order-2" : ""}`}
        >
          {/* Text column */}
          <motion.div
            initial={{ opacity: 0, x: section.reverse ? 32 : -32 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* Eyebrow */}
            <div
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full t-eyebrow border mb-6"
              style={{
                color: "var(--accent-secondary)",
                borderColor: "color-mix(in srgb, var(--accent-secondary) 28%, transparent)",
                background: "color-mix(in srgb, var(--accent-secondary) 8%, transparent)",
              }}
            >
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--accent-secondary)" }} />
              {section.eyebrow}
            </div>

            {/* Headline — two lines, second line gradient-text */}
            <h2 className="t-display-lg mb-6" style={{ color: "var(--text-primary)" }}>
              {section.headline}
              <br />
              <span className="gradient-text">{section.headline2}</span>
            </h2>

            {/* Body */}
            <p className="t-body-lg mb-6 max-w-md" style={{ color: "var(--text-muted)" }}>
              {section.subtext}
            </p>

            {/* Stat callout chip */}
            <div
              className="inline-flex items-center gap-3 px-4 py-2.5 rounded-2xl border"
              style={{
                borderColor: "var(--border)",
                background: "var(--bg-card)",
                backdropFilter: "blur(12px)",
              }}
            >
              <span
                style={{
                  fontSize: "1.5rem",
                  fontWeight: 500,
                  color: "var(--text-primary)",
                  letterSpacing: "-0.02em",
                  lineHeight: 1,
                }}
              >
                {section.stat.value}
              </span>
              <span className="t-micro" style={{ color: "var(--text-muted)" }}>
                {section.stat.label}
              </span>
            </div>
          </motion.div>

          {/* Visual column */}
          <motion.div
            style={{ y: yVisual }}
            initial={{ opacity: 0, x: section.reverse ? -32 : 32 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.7, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="relative">
              {/* SS3 halo backdrop — silver/violet halos behind card */}
              <div className="halo-backdrop" />

              {/* Glowing gradient border card */}
              <div
                className="rounded-3xl p-px relative"
                style={{
                  background: `linear-gradient(135deg, color-mix(in srgb, var(--accent-secondary) 45%, transparent) 0%, color-mix(in srgb, var(--accent-tertiary) 28%, transparent) 50%, transparent 100%)`,
                }}
              >
                <div
                  className="rounded-[23px] p-6 md:p-8 backdrop-blur-md"
                  style={{
                    background: "color-mix(in srgb, var(--bg-card-elevated) 92%, transparent)",
                    boxShadow: "var(--shadow-card-hover)",
                  }}
                >
                  <Visual accent={section.accentDark} />
                </div>
              </div>
            </div>

            {/* Floating live-data chip */}
            <div className="mt-4 flex justify-end">
              <div
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full t-micro border"
                style={{
                  color: "var(--accent)",
                  borderColor: "color-mix(in srgb, var(--accent) 28%, transparent)",
                  background: "color-mix(in srgb, var(--accent) 8%, transparent)",
                }}
              >
                <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: "var(--accent)" }} />
                LIVE DATA
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

/* ─── MarketingFeatures (entry) ──────────────────────────── */
export default function MarketingFeatures() {
  return (
    <section id="deep-dive" className="relative">
      {/* Section intro */}
      <div className="max-w-7xl mx-auto px-6 pt-24 pb-4 text-center relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.55 }}
        >
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full border t-eyebrow mb-5"
            style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
          >
            What makes it different
          </div>
          <h2 className="t-display-lg mb-4" style={{ color: "var(--text-primary)" }}>
            Built different.
            <br />
            <span className="gradient-text">Works different.</span>
          </h2>
          <p className="t-body-lg max-w-xl mx-auto" style={{ color: "var(--text-muted)" }}>
            Every design decision was made to maximise output quality and minimise your involvement.
          </p>
        </motion.div>
      </div>

      {/* Sections — no wavy dividers, glow backgrounds instead */}
      {SECTIONS.map((section, i) => (
        <MarketingSection key={section.id} section={section} index={i} />
      ))}
    </section>
  );
}
