'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { motion, useMotionValue, useSpring } from 'framer-motion'
import { ArrowRight, Activity, ChevronDown } from 'lucide-react'
import GlowButton from './ui/GlowButton'
import ParticleField from './ui/ParticleField'

/* ─── Pipeline stages ─────────────────────────────────────── */
const STAGES = [
  { id: 'research',  label: 'Research',  color: '#00D89F', x: 60,  y: 130 },
  { id: 'script',   label: 'Script',    color: '#7C3AED', x: 200, y: 60  },
  { id: 'voice',    label: 'Voice',     color: '#06B6D4', x: 340, y: 130 },
  { id: 'render',   label: 'Render',    color: '#F59E0B', x: 200, y: 200 },
  { id: 'publish',  label: 'Publish',   color: '#00D89F', x: 480, y: 130 },
]

const EDGES = [
  { from: 0, to: 1 }, { from: 0, to: 3 },
  { from: 1, to: 2 }, { from: 3, to: 2 },
  { from: 2, to: 4 },
]

/* ─── Live job feed data ──────────────────────────────────── */
const JOB_POOL = [
  { title: 'How compound interest really works', niche: 'Finance',  stage: 'Rendering',         color: '#00D89F', progress: 78 },
  { title: 'Sleep cycles decoded — the science',  niche: 'Health',   stage: 'Voice synthesis',   color: '#06B6D4', progress: 52 },
  { title: 'Gut microbiome — beginner guide',     niche: 'Health',   stage: 'Script generation', color: '#7C3AED', progress: 23 },
  { title: 'Why index funds beat hedge funds',    niche: 'Finance',  stage: 'Research',          color: '#00D89F', progress: 8  },
  { title: 'HIIT vs steady-state cardio',         niche: 'Fitness',  stage: 'Publishing',        color: '#F59E0B', progress: 97 },
  { title: 'The psychology of money',             niche: 'Finance',  stage: 'Rendering',         color: '#00D89F', progress: 64 },
  { title: 'Cold exposure — full protocol',       niche: 'Health',   stage: 'Script generation', color: '#7C3AED', progress: 31 },
]

/* ─── PipelineSVG ─────────────────────────────────────────── */
function PipelineSVG({ active, mouseX, mouseY }: { active: number; mouseX: number; mouseY: number }) {
  return (
    <div
      className="relative w-full"
      style={{
        transform: `translate(${mouseX * 12}px, ${mouseY * 8}px)`,
        transition: 'transform 0.9s cubic-bezier(0.16,1,0.3,1)',
      }}
    >
      <svg viewBox="0 0 560 270" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-auto">
        {/* Edges */}
        {EDGES.map((edge, i) => {
          const from = STAGES[edge.from]
          const to   = STAGES[edge.to]
          const isActive = edge.from === active || edge.to === active
          return (
            <g key={i}>
              <line
                x1={from.x} y1={from.y}
                x2={to.x}   y2={to.y}
                stroke={isActive ? from.color : 'rgba(255,255,255,0.08)'}
                strokeWidth={isActive ? 2 : 1}
                strokeDasharray={isActive ? '8 4' : '4 6'}
                style={isActive ? {
                  animation: 'flowDash 1.5s linear infinite',
                  strokeDashoffset: 0,
                } : undefined}
              />
              {/* Flowing particle */}
              {isActive && (
                <circle r="3" fill={from.color} opacity="0.9">
                  <animateMotion dur="1.8s" repeatCount="indefinite">
                    <mpath href={`#edge-${i}`} />
                  </animateMotion>
                </circle>
              )}
              <path id={`edge-${i}`} d={`M${from.x},${from.y} L${to.x},${to.y}`} />
            </g>
          )
        })}

        {/* Nodes */}
        {STAGES.map((stage, i) => {
          const isActive = i === active
          return (
            <g key={stage.id} className="cursor-default select-none">
              {/* Halo ring */}
              {isActive && (
                <circle
                  cx={stage.x} cy={stage.y} r="28"
                  fill="none"
                  stroke={stage.color}
                  strokeWidth="1"
                  opacity="0.3"
                  style={{ animation: 'nodePulse 2.4s ease-in-out infinite' }}
                />
              )}
              {/* Node circle */}
              <circle
                cx={stage.x} cy={stage.y} r={isActive ? 20 : 16}
                fill={isActive ? `${stage.color}22` : 'rgba(255,255,255,0.04)'}
                stroke={isActive ? stage.color : 'rgba(255,255,255,0.12)'}
                strokeWidth={isActive ? 2 : 1}
                style={{ transition: 'all 0.4s cubic-bezier(0.16,1,0.3,1)' }}
              />
              {/* Inner dot */}
              <circle
                cx={stage.x} cy={stage.y} r={isActive ? 6 : 4}
                fill={isActive ? stage.color : 'rgba(255,255,255,0.25)'}
                style={{ transition: 'all 0.4s cubic-bezier(0.16,1,0.3,1)' }}
              />
              {/* Label */}
              <text
                x={stage.x} y={stage.y + (i === 1 ? -30 : i === 3 ? 32 : -28)}
                textAnchor="middle"
                fontSize="10"
                fontFamily="var(--font-mono), monospace"
                fill={isActive ? stage.color : 'rgba(255,255,255,0.35)'}
                style={{ transition: 'fill 0.3s ease' }}
              >
                {stage.label}
              </text>
            </g>
          )
        })}

        {/* Central label */}
        <text x="280" y="248" textAnchor="middle" fontSize="9" fontFamily="var(--font-mono), monospace" fill="rgba(255,255,255,0.2)">
          AUTONIIX ENGINE v2.5 • RUNNING
        </text>
      </svg>

      {/* Glow beneath the diagram */}
      <div
        className="absolute inset-x-0 bottom-0 h-16 pointer-events-none"
        style={{
          background: `radial-gradient(ellipse at center, ${STAGES[active]?.color ?? '#00D89F'}18 0%, transparent 70%)`,
          transition: 'background 0.6s ease',
        }}
      />
    </div>
  )
}

