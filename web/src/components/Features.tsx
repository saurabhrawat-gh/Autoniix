'use client'

import { motion } from 'framer-motion'
import { Brain, PenTool, Mic2, Film, BarChart3, Globe2 } from 'lucide-react'
import GlassCard from './ui/GlassCard'

const features = [
  {
    icon: Brain,
    title: 'AI Research Engine',
    description: 'Gemini 2.5 Flash + GPT-4o synthesise trending topics, analyse audience signals, and surface high-potential content ideas automatically.',
    accent: '#00D89F',
    large: true,
  },
  {
    icon: PenTool,
    title: 'Script Generation',
    description: 'Claude Sonnet writes cinematic, engaging scripts tailored to each niche. Fact-checked, quality-scored, and ready to render.',
    accent: '#6645C1',
    large: true,
  },
  {
    icon: Mic2,
    title: 'Voice Synthesis',
    description: 'Unique AI voice per profile. Fish Audio delivers broadcast-quality narration at a fraction of the cost.',
    accent: '#00D89F',
    large: false,
  },
  {
    icon: Film,
    title: 'Automated Rendering',
    description: 'Remotion-powered video engine with 48+ cinematic components. Code-driven, pixel-perfect output every time.',
    accent: '#6645C1',
    large: false,
  },
  {
    icon: BarChart3,
    title: 'Analytics Intelligence',
    description: 'Real-time performance signals feed back into the research loop — content gets smarter as it publishes.',
    accent: '#2563EB',
    large: false,
  },
  {
    icon: Globe2,
    title: 'Multi-Platform Scaling',
    description: '1 to 100+ profiles across any platform — zero additional effort. YouTube, Instagram, TikTok and beyond.',
    accent: '#00D89F',
    large: false,
  },
]

const container = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.09,
    },
  },
}

const item = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.16, 1, 0.3, 1] } },
}

export default function Features() {
  return (
    <section id="features" className="section-pad relative overflow-hidden">
      <div className="max-w-7xl mx-auto px-6">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.55 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/8 text-xs text-white/40 font-medium tracking-wider uppercase mb-4">
            Features
          </div>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-black tracking-tighter text-white mb-4">
            Everything you need to
            <br />
            <span className="gradient-text">dominate content</span>
          </h2>
          <p className="text-white/50 text-lg max-w-xl mx-auto">
            Six AI-powered modules that work together to take you from idea to published — without lifting a finger.
          </p>
        </motion.div>

        {/* Bento grid */}
        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-60px' }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          {/* Large cards (span 1 each in 3-col, but first two take more visual weight) */}
          {features.map((feature, i) => {
            const Icon = feature.icon
            const isLarge = feature.large
            return (
              <motion.div key={feature.title} variants={item} className={isLarge ? 'lg:col-span-1' : ''}>
                <GlassCard
                  hover
                  className={`p-6 h-full group ${isLarge ? 'min-h-[220px]' : 'min-h-[180px]'}`}
                  style={{
                    borderColor: `rgba(255,255,255,0.08)`,
                  }}
                >
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center mb-4 transition-transform duration-300 group-hover:scale-110"
                    style={{
                      background: `${feature.accent}18`,
                      border: `1px solid ${feature.accent}30`,
                    }}
                  >
                    <Icon
                      className="w-5 h-5"
                      style={{ color: feature.accent }}
                    />
                  </div>
                  <h3 className="text-white font-bold text-lg mb-2 tracking-tight">
                    {feature.title}
                  </h3>
                  <p className="text-white/50 text-sm leading-relaxed">
                    {feature.description}
                  </p>

                  {/* Accent glow on hover */}
                  <div
                    className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
                    style={{
                      background: `radial-gradient(ellipse at top left, ${feature.accent}08 0%, transparent 60%)`,
                    }}
                  />
                </GlassCard>
              </motion.div>
            )
          })}
        </motion.div>
      </div>
    </section>
  )
}
