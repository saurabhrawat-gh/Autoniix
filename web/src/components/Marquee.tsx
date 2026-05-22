export default function Marquee() {
  const items = [
    { name: 'OpenAI GPT-4o', icon: '◆' },
    { name: 'Anthropic Claude', icon: '◆' },
    { name: 'Google Gemini', icon: '◆' },
    { name: 'Fish Audio', icon: '◆' },
    { name: 'YouTube API', icon: '◆' },
    { name: 'Remotion', icon: '◆' },
    { name: 'Temporal', icon: '◆' },
    { name: 'PostgreSQL', icon: '◆' },
    { name: 'Redis', icon: '◆' },
    { name: 'MinIO', icon: '◆' },
  ]

  const doubled = [...items, ...items]

  return (
    <div className="relative py-14 border-y border-white/5 overflow-hidden">
      {/* Fade edges */}
      <div className="absolute left-0 top-0 bottom-0 w-24 bg-gradient-to-r from-[#0A0A0F] to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 top-0 bottom-0 w-24 bg-gradient-to-l from-[#0A0A0F] to-transparent z-10 pointer-events-none" />

      <div className="text-xs text-white/25 text-center font-medium tracking-[0.2em] uppercase mb-6">
        Powered by the world&apos;s best AI infrastructure
      </div>

      <div className="flex overflow-hidden">
        <div className="marquee-inner">
          {doubled.map((item, i) => (
            <div
              key={i}
              className="inline-flex items-center gap-2 text-white/35 hover:text-white/60 transition-colors duration-200 select-none"
            >
              <span className="text-[#00D89F]/50 text-xs">{item.icon}</span>
              <span className="text-sm font-medium whitespace-nowrap">{item.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