/* ─── LiveJobsFeed ────────────────────────────────────────── */
function LiveJobsFeed({ mouseX, mouseY }: { mouseX: number; mouseY: number }) {
  const [jobs, setJobs] = useState(JOB_POOL.slice(0, 4))
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 3200)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    setJobs(prev => {
      const next = [...prev]
      const updated = { ...next[tick % next.length] }
      updated.progress = Math.min(100, updated.progress + Math.floor(Math.random() * 18) + 4)
      if (updated.progress >= 100) {
        const newJob = { ...JOB_POOL[(tick + 4) % JOB_POOL.length], progress: 0 }
        next.splice(tick % next.length, 1, newJob)
      } else {
        next[tick % next.length] = updated
      }
      return next
    })
  }, [tick])

  return (
    <div
      className="space-y-3"
      style={{
        transform: `translate(${mouseX * -10}px, ${mouseY * -6}px)`,
        transition: 'transform 0.7s cubic-bezier(0.16,1,0.3,1)',
      }}
    >
      {/* Feed header */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-white/40 text-xs font-mono uppercase tracking-widest">Live Pipeline</span>
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-[#00D89F] animate-pulse" />
          <span className="text-[#00D89F] text-xs font-mono">{jobs.length} active</span>
        </div>
      </div>

      {jobs.map((job, i) => (
        <motion.div
          key={`${job.title}-${i}`}
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.45, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
          className="glass-card rounded-xl p-3.5 border border-white/[0.07] group hover:border-white/15 transition-colors duration-300"
          style={{ '--sweep-color': job.color } as React.CSSProperties}
        >
          <div className="flex items-start justify-between gap-2 mb-2.5">
            <div className="flex items-center gap-2 min-w-0">
              <div
                className="w-2 h-2 rounded-full flex-shrink-0 mt-0.5"
                style={{ background: job.color, boxShadow: `0 0 6px ${job.color}80` }}
              />
              <p className="text-white/80 text-xs font-medium truncate">{job.title}</p>
            </div>
            <span
              className="text-[10px] font-mono flex-shrink-0 px-1.5 py-0.5 rounded"
              style={{ color: job.color, background: `${job.color}15` }}
            >
              {job.niche}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex-1 h-1 bg-white/[0.06] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{ width: `${job.progress}%`, background: `linear-gradient(90deg, ${job.color}cc, ${job.color})` }}
              />
            </div>
            <span className="text-white/35 text-[10px] font-mono flex-shrink-0 w-16 text-right">{job.stage}</span>
            <span style={{ color: job.color }} className="text-[10px] font-mono flex-shrink-0 w-8 text-right">{job.progress}%</span>
          </div>
        </motion.div>
      ))}

      {/* Stats footer */}
      <div className="flex items-center gap-3 pt-1">
        {[
          { label: 'Today', value: '47 published' },
          { label: 'Queue', value: '12 jobs' },
        ].map(s => (
          <div key={s.label} className="flex-1 glass-card rounded-lg px-3 py-2 text-center border border-white/[0.06]">
            <p className="text-white/30 text-[10px] mb-0.5 font-mono">{s.label}</p>
            <p className="text-white/70 text-xs font-semibold">{s.value}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ─── Headline words ──────────────────────────────────────── */
const H_LINE1 = ['Your', 'content']
const H_LINE2_PLAIN = 'empire, '
const H_LINE2_ACCENT = 'automated.'

/* ─── Hero ────────────────────────────────────────────────── */
export default function Hero() {
  const [activeNode, setActiveNode] = useState(0)
  const sectionRef = useRef<HTMLElement>(null)

  const rawX = useMotionValue(0)
  const rawY = useMotionValue(0)
  const springX = useSpring(rawX, { stiffness: 60, damping: 20 })
  const springY = useSpring(rawY, { stiffness: 60, damping: 20 })
  const [mx, setMx] = useState(0)
  const [my, setMy] = useState(0)

  /* Cycle pipeline active node */
  useEffect(() => {
    const id = setInterval(() => setActiveNode(n => (n + 1) % STAGES.length), 2000)
    return () => clearInterval(id)
  }, [])

  /* Mouse parallax */
  const handleMouse = useCallback((e: MouseEvent) => {
    if (!sectionRef.current) return
    const rect = sectionRef.current.getBoundingClientRect()
    rawX.set((e.clientX - rect.width / 2) / rect.width)
    rawY.set((e.clientY - rect.height / 2) / rect.height)
  }, [rawX, rawY])

  useEffect(() => {
    window.addEventListener('mousemove', handleMouse, { passive: true })
    return () => window.removeEventListener('mousemove', handleMouse)
  }, [handleMouse])

  useEffect(() => {
    const unsub1 = springX.on('change', v => setMx(v))
    const unsub2 = springY.on('change', v => setMy(v))
    return () => { unsub1(); unsub2() }
  }, [springX, springY])

  return (
    <section
      ref={sectionRef}
      className="relative min-h-screen flex flex-col justify-center"
      style={{ overflowX: 'clip' }}
    >
      {/* ── Hero glow (theme-aware radial) ── */}
      <div className="hero-glow" />

      {/* ── Rainbow ambient mesh (pastel in light, neon in dark) ── */}
      <div className="rainbow-glow" style={{ opacity: 0.95 }} />

      {/* ── Mesh gradient background ── */}
      <div className="mesh-bg">
        <div className="mesh-orb mesh-orb-1" style={{ transform: `translate(${mx * -40}px, ${my * -25}px)` }} />
        <div className="mesh-orb mesh-orb-2" style={{ transform: `translate(${mx * 35}px, ${my * -20}px)` }} />
        <div className="mesh-orb mesh-orb-3" style={{ transform: `translate(${mx * 25}px, ${my * 28}px)` }} />
        <div className="mesh-orb mesh-orb-4" style={{ transform: `translate(${mx * -20}px, ${my * 20}px)` }} />
      </div>

      {/* ── Content ── */}
      <div className="relative z-10 max-w-7xl mx-auto px-6 pt-28 pb-12 w-full">

        {/* Eyebrow badge */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="flex justify-center mb-8"
        >
          <div
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border t-eyebrow"
            style={{
              borderColor: 'color-mix(in srgb, var(--accent) 28%, transparent)',
              background: 'color-mix(in srgb, var(--accent) 8%, transparent)',
              color: 'var(--accent)',
              letterSpacing: '0.18em',
            }}
          >
            <span className="relative flex h-2 w-2 flex-shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60" style={{ background: 'var(--accent)' }} />
              <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: 'var(--accent)' }} />
            </span>
            AI-Powered Content Engine
          </div>
        </motion.div>

        {/* ── Headline ── */}
        <div className="text-center mb-6">
          <h1 className="t-display-xl mb-0" style={{ color: 'var(--text-primary)' }}>
            {H_LINE1.map((word, i) => (
              <motion.span
                key={word}
                initial={{ opacity: 0, y: 32 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.65, delay: 0.15 + i * 0.1, ease: [0.16, 1, 0.3, 1] }}
                className="inline-block mr-[0.18em]"
              >
                {word}
              </motion.span>
            ))}
            <br />
            <motion.span
              initial={{ opacity: 0, y: 32 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.65, delay: 0.35, ease: [0.16, 1, 0.3, 1] }}
              className="inline-block mr-[0.05em]"
              style={{ color: 'var(--text-secondary)' }}
            >
              {H_LINE2_PLAIN}
            </motion.span>
            <motion.span
              initial={{ opacity: 0, y: 32 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.65, delay: 0.46, ease: [0.16, 1, 0.3, 1] }}
              className="inline-block gradient-shimmer"
            >
              {H_LINE2_ACCENT}
            </motion.span>
          </h1>
        </div>

        {/* Sub-headline */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="text-center t-body-lg max-w-2xl mx-auto mb-10"
          style={{ color: 'var(--text-muted)' }}
        >
          Research, script, voice, render, publish — across every platform, at any scale.
          <span style={{ color: 'var(--text-faint)' }}> Set it once. Let it run forever.</span>
        </motion.p>

        {/* CTA row */}
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.52 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-6"
        >
          <GlowButton
            size="lg"
            onClick={() => window.open('https://dash.autoniix.com/register', '_blank')}
            className="flex items-center gap-2 min-w-[210px] justify-center"
          >
            Start automating free
            <ArrowRight className="w-4 h-4" />
          </GlowButton>
          <GlowButton
            variant="ghost"
            size="lg"
            className="flex items-center gap-2 min-w-[160px] justify-center"
          >
            See how it works
          </GlowButton>
        </motion.div>

        {/* Live stats badge */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.85 }}
          className="flex justify-center mb-14"
        >
          <div
            className="flex items-center gap-3 px-4 py-2 rounded-full border t-body-sm"
            style={{
              borderColor: 'var(--border)',
              background: 'var(--bg-card)',
              color: 'var(--text-muted)',
              backdropFilter: 'blur(12px)',
            }}
          >
            <Activity className="w-3.5 h-3.5" strokeWidth={1.75} style={{ color: 'var(--accent)' }} />
            <span>47 videos published today</span>
            <span className="w-px h-3" style={{ background: 'var(--border)' }} />
            <span>6 pipelines running</span>
            <span className="w-px h-3" style={{ background: 'var(--border)' }} />
            <span>3 platforms active</span>
          </div>
        </motion.div>

        {/* ── Antigravity-style particle hero card ── */}
        <motion.div
          initial={{ opacity: 0, y: 48 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="max-w-6xl mx-auto relative"
        >
          {/* SS3-style halo backdrop — silver/violet ring behind the dark card */}
          <div className="halo-backdrop" />

          <div className="hero-particle-card mockup-dark relative">
            <ParticleField count={420} color="#7C3AED" altColor="#06B6D4" centerX={0.72} centerY={0.5} radius={0.55} />
            <div className="hero-particle-card-inner">
              <div className="t-eyebrow mb-4" style={{ color: 'rgba(255,255,255,0.45)' }}>
                The Engine
              </div>
              <h3 className="t-display-md text-white mb-4">
                Ten models. One brain.
                <br />
                <span style={{ color: 'rgba(255,255,255,0.55)' }}>Working in parallel.</span>
              </h3>
              <p className="t-body-lg max-w-md mb-6" style={{ color: 'rgba(255,255,255,0.62)' }}>
                Gemini, Claude, GPT-4, ElevenLabs, Veo, FFmpeg — orchestrated together so every step of the
                pipeline gets the model best suited for it.
              </p>
              <div className="inline-flex items-center gap-2 t-micro" style={{ color: '#00D89F' }}>
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60 bg-[#00D89F]" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#00D89F]" />
                </span>
                {STAGES[activeNode].label.toUpperCase()} · ACTIVE
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      {/* ── Scroll indicator ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.4 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1 z-10"
        style={{ color: 'var(--text-faint)' }}
      >
        <span className="t-micro">Scroll</span>
        <ChevronDown className="w-4 h-4 animate-bounce" strokeWidth={1.5} />
      </motion.div>
    </section>
  )
}
