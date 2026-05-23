'use client'

import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'

/* ─── Wavy SVG divider ───────────────────────────────────── */
function WaveDivider({ flip = false, color = '#09090F' }: { flip?: boolean; color?: string }) {
  return (
    <div className={`wave-divider ${flip ? 'rotate-180' : ''}`} style={{ marginTop: flip ? 0 : -2, marginBottom: flip ? -2 : 0 }}>
      <svg viewBox="0 0 1440 60" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <motion.path
          d="M0,30 C240,60 480,0 720,30 C960,60 1200,0 1440,30 L1440,60 L0,60 Z"
          fill={color}
          animate={{ d: [
            'M0,30 C240,60 480,0 720,30 C960,60 1200,0 1440,30 L1440,60 L0,60 Z',
            'M0,20 C240,0 480,60 720,20 C960,0 1200,60 1440,20 L1440,60 L0,60 Z',
            'M0,30 C240,60 480,0 720,30 C960,60 1200,0 1440,30 L1440,60 L0,60 Z',
          ]}}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
        />
      </svg>
    </div>
  )
}

/* ─── Animated visuals ───────────────────────────────────── */
function AutopilotVisual() {
  const models = [
    { name: 'Gemini 2.5 Flash', role: 'Research',  color: '#00D89F', ms: '120ms' },
    { name: 'Claude Sonnet 4',  role: 'Script',    color: '#7C3AED', ms: '340ms' },
    { name: 'GPT-4o',           role: 'Fact-check', color: '#06B6D4', ms: '80ms' },
    { name: 'Fish Audio',       role: 'Voice',     color: '#F59E0B', ms: '210ms' },
  ]
  return (
    <div className="space-y-3">
      <div className="text-[10px] font-mono text-white/25 uppercase tracking-[0.2em] mb-5">AI orchestration layer</div>
      {models.map((m, i) => (
        <motion.div
          key={m.name}
          initial={{ opacity: 0, x: 20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.1, duration: 0.5, ease: [0.16,1,0.3,1] }}
          className="flex items-center gap-4 glass-card rounded-xl px-4 py-3 border border-white/[0.07]"
        >
          <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: m.color, boxShadow: `0 0 8px ${m.color}80` }} />
          <div className="flex-1 min-w-0">
            <p className="text-white/75 text-sm font-medium truncate">{m.name}</p>
            <p className="text-white/30 text-[10px] font-mono">{m.role}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="h-1 w-12 bg-white/[0.06] rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ background: m.color }}
                initial={{ width: '0%' }}
                whileInView={{ width: '100%' }}
                viewport={{ once: true }}
                transition={{ duration: 1.2, delay: 0.4 + i * 0.15 }}
              />
            </div>
            <span className="text-[10px] font-mono" style={{ color: m.color }}>{m.ms}</span>
          </div>
        </motion.div>
      ))}
      {/* Status bar */}
      <div className="flex items-center gap-2 pt-2">
        <div className="w-1.5 h-1.5 rounded-full bg-[#00D89F] animate-pulse" />
        <span className="text-[11px] font-mono text-white/35">All models nominal · 99.9% uptime</span>
      </div>
    </div>
  )
}

