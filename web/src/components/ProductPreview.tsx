'use client'

import { motion, useScroll, useTransform } from 'framer-motion'
import { useRef } from 'react'

const annotations = [
  { label: '🟢 AI running', position: 'top-[12%] right-[-8%]', delay: 0.2 },
  { label: '📊 Live analytics', position: 'top-[38%] left-[-10%]', delay: 0.4 },
  { label: '⚡ Queue: 12 jobs', position: 'bottom-[22%] right-[-6%]', delay: 0.6 },
  { label: '✓ 3 published today', position: 'bottom-[8%] left-[5%]', delay: 0.8 },
]

export default function ProductPreview() {
  const sectionRef = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ['start end', 'end start'],
  })
  const y = useTransform(scrollYProgress, [0, 1], [40, -40])

  return (
    <section id="preview" className="section-pad relative overflow-hidden" ref={sectionRef}>
      {/* Subtle divider */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/8 to-transparent" />

      <div className="max-w-7xl mx-auto px-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.55 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/8 text-xs text-white/40 font-medium tracking-wider uppercase mb-4">
            Dashboard
          </div>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-black tracking-tighter text-white mb-4">
            A command centre
            <br />
            <span className="gradient-text">built for creators</span>
          </h2>
          <p className="text-white/50 text-lg max-w-lg mx-auto">
            Access everything from a single, beautiful dashboard. No clutter, no confusion.
          </p>
        </motion.div>

        {/* Dashboard mock */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          style={{ y }}
          className="relative max-w-5xl mx-auto"
        >
          {/* Dashboard frame */}
          <div className="relative rounded-2xl overflow-hidden border border-white/10 shadow-[0_0_80px_rgba(0,0,0,0.6),0_0_0_1px_rgba(255,255,255,0.08)] group hover:border-[#00D89F]/20 transition-colors duration-500">
            {/* Window chrome */}
            <div className="flex items-center gap-2 px-4 py-3 bg-white/[0.03] border-b border-white/8">
              <div className="w-3 h-3 rounded-full bg-[#FF5F57]" />
              <div className="w-3 h-3 rounded-full bg-[#FFBD2E]" />
              <div className="w-3 h-3 rounded-full bg-[#28CA41]" />
              <span className="ml-3 text-xs text-white/25 font-mono">dash.autoniix.com — Dashboard</span>
              <div className="ml-auto flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-[#00D89F] animate-pulse" />
                <span className="text-xs text-white/30 font-mono">3 jobs running</span>
              </div>
            </div>

            {/* Dashboard body — styled mock UI */}
            <div className="bg-[#0F1015] p-6" style={{ minHeight: 420 }}>
              {/* Top stats row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                {[
                  { label: 'Videos Published', value: '247', trend: '+12 this week' },
                  { label: 'Active Profiles', value: '8', trend: '2 platforms' },
                  { label: 'AI Jobs Running', value: '3', trend: 'real-time' },
                  { label: 'Total Views', value: '1.2M', trend: '+18% this month' },
                ].map((stat) => (
                  <div key={stat.label} className="glass-card rounded-xl p-4">
                    <p className="text-white/40 text-xs mb-1">{stat.label}</p>
                    <p className="text-white font-bold text-xl tracking-tight">{stat.value}</p>
                    <p className="text-[#00D89F] text-xs mt-1">{stat.trend}</p>
                  </div>
                ))}
              </div>

              {/* Main content area */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {/* Job queue */}
                <div className="md:col-span-2 glass-card rounded-xl p-4">
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-white/70 text-sm font-semibold">Active Pipeline</p>
                    <span className="text-xs text-[#00D89F] font-mono bg-[#00D89F]/10 px-2 py-0.5 rounded-full">3 running</span>
                  </div>
                  <div className="space-y-3">
                    {[
                      { title: 'How compound interest works', stage: 'Rendering video', progress: 72, color: '#00D89F' },
                      { title: 'Sleep cycle optimisation', stage: 'Voice synthesis', progress: 45, color: '#6645C1' },
                      { title: 'Gut microbiome basics', stage: 'Script generation', progress: 20, color: '#2563EB' },
                    ].map((job) => (
                      <div key={job.title}>
                        <div className="flex items-center justify-between mb-1.5">
                          <p className="text-white/80 text-xs font-medium truncate max-w-[200px]">{job.title}</p>
                          <span className="text-white/35 text-xs ml-2 flex-shrink-0">{job.stage}</span>
                        </div>
                        <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{ width: `${job.progress}%`, background: job.color }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Quick stats */}
                <div className="glass-card rounded-xl p-4">
                  <p className="text-white/70 text-sm font-semibold mb-4">Top Profiles</p>
                  <div className="space-y-3">
                    {[
                      { name: 'Body Signals', vids: 84, platform: 'YT' },
                      { name: 'Money Decoded', vids: 61, platform: 'YT' },
                      { name: 'Mind Shifts', vids: 53, platform: 'YT' },
                    ].map((profile) => (
                      <div key={profile.name} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-md bg-[#00D89F]/15 flex items-center justify-center text-[10px] text-[#00D89F] font-bold">
                            {profile.name[0]}
                          </div>
                          <span className="text-white/70 text-xs">{profile.name}</span>
                        </div>
                        <span className="text-white/40 text-xs">{profile.vids} videos</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Green glow under frame */}
          <div className="absolute inset-x-8 -bottom-6 h-12 bg-[#00D89F]/8 blur-2xl rounded-full" />

          {/* Floating annotation chips */}
          {annotations.map((ann) => (
            <motion.div
              key={ann.label}
              initial={{ opacity: 0, scale: 0.85 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: ann.delay }}
              className={`absolute hidden lg:flex items-center gap-1.5 glass-card px-3 py-1.5 rounded-full border border-white/12 text-xs text-white/70 font-medium shadow-lg ${ann.position}`}
            >
              {ann.label}
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}
