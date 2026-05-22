'use client'

import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Play, ArrowRight, Activity } from 'lucide-react'
import GlowButton from './ui/GlowButton'
import GradientOrb from './ui/GradientOrb'

const TERMINAL_LINES = [
  { text: 'Initialising Autoniix engine...', type: 'info', delay: 0 },
  { text: 'Loading AI research module', type: 'info', delay: 600 },
  { text: '✓ Gemini 2.5 Flash ready', type: 'success', delay: 1200 },
  { text: '✓ Claude Sonnet ready', type: 'success', delay: 1700 },
  { text: 'Analysing trending topics for "Finance"...', type: 'processing', delay: 2200 },
  { text: '✓ 47 high-potential topics found', type: 'success', delay: 3000 },
  { text: 'Generating script → "How compound interest works"', type: 'processing', delay: 3500 },
  { text: '✓ Script generated (1,847 words, score: 9.2/10)', type: 'success', delay: 4400 },
  { text: 'Synthesising voice with Fish Audio...', type: 'processing', delay: 4900 },
  { text: '✓ Voice track rendered (6m 42s)', type: 'success', delay: 5600 },
  { text: 'Rendering video with Remotion...', type: 'processing', delay: 6100 },
  { text: '✓ Video exported — uploading to YouTube', type: 'success', delay: 7000 },
  { text: '✓ Published. Next job queued.', type: 'success', delay: 7600 },
]

function TerminalLine({ text, type, visible }: { text: string; type: string; visible: boolean }) {
  if (!visible) return null
  const colorMap: Record<string, string> = {
    success: 'text-[#00D89F]',
    processing: 'text-[#6645C1]',
    info: 'text-white/50',
  }
  return (
    <div className="terminal-line animate-fade-in-up">
      <span className="terminal-prompt flex-shrink-0">›</span>
      <span className={colorMap[type] || 'text-white/70'}>{text}</span>
    </div>
  )
}

const LINE1 = ['Your', 'content', 'empire,']
const LINE2_PLAIN = 'fully '
const LINE2_GRADIENT = 'automated.'

