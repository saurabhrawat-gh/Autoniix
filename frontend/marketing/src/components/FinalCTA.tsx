import { ArrowRight } from "lucide-react";
import Button from "./ui/Button";
import Reveal from "./ui/Reveal";
import { STAGES } from "@/lib/pipeline";

export default function FinalCTA() {
  return (
    <section className="section">
      <div className="container-x">
        <Reveal className="panel noise relative overflow-hidden px-6 py-20 md:px-16 md:py-28 text-center">
          <div className="absolute inset-0 hero-spot opacity-90 pointer-events-none" />
          <div className="absolute inset-0 grid-bg pointer-events-none" />
          <div className="absolute -bottom-32 left-1/2 -translate-x-1/2 w-[640px] h-[320px] bg-brand opacity-[0.14] blur-[100px] rounded-full pointer-events-none" />

          <div className="relative">
            <div className="flex justify-center gap-2 mb-8">
              {STAGES.map((s) => (
                <span key={s.id} className="chip bg-surface-1 border border-border text-content-secondary">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.color }} />
                  {s.label}
                </span>
              ))}
            </div>
            <h2 className="t-h1 text-cream max-w-3xl mx-auto">
              Your next 20 videos are free. Your next 2,000 are automated.
            </h2>
            <p className="t-lead mt-6 max-w-xl mx-auto">
              Connect a channel, pick a niche and a voice, and watch the first video land in your review queue in under
              an hour.
            </p>
            <div className="mt-10 flex flex-col sm:flex-row justify-center gap-3">
              <Button href="https://dash.autoniix.com/register" size="lg" className="min-w-[220px]">
                Start automating free <ArrowRight className="w-4 h-4" />
              </Button>
              <Button href="mailto:sales@autoniix.com" variant="secondary" size="lg">
                Book a demo
              </Button>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
