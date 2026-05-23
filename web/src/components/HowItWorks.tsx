'use client'

import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Settings2, Cpu, Send } from 'lucide-react'

/* ─── Step data ──────────────────────────────────────────── */
const STEPS = [
  {
    number: '01',
    icon: Settings2,
    title: 'Configure',
    description: 'Set your niche, tone, brand voice, and target platforms. Takes minutes, drives everything.',
    accent: '#00D89F',
    detail: 'Pick a niche → Define your voice → Connect platforms → Done.',
  },
  {
    number: '02',
    icon: Cpu,
    title: 'Automate',
    description: 'AI researches trends, writes scripts, synthesises voice, and renders video — fully autonomous.',
    accent: '#7C3AED',
    detail: 'Research → Script → Voice → Render → Queue',
  },
  {
    number: '03',
    icon: Send,
    title: 'Publish',
    description: 'Content ships on schedule. Analytics feed back into the loop. System learns and improves.',
    accent: '#2563EB',
    detail: 'Auto-schedule → Multi-platform → Analytics loop',
  },
]

/* ─── Terminal lines ─────────────────────────────────────── */
const TERMINAL_LINES = [
  { text: 'Initialising Autoniix engine v2.5...', type: 'info',       delay: 0    },
  { text: '✓ Gemini 2.5 Flash  ready',           type: 'success',    delay: 500  },
  { text: '✓ Claude Sonnet 4   ready',           type: 'success',    delay: 900  },
  { text: '✓ Fish Audio        ready',           type: 'success',    delay: 1250 },
  { text: 'Scanning trends → niche: Finance',    type: 'processing', delay: 1700 },
  { text: '✓ 47 topics scored. Top: 9.4/10',    type: 'success',    delay: 2600 },
  { text: 'Generating script → 1,847 words',     type: 'processing', delay: 3100 },
  { text: '✓ Hook score: 9.1 · Quality: 9.2',   type: 'success',    delay: 4000 },
  { text: 'Synthesising voice (6m 42s)...',      type: 'processing', delay: 4500 },
  { text: '✓ Voice rendered — Fish Audio',       type: 'success',    delay: 5400 },
  { text: 'Rendering video — 9,840 frames...',   type: 'processing', delay: 5900 },
  { text: '✓ 1080p exported in 38s',             type: 'success',    delay: 6800 },
  { text: '✓ Uploaded to YouTube · TikTok',      type: 'success',    delay: 7300 },
  { text: '✓ Next job queued. Running at 00:00', type: 'success',    delay: 7800 },
]

/* ─── TiltCard ───────────────────────────────────────────── */
function TiltCard({ children, accent }: { children: React.ReactNode; accent: string }) {
  const ref = useRef<HTMLDivElement>(null)

  const handleMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width  - 0.5
    const y = (e.clientY - rect.top)  / rect.height - 0.5
    el.style.transform = `perspective(700px) rotateX(${-y * 10}deg) rotateY(${x * 10}deg) scale(1.02)`
    el.style.boxShadow = `0 20px 50px rgba(0,0,0,0.4), 0 0 30px ${accent}20`
  }

  const handleLeave = () => {
    const el = ref.current
    if (!el) return
    el.style.transform = 'perspective(700px) rotateX(0deg) rotateY(0deg) scale(1)'
    el.style.boxShadow = ''
  }

  return (
    <div
      ref={ref}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      className="tilt-card glass-card rounded-2xl p-6 border h-full"
      style={{ transition: 'transform 0.25s ease, box-shadow 0.25s ease', borderColor: 'var(--border)' }}
    >
      {children}
    </div>
  )
}

