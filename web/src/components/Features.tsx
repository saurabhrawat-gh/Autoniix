'use client'

import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, PenTool, Mic2, Film, BarChart3, Globe2 } from 'lucide-react'

/* ─── Feature data ───────────────────────────────────────── */
const FEATURES = [
  {
    id: 'research',
    number: '01',
    icon: Brain,
    title: 'AI Research Engine',
    subtitle: 'Ideas at machine speed.',
    description: 'Gemini 2.5 Flash + GPT-4o synthesise trending topics, analyse audience signals, and surface high-potential ideas — before your competition knows they exist.',
    accent: '#00D89F',
    tags: ['Gemini 2.5 Flash', 'GPT-4o', 'Trend Analysis'],
  },
  {
    id: 'script',
    number: '02',
    icon: PenTool,
    title: 'Script Generation',
    subtitle: 'Claude writes. You watch.',
    description: 'Claude Sonnet crafts cinematic, retention-optimised scripts tailored to each niche. Fact-checked, quality-scored, hook-first — ready for production.',
    accent: '#7C3AED',
    tags: ['Claude Sonnet', 'Quality Score', 'Hook Optimised'],
  },
  {
    id: 'voice',
    number: '03',
    icon: Mic2,
    title: 'Voice Synthesis',
    subtitle: 'Broadcast quality, zero studio.',
    description: 'Each content profile gets a unique AI voice via Fish Audio — consistent, compelling, broadcast-ready narration at a fraction of the cost.',
    accent: '#06B6D4',
    tags: ['Fish Audio', 'Per-Profile Voice', 'Custom Tone'],
  },
  {
    id: 'render',
    number: '04',
    icon: Film,
    title: 'Automated Rendering',
    subtitle: 'Pixel-perfect. Every frame.',
    description: 'Remotion-powered engine with 48+ cinematic components. Code-driven composition means zero variability — the same professional output at any volume.',
    accent: '#F59E0B',
    tags: ['Remotion', '48+ Components', '4K Export'],
  },
  {
    id: 'analytics',
    number: '05',
    icon: BarChart3,
    title: 'Analytics Intelligence',
    subtitle: 'Content that learns.',
    description: 'Real-time performance signals feed back into the research loop — the AI knows what works and adjusts every topic, angle, and format automatically.',
    accent: '#2563EB',
    tags: ['Closed Loop', 'Auto-Optimise', 'Platform Signals'],
  },
  {
    id: 'scale',
    number: '06',
    icon: Globe2,
    title: 'Multi-Platform Scale',
    subtitle: '1 setup. Infinite reach.',
    description: 'From 1 to 100+ profiles across YouTube, Instagram, TikTok and beyond — zero extra effort. One pipeline, every platform, simultaneously.',
    accent: '#00D89F',
    tags: ['YouTube', 'Instagram', 'TikTok', 'Infinite Profiles'],
  },
]

/* ─── Animated feature visuals ───────────────────────────── */
function ResearchVisual({ accent }: { accent: string }) {
  const topics = [
    { label: 'Compound interest explained', score: 94 },
    { label: 'Sleep cycles decoded',        score: 88 },
    { label: 'Gut microbiome basics',        score: 82 },
    { label: 'Cold exposure protocol',       score: 79 },
  ]
  return (
    <div className="space-y-3">
      <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-4">Trending topics · Live</div>
      {topics.map((t, i) => (
        <motion.div
          key={t.label}
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.12, duration: 0.45, ease: [0.16,1,0.3,1] }}
          className="flex items-center gap-3 glass-card rounded-lg px-3 py-2.5"
        >
          <div className="flex-1 text-white/75 text-xs truncate">{t.label}</div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="w-16 h-1 bg-white/[0.06] rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${t.score}%`, background: accent }} />
            </div>
            <span className="text-[10px] font-mono" style={{ color: accent }}>{t.score}</span>
          </div>
        </motion.div>
      ))}
    </div>
  )
}

function ScriptVisual({ accent }: { accent: string }) {
  const lines = [
    'HOOK: "Most people never retire—',
    'not because they\'re lazy..."',
    '',
    'ACT 1: The compound secret...',
    'Imagine a snowball rolling...',
    'At 7% annual return...',
  ]
  const [shown, setShown] = useState(0)
  useEffect(() => {
    if (shown >= lines.length) return
    const t = setTimeout(() => setShown(s => s + 1), 320)
    return () => clearTimeout(t)
  }, [shown, lines.length])

  return (
    <div className="font-mono text-xs space-y-1">
      <div className="text-[10px] text-white/30 uppercase tracking-widest mb-3">Script generation · Writing</div>
      {lines.slice(0, shown).map((line, i) => (
        <div key={i} className={`${line === '' ? 'h-2' : ''} text-white/70 leading-relaxed`}>
          {line && <span className="text-white/30 mr-2">{String(i + 1).padStart(2, '0')}</span>}
          {line}
        </div>
      ))}
      {shown < lines.length && (
        <div className="flex">
          <span className="text-white/30 mr-2">{String(shown + 1).padStart(2, '0')}</span>
          <span className="animate-blink" style={{ color: accent }}>█</span>
        </div>
      )}
      <div className="mt-4 flex items-center gap-2">
        <div className="h-px flex-1 bg-white/[0.06]" />
        <span className="text-[10px] font-mono px-2 py-0.5 rounded" style={{ color: accent, background: `${accent}15` }}>
          Quality: 9.2 / 10
        </span>
      </div>
    </div>
  )
}