export default function Hero() {
  const [visibleLines, setVisibleLines] = useState<number[]>([])
  const [cycle, setCycle] = useState(0)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const sectionRef = useRef<HTMLElement>(null)

  useEffect(() => {
    setVisibleLines([])
    const timeouts: ReturnType<typeof setTimeout>[] = []

    TERMINAL_LINES.forEach((line, i) => {
      const t = setTimeout(() => {
        setVisibleLines((prev) => [...prev, i])
      }, line.delay)
      timeouts.push(t)
    })

    const resetTimeout = setTimeout(() => {
      setCycle((c) => c + 1)
    }, 10000)
    timeouts.push(resetTimeout)

    return () => timeouts.forEach(clearTimeout)
  }, [cycle])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!sectionRef.current) return
      const rect = sectionRef.current.getBoundingClientRect()
      setMousePos({
        x: (e.clientX - rect.width / 2) / rect.width,
        y: (e.clientY - rect.height / 2) / rect.height,
      })
    }
    window.addEventListener('mousemove', handler, { passive: true })
    return () => window.removeEventListener('mousemove', handler)
  }, [])

  return (
    <section
      ref={sectionRef}
      className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden dot-grid scanlines"
    >
      {/* Gradient orbs — parallax on mouse */}
      <GradientOrb
        variant="green"
        size={700}
        className="top-[-100px] left-[-200px]"
        style={{
          opacity: 0.65,
          transform: `translate(${mousePos.x * -30}px, ${mousePos.y * -20}px)`,
          transition: 'transform 0.6s cubic-bezier(0.16,1,0.3,1)',
        }}
      />
      <GradientOrb
        variant="purple"
        size={600}
        className="top-[-50px] right-[-150px]"
        style={{
          opacity: 0.5,
          transform: `translate(${mousePos.x * 25}px, ${mousePos.y * -15}px)`,
          transition: 'transform 0.8s cubic-bezier(0.16,1,0.3,1)',
        }}
      />
      <GradientOrb
        variant="blue"
        size={500}
        className="bottom-[-50px] left-[30%]"
        style={{
          opacity: 0.4,
          transform: `translate(${mousePos.x * 20}px, ${mousePos.y * 20}px)`,
          transition: 'transform 1s cubic-bezier(0.16,1,0.3,1)',
        }}
      />

      {/* Content */}
      <div className="relative z-10 max-w-7xl mx-auto px-6 pt-28 pb-16 flex flex-col items-center text-center">
        {/* Eyebrow badge */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#00D89F]/25 bg-[#00D89F]/8 text-sm text-[#00D89F] font-medium mb-8"
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00D89F] opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00D89F]" />
          </span>
          ✦ AI-Powered Content Automation
        </motion.div>

        {/* Headline — word-by-word stagger reveal */}
        <h1 className="font-display text-[2.8rem] sm:text-6xl md:text-7xl lg:text-[90px] font-black leading-[1.05] tracking-tighter text-white mb-6 max-w-5xl">
          <span className="block">
            {LINE1.map((word, i) => (
              <motion.span
                key={word + i}
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.55, delay: 0.18 + i * 0.09, ease: [0.16, 1, 0.3, 1] }}
                className="inline-block mr-[0.22em]"
              >
                {word}
              </motion.span>
            ))}
          </span>
          <span className="block mt-1">
            <motion.span
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55, delay: 0.46, ease: [0.16, 1, 0.3, 1] }}
              className="inline-block mr-[0.22em] text-white/80"
            >
              {LINE2_PLAIN}
            </motion.span>
            <motion.span
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55, delay: 0.56, ease: [0.16, 1, 0.3, 1] }}
              className="inline-block gradient-text-animated font-serif-display"
            >
              {LINE2_GRADIENT}
            </motion.span>
          </span>
        </h1>

        {/* Sub-headline */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35 }}
          className="text-lg sm:text-xl text-white/55 max-w-2xl leading-relaxed mb-10"
        >
          Autoniix orchestrates AI to research, script, voice, render and publish —
          across every platform, at any scale. Set it up once. Let it run forever.
        </motion.p>

        {/* CTA row */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.5 }}
          className="flex flex-col sm:flex-row items-center gap-4 mb-6"
        >
          <GlowButton
            size="lg"
            onClick={() => window.open('https://dash.autoniix.com/register', '_blank')}
            className="flex items-center gap-2"
          >
            Start automating free
            <ArrowRight className="w-5 h-5" />
          </GlowButton>
          <GlowButton
            variant="ghost"
            size="lg"
            className="flex items-center gap-2"
          >
            <div className="w-7 h-7 rounded-full border border-white/20 flex items-center justify-center">
              <Play className="w-3 h-3 fill-white/80 text-white/80 ml-0.5" />
            </div>
            Watch demo
          </GlowButton>
        </motion.div>

        {/* Live activity badge */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.9 }}
          className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/8 bg-white/[0.03] text-xs text-white/45 mb-10"
        >
          <Activity className="w-3 h-3 text-[#00D89F]" />
          <span>14 videos published in the last hour</span>
          <span className="w-1 h-1 rounded-full bg-white/20" />
          <span>6 pipelines running now</span>
        </motion.div>

        {/* Terminal mockup */}
        <motion.div
          initial={{ opacity: 0, y: 40, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.65, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-3xl"
        >
          <div className="glass-card rounded-2xl overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.6),0_0_0_1px_rgba(255,255,255,0.08)] border border-white/10">
            {/* Terminal header */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-white/8 bg-white/[0.02]">
              <div className="w-3 h-3 rounded-full bg-[#FF5F57]" />
              <div className="w-3 h-3 rounded-full bg-[#FFBD2E]" />
              <div className="w-3 h-3 rounded-full bg-[#28CA41]" />
              <span className="ml-3 text-xs text-white/30 font-mono">Autoniix — ai-pipeline</span>
              <div className="ml-auto flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-[#00D89F] animate-pulse" />
                <span className="text-xs text-[#00D89F] font-mono">running</span>
              </div>
            </div>

            {/* Terminal body */}
            <div className="p-5 space-y-1.5 min-h-[260px] overflow-hidden">
              {TERMINAL_LINES.map((line, i) => (
                <TerminalLine
                  key={`${cycle}-${i}`}
                  text={line.text}
                  type={line.type}
                  visible={visibleLines.includes(i)}
                />
              ))}
              {visibleLines.length < TERMINAL_LINES.length && (
                <div className="terminal-line">
                  <span className="terminal-prompt">›</span>
                  <span className="text-white/40 animate-blink">█</span>
                </div>
              )}
            </div>
          </div>

          {/* Glow under terminal */}
          <div className="h-px bg-gradient-to-r from-transparent via-[#00D89F]/40 to-transparent mt-[-1px]" />
          <div className="h-8 bg-gradient-to-b from-[#00D89F]/8 to-transparent rounded-b-3xl mx-8 blur-sm" />
        </motion.div>
      </div>
    </section>
  )
}
