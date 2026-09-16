export default function Marquee() {
  const items = [
    { name: "OpenAI GPT-4o", icon: "◆" },
    { name: "Anthropic Claude", icon: "◆" },
    { name: "Google Gemini", icon: "◆" },
    { name: "Fish Audio", icon: "◆" },
    { name: "YouTube API", icon: "◆" },
    { name: "Remotion", icon: "◆" },
    { name: "Temporal", icon: "◆" },
    { name: "PostgreSQL", icon: "◆" },
    { name: "Redis", icon: "◆" },
    { name: "MinIO", icon: "◆" },
  ];

  const doubled = [...items, ...items];

  return (
    <div className="relative py-14 border-y overflow-hidden" style={{ borderColor: "var(--border)" }}>
      {/* Fade edges — theme-aware */}
      <div
        className="absolute left-0 top-0 bottom-0 w-24 z-10 pointer-events-none"
        style={{ background: "linear-gradient(90deg, var(--bg-page) 0%, transparent 100%)" }}
      />
      <div
        className="absolute right-0 top-0 bottom-0 w-24 z-10 pointer-events-none"
        style={{ background: "linear-gradient(-90deg, var(--bg-page) 0%, transparent 100%)" }}
      />

      <div className="t-eyebrow text-center mb-6" style={{ color: "var(--text-faint)" }}>
        Powered by the world&apos;s best AI infrastructure
      </div>

      <div className="flex overflow-hidden">
        <div className="marquee-inner">
          {doubled.map((item, i) => (
            <div
              key={i}
              className="inline-flex items-center gap-2 transition-colors duration-200 select-none t-body-sm"
              style={{ color: "var(--text-muted)" }}
            >
              <span style={{ color: "var(--accent)", opacity: 0.6, fontSize: "0.75rem" }}>{item.icon}</span>
              <span className="whitespace-nowrap" style={{ fontWeight: 500 }}>
                {item.name}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