function VoiceVisual({ accent }: { accent: string }) {
  const bars = Array.from({ length: 40 }, (_, i) => ({
    height: Math.sin(i * 0.4) * 0.4 + Math.sin(i * 0.9) * 0.3 + 0.35,
    delay: i * 0.04,
  }))
  return (
    <div>
      <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-4">Voice synthesis · Rendering</div>
      <div className="flex items-center gap-0.5 h-16 mb-4">
        {bars.map((bar, i) => (
          <motion.div
            key={i}
            className="flex-1 rounded-full"
            style={{ background: accent, opacity: 0.6 + bar.height * 0.4 }}
            animate={{ scaleY: [bar.height, bar.height * 1.6, bar.height] }}
            transition={{ duration: 0.9 + bar.height * 0.4, repeat: Infinity, delay: bar.delay, ease: 'easeInOut' }}
          />
        ))}
      </div>
      <div className="flex items-center justify-between text-[10px] font-mono text-white/30">
        <span>0:00</span>
        <span style={{ color: accent }}>▶ Playing — Track 1 of 1</span>
        <span>6:42</span>
      </div>
    </div>
  )
}

function RenderVisual({ accent }: { accent: string }) {
  const [frame, setFrame] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setFrame(f => (f + 1) % 100), 80)
    return () => clearInterval(id)
  }, [])
  return (
    <div>
      <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-4">Video rendering · Frame {frame + 1} / 9840</div>
      <div className="relative w-full aspect-video rounded-xl overflow-hidden border border-white/[0.08] bg-[#0A0A14]">
        <div className="absolute inset-0 flex items-center justify-center">
          <div
            className="text-center"
            style={{ opacity: 0.08 + (frame % 10) * 0.008 }}
          >
            <div className="font-mono text-4xl font-black text-white">AUTONIIX</div>
          </div>
        </div>
        <div
          className="absolute bottom-0 left-0 h-0.5 transition-none"
          style={{ width: `${frame}%`, background: `linear-gradient(90deg, ${accent}cc, ${accent})` }}
        />
        <div className="absolute top-2 right-2 text-[10px] font-mono" style={{ color: accent }}>
          {frame}% rendered
        </div>
      </div>
    </div>
  )
}

function AnalyticsVisual({ accent }: { accent: string }) {
  const points = [12, 19, 14, 28, 22, 38, 32, 45, 41, 58, 62, 71]
  const max = Math.max(...points)
  const w = 280, h = 80
  const pts = points.map((v, i) => `${(i / (points.length - 1)) * w},${h - (v / max) * h}`).join(' ')
  return (
    <div>
      <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-4">Performance · Last 30 days</div>
      <svg viewBox={`0 0 ${w} ${h + 8}`} className="w-full" fill="none">
        <defs>
          <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity="0.3" />
            <stop offset="100%" stopColor={accent} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon
          points={`0,${h} ${pts} ${w},${h}`}
          fill="url(#chartGrad)"
        />
        <polyline
          points={pts}
          stroke={accent}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {points.map((v, i) => (
          <circle
            key={i}
            cx={(i / (points.length - 1)) * w}
            cy={h - (v / max) * h}
            r="3"
            fill={accent}
            opacity={i === points.length - 1 ? 1 : 0.3}
          />
        ))}
      </svg>
      <div className="flex items-center justify-between text-[10px] font-mono mt-2">
        <span className="text-white/30">Views: 1.2M</span>
        <span style={{ color: accent }}>↑ 34% this week</span>
      </div>
    </div>
  )
}