function ContentQualityVisual() {
  const before = { score: 4.1, retention: '38%', ctr: '2.1%' }
  const after  = { score: 9.4, retention: '73%', ctr: '8.7%' }
  const metrics = [
    { label: 'Quality score', before: before.score,    after: after.score,    max: 10,   suffix: '/10' },
    { label: 'Avg retention', before: 38,              after: 73,             max: 100,  suffix: '%'  },
    { label: 'Click-through', before: 2.1,             after: 8.7,            max: 15,   suffix: '%'  },
  ]
  return (
    <div>
      <div className="text-[10px] font-mono text-white/25 uppercase tracking-[0.2em] mb-5">Quality comparison · AI vs manual</div>
      <div className="space-y-5">
        {metrics.map(m => (
          <div key={m.label}>
            <div className="flex items-center justify-between text-[11px] font-mono mb-2">
              <span className="text-white/40">{m.label}</span>
              <span className="text-white/25">{m.before}{m.suffix} → <span className="text-[#00D89F]">{m.after}{m.suffix}</span></span>
            </div>
            <div className="relative h-2 bg-white/[0.06] rounded-full overflow-hidden">
              {/* Before bar */}
              <div className="absolute left-0 top-0 h-full rounded-full bg-white/10"
                style={{ width: `${(m.before / m.max) * 100}%` }} />
              {/* After bar */}
              <motion.div
                className="absolute left-0 top-0 h-full rounded-full"
                style={{ background: 'linear-gradient(90deg, #00D89F88, #00D89F)' }}
                initial={{ width: '0%' }}
                whileInView={{ width: `${(m.after / m.max) * 100}%` }}
                viewport={{ once: true }}
                transition={{ duration: 1.4, ease: [0.16,1,0.3,1], delay: 0.3 }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ScaleDemoVisual() {
  const tiers = [
    { label: '1 profile',    videos: 4,   color: '#00D89F' },
    { label: '10 profiles',  videos: 40,  color: '#7C3AED' },
    { label: '50 profiles',  videos: 200, color: '#06B6D4' },
    { label: '100 profiles', videos: 400, color: '#F59E0B' },
  ]
  return (
    <div>
      <div className="text-[10px] font-mono text-white/25 uppercase tracking-[0.2em] mb-5">Output volume · Monthly videos</div>
      <div className="space-y-4">
        {tiers.map((tier, i) => (
          <motion.div
            key={tier.label}
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
          >
            <div className="flex items-center justify-between text-[11px] font-mono mb-1.5">
              <span className="text-white/50">{tier.label}</span>
              <span style={{ color: tier.color }}>{tier.videos} videos/mo</span>
            </div>
            <div className="h-2 bg-white/[0.05] rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ background: `linear-gradient(90deg, ${tier.color}88, ${tier.color})` }}
                initial={{ width: '0%' }}
                whileInView={{ width: `${(tier.videos / 400) * 100}%` }}
                viewport={{ once: true }}
                transition={{ duration: 1.2, ease: [0.16,1,0.3,1], delay: 0.2 + i * 0.12 }}
              />
            </div>
          </motion.div>
        ))}
      </div>
      <div className="mt-5 glass-card rounded-xl px-4 py-3 border border-[#00D89F]/15 flex items-center gap-3">
        <div className="text-2xl font-black gradient-text font-display">∞</div>
        <div>
          <p className="text-white/65 text-sm font-semibold">No hard limit</p>
          <p className="text-white/30 text-[11px]">Scale to any volume on the Enterprise plan</p>
        </div>
      </div>
    </div>
  )
}

function HumanLoopVisual() {
  const steps = [
    { label: 'AI generates script',  status: 'done',    color: '#00D89F' },
    { label: 'Quality gate: 8.5+',   status: 'done',    color: '#00D89F' },
    { label: 'Human review (opt.)',   status: 'pending', color: '#F59E0B' },
    { label: 'Render + publish',      status: 'queued',  color: '#7C3AED' },
  ]
  return (
    <div>
      <div className="text-[10px] font-mono text-white/25 uppercase tracking-[0.2em] mb-5">Approval workflow · Configurable</div>
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-3.5 top-4 bottom-4 w-px bg-white/[0.07]" />
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
                  background: step.status === 'queued' ? 'rgba(255,255,255,0.04)' : `${step.color}18`,
                  borderColor: step.status === 'queued' ? 'rgba(255,255,255,0.1)' : `${step.color}50`,
                }}
              >
                {step.status === 'done'    && <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none"><path d="M2.5 6L5 8.5L9.5 3.5" stroke={step.color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
                {step.status === 'pending' && <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: step.color }} />}
                {step.status === 'queued'  && <div className="w-2 h-2 rounded-full bg-white/20" />}
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium" style={{ color: step.status === 'queued' ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.75)' }}>
                  {step.label}
                </p>
              </div>
              <span
                className="text-[10px] font-mono px-2 py-0.5 rounded"
                style={{ color: step.color, background: `${step.color}12` }}
              >
                {step.status}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
      <div className="mt-4 text-[11px] text-white/30 font-mono border-t border-white/[0.06] pt-4">
        Human review is <span className="text-[#F59E0B]">optional</span> — disable it and everything ships automatically.
      </div>
    </div>
  )
}

/* ─── Section data ───────────────────────────────────────── */
const SECTIONS = [
  {
    id: 'autopilot',
    eyebrow: 'AI Orchestration',
    headline: 'Ten models.\nOne brain.',
    subtext: 'Autoniix doesn\'t use a single AI — it orchestrates a team of specialist models, each best-in-class for its role. The result is content no single model could produce alone.',
    accent: '#00D89F',
    visual: AutopilotVisual,
    reverse: false,
    bgAccent: 'rgba(0,216,159,0.04)',
  },
  {
    id: 'quality',
    eyebrow: 'Content Quality',
    headline: 'Not just fast.\nActually good.',
    subtext: 'Every script is fact-checked, hook-optimised, and quality-scored before it touches your audience. Average score: 9.2/10. Average retention lift: +35%.',
    accent: '#7C3AED',
    visual: ContentQualityVisual,
    reverse: true,
    bgAccent: 'rgba(124,58,237,0.04)',
  },
  {
    id: 'scale',
    eyebrow: 'Infinite Scale',
    headline: 'One setup.\nEvery platform.',
    subtext: 'Go from 1 channel to 100 overnight. Autoniix handles every profile identically — same quality, same speed, same reliability — whether you\'re running 5 or 500 jobs.',
    accent: '#06B6D4',
    visual: ScaleDemoVisual,
    reverse: false,
    bgAccent: 'rgba(6,182,212,0.04)',
  },
  {
    id: 'control',
    eyebrow: 'Full Control',
    headline: 'Autopilot on.\nYou still fly.',
    subtext: 'Set a quality threshold and let everything through automatically — or require human sign-off before anything publishes. Every step is configurable, pausable, and reversible.',
    accent: '#F59E0B',
    visual: HumanLoopVisual,
    reverse: true,
    bgAccent: 'rgba(245,158,11,0.04)',
  },
]

/* ─── MarketingSection (single) ─────────────────────────── */
function MarketingSection({
  section,
  index,
}: {
  section: typeof SECTIONS[0]
  index: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] })
  const y = useTransform(scrollYProgress, [0, 1], [30, -30])
  const Visual = section.visual

  return (
    <div
      ref={ref}
      className="marketing-section relative"
      style={{ background: section.bgAccent !== 'rgba(0,0,0,0)' ? `linear-gradient(180deg, #09090F 0%, ${section.bgAccent.replace('0.04', '0.06')} 50%, #09090F 100%)` : undefined }}
    >
      {/* Ambient glow */}
      <div
        className="marketing-visual-glow w-[600px] h-[600px] pointer-events-none"
        style={{
          background: `radial-gradient(ellipse, ${section.accent}08 0%, transparent 70%)`,
          top: '10%',
          left: section.reverse ? 'auto' : '-10%',
          right: section.reverse ? '-10%' : 'auto',
        }}
      />

      <div className="max-w-7xl mx-auto px-6">
        <div className={`grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center ${section.reverse ? 'lg:[&>*:first-child]:order-2' : ''}`}>

          {/* Text column */}
          <motion.div
            initial={{ opacity: 0, x: section.reverse ? 32 : -32 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.7, ease: [0.16,1,0.3,1] }}
          >
            {/* Eyebrow */}
            <div
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono tracking-[0.18em] uppercase border mb-6"
              style={{ color: section.accent, borderColor: `${section.accent}28`, background: `${section.accent}0C` }}
            >
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: section.accent }} />
              {section.eyebrow}
            </div>

            {/* Headline */}
            <h2 className="font-display text-4xl sm:text-5xl lg:text-[3.5rem] font-black tracking-tighter text-white mb-6 leading-[1.05] whitespace-pre-line">
              {section.headline}
            </h2>

            {/* Body */}
            <p className="text-white/50 text-lg leading-relaxed mb-8 max-w-md">
              {section.subtext}
            </p>

            {/* Section number — large decorative */}
            <div
              className="text-[120px] font-black font-mono leading-none select-none absolute -bottom-8 -left-4 pointer-events-none hidden xl:block"
              style={{ color: `${section.accent}06`, WebkitTextStroke: `1px ${section.accent}10` }}
            >
              {String(index + 1).padStart(2, '0')}
            </div>
          </motion.div>

          {/* Visual column */}
          <motion.div
            style={{ y }}
            initial={{ opacity: 0, x: section.reverse ? -32 : 32 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.7, delay: 0.1, ease: [0.16,1,0.3,1] }}
          >
            {/* Gradient border card */}
            <div
              className="rounded-2xl p-px"
              style={{
                background: `linear-gradient(135deg, ${section.accent}40 0%, ${section.accent}10 40%, transparent 60%, ${section.accent}15 100%)`,
              }}
            >
              <div className="rounded-[15px] p-6 bg-[#0D0D18]">
                <Visual />
              </div>
            </div>

            {/* Floating accent chip */}
            <motion.div
              className="mt-4 flex justify-end"
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.5, duration: 0.45 }}
            >
              <div
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-mono"
                style={{ color: section.accent, borderColor: `${section.accent}22`, background: `${section.accent}0A` }}
              >
                <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: section.accent }} />
                Live data
              </div>
            </motion.div>
          </motion.div>
        </div>
      </div>
    </div>
  )
}

/* ─── MarketingFeatures (replaces FAQ) ───────────────────── */
export default function MarketingFeatures() {
  return (
    <section id="deep-dive" className="relative">
      {/* Section intro */}
      <div className="max-w-7xl mx-auto px-6 pt-24 pb-4 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.55 }}
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/8 text-xs text-white/40 font-medium tracking-[0.15em] uppercase mb-5">
            What makes it different
          </div>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-black tracking-tighter text-white mb-4">
            Built different.
            <br />
            <span className="gradient-text">Works different.</span>
          </h2>
          <p className="text-white/40 text-lg max-w-xl mx-auto">
            Every design decision was made to maximise output quality and minimise your involvement.
          </p>
        </motion.div>
      </div>

      {/* Alternating sections with wavy dividers */}
      {SECTIONS.map((section, i) => (
        <div key={section.id}>
          <WaveDivider flip={i % 2 === 1} />
          <MarketingSection section={section} index={i} />
        </div>
      ))}

      <WaveDivider />
    </section>
  )
}
