"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Building2, UserCircle2, Youtube, Rocket, ArrowLeft, Check, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/lib/ui/button";
import { Input } from "@/lib/ui/input";
import { UrlPrefixInput } from "@/lib/ui/url-prefix-input";

const STEPS = [
  { id: 1, label: "Workspace", icon: Building2 },
  { id: 2, label: "Profile", icon: UserCircle2 },
  { id: 3, label: "Channel", icon: Youtube },
  { id: 4, label: "Done", icon: Rocket },
] as const;

interface WelcomePageProps {
  params: { workspace_slug: string };
}

export default function WelcomePage({ params }: WelcomePageProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const encryptedUserId = searchParams.get("u");

  const [step, setStep] = React.useState(1);
  const [wsName, setWsName] = React.useState("");
  const [wsSlug, setWsSlug] = React.useState(params.workspace_slug ?? "");
  const [displayName, setDisplayName] = React.useState("");
  const [role, setRole] = React.useState("");

  const totalSteps = STEPS.length;

  const next = () => setStep((s) => Math.min(s + 1, totalSteps));
  const back = () => setStep((s) => Math.max(s - 1, 1));

  const finish = () => {
    router.push(`/${params.workspace_slug}/overview`);
  };

  return (
    <div className="min-h-screen bg-surface-bg flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-onboarding">
        {/* Logo wordmark */}
        <div className="flex justify-center mb-8">
          <span className="text-h3 font-semibold tracking-tight text-content-primary">autoniix</span>
        </div>

        {/* Card */}
        <div className="bg-surface-0 border border-border rounded-xl overflow-hidden">
          {/* Step progress — labelled tabs */}
          <div className="flex items-center border-b border-border px-6 py-4 gap-0">
            {STEPS.map((s, i) => {
              const done = step > s.id;
              const active = step === s.id;
              return (
                <React.Fragment key={s.id}>
                  <button
                    type="button"
                    onClick={() => done && setStep(s.id)}
                    disabled={!done}
                    className={cn(
                      "flex items-center gap-1.5 text-xs font-medium transition-colors",
                      active
                        ? "text-accent"
                        : done
                          ? "text-content-secondary hover:text-content-primary cursor-pointer"
                          : "text-content-disabled cursor-default"
                    )}
                  >
                    <span
                      className={cn(
                        "w-5 h-5 rounded-full flex items-center justify-center text-[10px] border",
                        active
                          ? "border-accent bg-accent text-white"
                          : done
                            ? "border-accent/40 bg-accent/10 text-accent"
                            : "border-border bg-surface-1 text-content-disabled"
                      )}
                    >
                      {done ? <Check size={9} strokeWidth={3} /> : s.id}
                    </span>
                    <span>{s.label}</span>
                  </button>
                  {i < STEPS.length - 1 && (
                    <div className={cn("flex-1 h-px mx-2", step > s.id ? "bg-accent/30" : "bg-border")} />
                  )}
                </React.Fragment>
              );
            })}
          </div>

          {/* Back + Skip row */}
          {step > 1 && step < totalSteps && (
            <div className="flex items-center justify-between px-6 pt-3">
              <button
                type="button"
                onClick={back}
                className="flex items-center gap-1 text-xs text-content-tertiary hover:text-content-secondary transition-colors"
              >
                <ArrowLeft size={12} /> Back
              </button>
              <button
                type="button"
                onClick={next}
                className="text-xs text-content-tertiary hover:text-content-secondary transition-colors"
              >
                Skip
              </button>
            </div>
          )}

          <div className="px-8 pb-8 pt-5">
            {/* ── Step 1 — Create Workspace ── */}
            {step === 1 && (
              <StepShell title="Create your workspace" subtitle="Your private AI content factory.">
                <Input
                  label="Workspace name"
                  placeholder="My Brand Studio"
                  value={wsName}
                  onChange={(e) => {
                    setWsName(e.target.value);
                    setWsSlug(
                      e.target.value
                        .toLowerCase()
                        .replace(/\s+/g, "-")
                        .replace(/[^a-z0-9-]/g, "")
                    );
                  }}
                  autoFocus
                />
                <UrlPrefixInput
                  label="Workspace URL"
                  prefix="dash.autoniix.com/"
                  value={wsSlug}
                  onChange={(e) => setWsSlug(e.target.value)}
                  placeholder="my-brand-studio"
                />
                <Button size="lg" className="w-full" onClick={next} disabled={!wsName.trim()}>
                  Create workspace <ChevronRight size={14} />
                </Button>
              </StepShell>
            )}

            {/* ── Step 2 — Set Up Profile ── */}
            {step === 2 && (
              <StepShell title="Set up your profile" subtitle="How should teammates know you?">
                <div className="flex justify-center">
                  <button
                    type="button"
                    className="w-16 h-16 rounded-full bg-surface-2 border-2 border-dashed border-border hover:border-accent flex items-center justify-center text-content-tertiary hover:text-accent transition-colors"
                    aria-label="Upload avatar"
                  >
                    <UserCircle2 size={28} />
                  </button>
                </div>
                <Input
                  label="Display name"
                  placeholder="Your name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
                <Input
                  label="Title / Role"
                  placeholder="Content strategist…"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                />
                <Button size="lg" className="w-full" onClick={next}>
                  Continue <ChevronRight size={14} />
                </Button>
              </StepShell>
            )}

            {/* ── Step 3 — Connect YouTube ── */}
            {step === 3 && (
              <StepShell title="Connect your YouTube channel" subtitle="Link your channel to start automating content.">
                <Button
                  size="lg"
                  className="w-full"
                  onClick={() => router.push("/dashboard/channels?connect=1")}
                  leftIcon={<Youtube size={16} />}
                >
                  Connect with YouTube
                </Button>
              </StepShell>
            )}

            {/* ── Step 4 — Done ── */}
            {step === 4 && (
              <StepShell
                title="Your workspace is ready."
                subtitle={`${wsName || "Your workspace"} is live at dash.autoniix.com/${wsSlug}`}
              >
                <div className="flex justify-center py-4">
                  <div className="w-20 h-20 rounded-full bg-accent-light flex items-center justify-center">
                    <Rocket size={36} className="text-accent" />
                  </div>
                </div>
                <ul className="space-y-2 text-sm text-content-secondary">
                  {["Workspace created", displayName ? "Profile set up" : null].filter(Boolean).map((item) => (
                    <li key={item} className="flex items-center gap-2">
                      <Check size={13} className="text-status-success shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
                <Button size="lg" className="w-full" onClick={finish}>
                  Go to dashboard <ChevronRight size={14} />
                </Button>
              </StepShell>
            )}
          </div>
        </div>

        {encryptedUserId && <input type="hidden" name="u" value={encryptedUserId} />}

        <p className="text-center text-caption text-content-muted mt-6">
          Already have a workspace?{" "}
          <a href="/login" className="text-accent hover:underline">
            Sign in
          </a>
        </p>
      </div>
    </div>
  );
}

function StepShell({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-h2 font-semibold tracking-tight text-content-primary">{title}</h2>
        {subtitle && <p className="mt-1 text-body-sm text-content-secondary">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}
