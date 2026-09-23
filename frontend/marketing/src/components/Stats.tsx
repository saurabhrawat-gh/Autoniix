import AnimatedCounter from "./ui/AnimatedCounter";
import Reveal from "./ui/Reveal";

const STATS = [
  { value: 10, suffix: "+", label: "Specialist AI models", sub: "orchestrated per video" },
  { value: 30, suffix: "+", label: "Automated quality gates", sub: "before anything publishes" },
  { value: 48, suffix: "+", label: "Cinematic components", sub: "code-driven, zero drift" },
  { value: 9.4, suffix: " / 10", label: "Average quality score", sub: "across all published videos", decimals: 1 },
];

export default function Stats() {
  return (
    <section className="relative py-16 md:py-20">
      <div className="hairline" />
      <div className="container-x grid grid-cols-2 lg:grid-cols-4 gap-8 py-14">
        {STATS.map((s, i) => (
          <Reveal key={s.label} delay={0.06 * i} className="text-center lg:text-left">
            <p className="text-4xl md:text-5xl font-bold tracking-tighter text-cream leading-none">
              {s.decimals ? (
                <>
                  {s.value}
                  {s.suffix}
                </>
              ) : (
                <AnimatedCounter value={s.value} suffix={s.suffix} />
              )}
            </p>
            <p className="mt-3 text-sm font-medium text-content-primary">{s.label}</p>
            <p className="text-xs text-content-tertiary mt-0.5">{s.sub}</p>
          </Reveal>
        ))}
      </div>
      <div className="hairline" />
    </section>
  );
}