/* ─── Terminal component ─────────────────────────────────── */
function LiveTerminal() {
  const [visible, setVisible] = useState<number[]>([])
  const [cycle, setCycle] = useState(0)

  useEffect(() => {
    setVisible([])
    const timeouts: ReturnType<typeof setTimeout>[] = []

    TERMINAL_LINES.forEach((line, i) => {
      const t = setTimeout(() => setVisible(v => [...v, i]), line.delay)
      timeouts.push(t)
    })

    const reset = setTimeout(() => setCycle(c => c + 1), 10500)
    timeouts.push(reset)

    return () => timeouts.forEach(clearTimeout)
  }, [cycle])

  const colorMap: Record<string, string> = {
    success:    'text-[#00D89F]',
    processing: 'text-[#7C3AED]',
    info:       'text-white/40',
  }

  return (
    <div className="gradient-border-card mockup-dark">
      <div className="gradient-border-card-inner">
        {/* Chrome bar */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.07] bg-white/[0.02]">
          <div className="w-3 h-3 rounded-full bg-[#FF5F57]" />
          <div className="w-3 h-3 rounded-full bg-[#FFBD2E]" />
          <div className="w-3 h-3 rounded-full bg-[#28CA41]" />
          <span className="ml-3 text-[11px] text-white/25 font-mono">autoniix — ai-pipeline</span>
          <div className="ml-auto flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-[#00D89F] animate-pulse" />
            <span className="text-[10px] font-mono text-[#00D89F]">running</span>
          </div>
        </div>

        {/* Lines */}
        <div className="p-5 space-y-1.5 min-h-[280px] overflow-hidden">
          {TERMINAL_LINES.map((line, i) => (
            visible.includes(i) && (
              <div key={`${cycle}-${i}`} className="terminal-line animate-fade-in-up">
                <span className="terminal-prompt flex-shrink-0">›</span>
                <span className={colorMap[line.type] || 'text-white/60'}>{line.text}</span>
              </div>
            )
          ))}
          {visible.length < TERMINAL_LINES.length && (
            <div className="terminal-line">
              <span className="terminal-prompt">›</span>
              <span className="text-white/30 animate-blink">█</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── HowItWorks ─────────────────────────────────────────── */
export default function HowItWorks() {
  return (
    <section id="how-it-works" className="section-pad relative" style={{ overflowX: 'clip' }}>
      {/* Aurora + rainbow ambient (SS3 look) */}
      <div className="section-glow-aurora" style={{ opacity: 0.85 }} />
      <div className="rainbow-glow" style={{ opacity: 0.4 }} />
      <div className="noise-texture" />
      <div className="section-blend section-blend-top" />
      <div className="section-blend section-blend-bottom" />

      <div className="max-w-7xl mx-auto px-6 relative z-10">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.55 }}
          className="text-center mb-20"
        >
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full border t-eyebrow mb-5"
            style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}
          >
            How it works
          </div>
          <h2 className="t-display-lg mb-4" style={{ color: 'var(--text-primary)' }}>
            Configure once.
            <br />
            <span className="gradient-text">Publish forever.</span>
          </h2>
          <p className="t-body-lg max-w-lg mx-auto" style={{ color: 'var(--text-muted)' }}>
            Three steps, then Autoniix takes over completely.
          </p>
        </motion.div>

        {/* ── Steps row ── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-16 relative">
          {/* Desktop connector */}
          <div className="hidden lg:block absolute top-10 left-[calc(16.66%+48px)] right-[calc(16.66%+48px)] h-px z-0"
            style={{ background: 'linear-gradient(90deg, #00D89F40, #7C3AED40, #2563EB40)' }}
          />

          {STEPS.map((step, i) => {
            const Icon = step.icon
            return (
              <motion.div
                key={step.number}
                initial={{ opacity: 0, y: 32 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-60px' }}
                transition={{ duration: 0.55, delay: i * 0.14, ease: [0.16, 1, 0.3, 1] }}
                className="relative z-10"
              >
                <TiltCard accent={step.accent}>
                  {/* Icon + badge */}
                  <div className="flex items-start justify-between mb-5">
                    <div
                      className="w-12 h-12 rounded-2xl flex items-center justify-center"
                      style={{
                        background: `linear-gradient(135deg, ${step.accent}20 0%, ${step.accent}08 100%)`,
                        border: `1px solid ${step.accent}30`,
                        boxShadow: `0 0 20px ${step.accent}18`,
                      }}
                    >
                      <Icon className="w-5 h-5" style={{ color: step.accent }} />
                    </div>
                    <span
                      className="text-[11px] font-bold font-mono px-2.5 py-1 rounded-lg"
                      style={{ background: `${step.accent}18`, color: step.accent, border: `1px solid ${step.accent}28` }}
                    >
                      {step.number}
                    </span>
                  </div>

                  <h3 className="t-headline mb-2" style={{ color: 'var(--text-primary)' }}>{step.title}</h3>
                  <p className="t-body-sm mb-4" style={{ color: 'var(--text-muted)' }}>{step.description}</p>

                  {/* Detail pill */}
                  <div
                    className="t-micro px-3 py-2 rounded-lg"
                    style={{
                      background: `${step.accent}0A`,
                      color: step.accent,
                      border: `1px solid ${step.accent}28`,
                      textTransform: 'none',
                      letterSpacing: 0,
                      fontSize: '0.6875rem',
                    }}
                  >
                    {step.detail}
                  </div>
                </TiltCard>
              </motion.div>
            )
          })}
        </div>

        {/* ── Terminal section ── */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.75, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="text-center mb-6">
            <p className="t-eyebrow" style={{ color: 'var(--text-muted)' }}>Watch the engine run — live</p>
          </div>
          <div className="max-w-3xl mx-auto">
            <LiveTerminal />
          </div>
        </motion.div>
      </div>
    </section>
  )
}