function ScaleVisual({ accent }: { accent: string }) {
  const platforms = ['YouTube', 'Instagram', 'TikTok', 'LinkedIn', 'X', 'Facebook']
  return (
    <div>
      <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-4">Active profiles · 6 platforms</div>
      <div className="grid grid-cols-3 gap-2">
        {platforms.map((p, i) => (
          <motion.div
            key={p}
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.1, ease: [0.16,1,0.3,1] }}
            className="glass-card rounded-lg p-2.5 text-center border border-white/[0.07]"
          >
            <div className="w-2 h-2 rounded-full mx-auto mb-1.5" style={{ background: accent, boxShadow: `0 0 6px ${accent}80` }} />
            <p className="text-[10px] text-white/55 font-medium">{p}</p>
            <p className="text-[8px] text-white/25 font-mono mt-0.5">Active</p>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

const VISUALS = [ResearchVisual, ScriptVisual, VoiceVisual, RenderVisual, AnalyticsVisual, ScaleVisual]

/* ─── Features component ─────────────────────────────────── */
export default function Features() {
  const [activeIndex, setActiveIndex] = useState(0)
  const itemRefs = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    const observers = itemRefs.current.map((el, i) => {
      if (!el) return null
      const obs = new IntersectionObserver(
        ([entry]) => { if (entry.isIntersecting) setActiveIndex(i) },
        { threshold: 0.55, rootMargin: '-80px 0px -80px 0px' }
      )
      obs.observe(el)
      return obs
    })
    return () => observers.forEach(o => o?.disconnect())
  }, [])

  const active = FEATURES[activeIndex]

  return (
    <section id="features" className="section-pad relative overflow-hidden">
      {/* Section header */}
      <div className="max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.55 }}
          className="text-center mb-20"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/8 text-xs text-white/40 font-medium tracking-[0.15em] uppercase mb-5">
            Under the hood
          </div>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-black tracking-tighter text-white mb-4">
            Six modules. One engine.
            <br />
            <span className="gradient-text">Every step automated.</span>
          </h2>
          <p className="text-white/45 text-lg max-w-xl mx-auto">
            From research to publish — every step of the content machine runs on its own, intelligently.
          </p>
        </motion.div>
      </div>

      {/* ── Sticky scroll layout (desktop) ── */}
      <div className="max-w-7xl mx-auto px-6 hidden lg:block">
        <div className="grid grid-cols-2 gap-16 relative">

          {/* Left — sticky info panel */}
          <div className="sticky top-[100px] h-[calc(100vh-200px)] flex flex-col justify-center self-start">
            <AnimatePresence mode="wait">
              <motion.div
                key={active.id}
                initial={{ opacity: 0, y: 24, filter: 'blur(6px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -24, filter: 'blur(6px)' }}
                transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
              >
                {/* Number */}
                <div className="font-mono text-[72px] font-black leading-none mb-6 select-none"
                  style={{ color: `${active.accent}12`, WebkitTextStroke: `1px ${active.accent}30` }}>
                  {active.number}
                </div>

                {/* Subtitle */}
                <div className="text-sm font-mono tracking-[0.15em] uppercase mb-3" style={{ color: active.accent }}>
                  {active.subtitle}
                </div>

                {/* Title */}
                <h3 className="font-display text-4xl font-black tracking-tighter text-white mb-5 leading-tight">
                  {active.title}
                </h3>

                {/* Description */}
                <p className="text-white/50 text-lg leading-relaxed mb-8 max-w-sm">
                  {active.description}
                </p>

                {/* Tags */}
                <div className="flex flex-wrap gap-2">
                  {active.tags.map(tag => (
                    <span
                      key={tag}
                      className="text-xs font-medium px-3 py-1.5 rounded-full border"
                      style={{ color: active.accent, borderColor: `${active.accent}30`, background: `${active.accent}0E` }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                {/* Progress indicator */}
                <div className="flex items-center gap-2 mt-10">
                  {FEATURES.map((_, i) => (
                    <div
                      key={i}
                      className="h-0.5 rounded-full transition-all duration-500"
                      style={{
                        width: i === activeIndex ? '24px' : '6px',
                        background: i === activeIndex ? active.accent : 'rgba(255,255,255,0.12)',
                      }}
                    />
                  ))}
                </div>
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Right — scrolling feature visuals */}
          <div className="space-y-[30vh] py-[10vh]">
            {FEATURES.map((feature, i) => {
              const Visual = VISUALS[i]
              return (
                <div
                  key={feature.id}
                  ref={el => { itemRefs.current[i] = el }}
                  className="min-h-[60vh] flex items-center"
                >
                  <motion.div
                    initial={{ opacity: 0, x: 32 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true, margin: '-100px' }}
                    transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                    className="w-full"
                  >
                    {/* Gradient border wrapper */}
                    <div
                      className="rounded-2xl p-px"
                      style={{
                        background: i === activeIndex
                          ? `linear-gradient(135deg, ${feature.accent}50, ${feature.accent}15, transparent)`
                          : 'rgba(255,255,255,0.06)',
                        transition: 'background 0.4s ease',
                      }}
                    >
                      <div className="rounded-[15px] p-6 bg-[#0D0D18]">
                        <Visual accent={feature.accent} />
                      </div>
                    </div>
                  </motion.div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── Mobile fallback — bento cards ── */}
      <div className="max-w-7xl mx-auto px-6 lg:hidden grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
        {FEATURES.map((feature, i) => {
          const Icon = feature.icon
          const Visual = VISUALS[i]
          return (
            <motion.div
              key={feature.id}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.5, delay: i * 0.07 }}
              className="glass-card rounded-2xl p-5 border border-white/[0.08]"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: `${feature.accent}18`, border: `1px solid ${feature.accent}28` }}>
                  <Icon className="w-4 h-4" style={{ color: feature.accent }} />
                </div>
                <div>
                  <p className="text-white font-bold text-sm">{feature.title}</p>
                  <p className="text-[10px] font-mono" style={{ color: feature.accent }}>{feature.subtitle}</p>
                </div>
              </div>
              <p className="text-white/45 text-xs leading-relaxed mb-4">{feature.description}</p>
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.05]">
                <Visual accent={feature.accent} />
              </div>
            </motion.div>
          )
        })}
      </div>
    </section>
  )
}
