const MODELS = [
  ["Gemini 2.5 Flash", "research"],
  ["Claude Sonnet", "scripting"],
  ["GPT-4o", "fact-check · direction"],
  ["GPT-4o mini", "quality control"],
  ["Fish Audio", "voice"],
  ["Veo", "generative b-roll"],
  ["Remotion", "composition"],
  ["FFmpeg", "encode"],
  ["YouTube Data API", "publish"],
  ["Whisper", "captions"],
];

export default function ModelStrip() {
  const items = [...MODELS, ...MODELS];
  return (
    <section
      aria-label="Models orchestrated by Autoniix"
      className="relative py-10 border-y border-border bg-surface-bg/60"
    >
      <p className="eyebrow text-center mb-6">One pipeline · ten specialist models · zero glue code</p>
      <div className="fade-x overflow-hidden">
        <div className="flex w-max gap-3 animate-marquee hover:[animation-play-state:paused]">
          {items.map(([name, role], i) => (
            <div key={`${name}-${i}`} className="card px-4 py-2.5 flex items-center gap-3 whitespace-nowrap">
              <span className="w-1.5 h-1.5 rounded-full bg-accent/70" />
              <span className="text-sm font-medium text-content-primary">{name}</span>
              <span className="font-mono text-[10px] uppercase tracking-wider text-content-tertiary">{role}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
