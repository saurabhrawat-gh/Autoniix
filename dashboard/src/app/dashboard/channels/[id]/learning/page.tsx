'use client';

/**
 * Phase 5 polish — Learning Insights panel.
 *
 * Surfaces what the self-learning loop has actually learned for one
 * channel, in four blocks:
 *   - Performance memory (the literal text the LLM sees on each run)
 *   - Bandit state per niche (hook style + pacing arms with win-rates)
 *   - Drift status (last AUC vs current AUC, retrain flag)
 *   - 30-day tier distribution (S/A/B/C/D counts)
 *
 * All data comes from a single endpoint: /api/channels/:id/learning-insights.
 * The page is read-only — it's an audit lens, not a control surface.
 */

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { api, isLoggedIn } from '@/lib/api';
import { cn } from '@/lib/utils';
import { PageHeader } from '@/lib/components/PageHeader';
import { SkeletonCard } from '@/lib/components/Skeleton';

type Bandit = {
  type: string;
  arm: string;
  pulls: number;
  win_rate: number | null;
  alpha: number;
  beta: number;
};

type Drift = {
  model_name: string;
  last_trained_at: string | null;
  last_auc: number | null;
  current_auc: number | null;
  needs_retrain: boolean;
  sample_count: number | null;
} | null;

type Insights = {
  channel_id: string;
  performance_memory: string;
  performance_memory_attached: boolean;
  bandits: Bandit[];
  drift: Drift;
  tier_distribution_30d: Record<'S' | 'A' | 'B' | 'C' | 'D', number>;
};

export default function ChannelLearningPage() {
  const router = useRouter();
  const params = useParams();
  const channelId = params.id as string;
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    api.channelLearningInsights(channelId)
      .then(res => setInsights(res?.data || null))
      .catch(err => setError(err?.message || 'Failed to load insights'))
      .finally(() => setLoading(false));
  }, [router, channelId]);

  // Group bandits by type so the UI shows hook_style and pacing_strategy
  // as separate blocks. Within each block, the highest win-rate arm is
  // highlighted — that's the one currently steering production prompts.
  const banditsByType: Record<string, Bandit[]> = {};
  for (const b of insights?.bandits || []) {
    (banditsByType[b.type] ||= []).push(b);
  }

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader
        title="Learning Insights"
        subtitle={`What the self-learning loop has learned for ${channelId}`}
        crumbs={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: channelId,    href: `/dashboard/channels/${channelId}` },
          { label: 'Learning' },
        ]}
        containerClassName="max-w-5xl"
      />
      <main className="max-w-5xl mx-auto w-full px-6 py-8 space-y-6">
        {loading && <SkeletonCard />}
        {error && (
          <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3">{error}</div>
        )}

        {insights && !loading && (
          <>
            {/* ── 1. Tier distribution ─────────────────── */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold text-content-primary mb-1">
                Performance tiers (last 30 days)
              </h2>
              <p className="text-xs text-content-tertiary mb-4">
                S = top 10%, D = bottom. Tier mix is the cheapest signal of channel health.
              </p>
              <div className="grid grid-cols-5 gap-3">
                {(['S', 'A', 'B', 'C', 'D'] as const).map(tier => {
                  const n = insights.tier_distribution_30d[tier] || 0;
                  const total = Object.values(insights.tier_distribution_30d).reduce((a, b) => a + b, 0);
                  const pct = total > 0 ? Math.round((n / total) * 100) : 0;
                  const color = tier === 'S' ? 'bg-status-success/10 text-status-success border-status-success/30'
                    : tier === 'A' ? 'bg-accent/10 text-accent border-accent/30'
                    : tier === 'D' ? 'bg-status-error/10 text-status-error border-status-error/30'
                    : 'bg-surface-1 text-content-tertiary border-border';
                  return (
                    <div key={tier} className={cn('rounded-md border-2 p-3 text-center', color)}>
                      <div className="text-2xl font-bold leading-none">{n}</div>
                      <div className="text-xs opacity-70 mt-1">Tier {tier}</div>
                      {total > 0 && <div className="text-[10px] opacity-50 mt-0.5">{pct}%</div>}
                    </div>
                  );
                })}
              </div>
            </section>

            {/* ── 2. Bandit state ─────────────────────── */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold text-content-primary mb-1">
                Bandit arms — currently steering script generation
              </h2>
              <p className="text-xs text-content-tertiary mb-4">
                Thompson sampling picks one arm per type per run. Win-rate ≈ rewards / pulls.
                The highest-rate arm wins more often but exploration keeps the others alive.
              </p>
              {Object.keys(banditsByType).length === 0 ? (
                <div className="text-xs text-content-tertiary italic py-4">
                  No bandit state yet. Arms initialise after the first few delivered videos for this niche.
                </div>
              ) : (
                <div className="space-y-4">
                  {Object.entries(banditsByType).map(([type, arms]) => {
                    const sorted = [...arms].sort((a, b) =>
                      (b.win_rate ?? -1) - (a.win_rate ?? -1)
                    );
                    return (
                      <div key={type}>
                        <h3 className="text-xs font-semibold text-content-secondary mb-2 uppercase tracking-wide">
                          {type.replace(/_/g, ' ')}
                        </h3>
                        <div className="space-y-1">
                          {sorted.map((b, i) => {
                            const winning = i === 0 && b.pulls > 0;
                            return (
                              <div key={b.arm}
                                className={cn(
                                  'flex items-center justify-between text-xs rounded-md px-3 py-2 border',
                                  winning ? 'border-accent/40 bg-accent/5' : 'border-border bg-surface-0'
                                )}>
                                <span className="flex items-center gap-2">
                                  {winning && <span className="text-accent">★</span>}
                                  <span className="font-medium text-content-primary">{b.arm}</span>
                                </span>
                                <span className="flex items-center gap-4 text-content-tertiary tabular-nums">
                                  <span>{b.pulls} pulls</span>
                                  <span>
                                    {b.win_rate === null ? '—' : `${(b.win_rate * 100).toFixed(1)}% win`}
                                  </span>
                                  <span className="text-[10px] opacity-60">
                                    α={b.alpha.toFixed(1)} β={b.beta.toFixed(1)}
                                  </span>
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            {/* ── 3. Drift status ─────────────────────── */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold text-content-primary mb-1">
                Script-success model — drift status
              </h2>
              <p className="text-xs text-content-tertiary mb-4">
                Trained periodically on real engagement. AUC drop &gt; threshold triggers retrain.
              </p>
              {!insights.drift ? (
                <div className="text-xs text-content-tertiary italic">
                  No model snapshot yet. The trainer needs ≥15 delivered videos before it produces one.
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-4">
                  <Stat label="Last AUC"
                    value={insights.drift.last_auc !== null ? insights.drift.last_auc.toFixed(3) : '—'} />
                  <Stat label="Current AUC"
                    value={insights.drift.current_auc !== null ? insights.drift.current_auc.toFixed(3) : '—'} />
                  <Stat label="Retrain needed"
                    value={insights.drift.needs_retrain ? 'YES' : 'no'}
                    accent={insights.drift.needs_retrain ? 'warn' : 'ok'} />
                </div>
              )}
            </section>

            {/* ── 4. Performance memory (raw text) ────── */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold text-content-primary mb-1">
                Performance memory injected into prompts
              </h2>
              <p className="text-xs text-content-tertiary mb-3">
                Exact text the ideation + script services prepend to the LLM user prompt.
                Empty until the channel has measured wins and flops.
              </p>
              {insights.performance_memory_attached ? (
                <pre className="text-[11px] leading-relaxed bg-surface-0 border border-border rounded-md p-3 overflow-x-auto whitespace-pre-wrap font-mono text-content-secondary">
                  {insights.performance_memory}
                </pre>
              ) : (
                <div className="text-xs text-content-tertiary italic py-4">
                  Cold start — no measured engagement above the noise floor yet.
                  This block will populate once analytics has classified a few videos as S/A or D.
                </div>
              )}
            </section>

            <div className="flex justify-end">
              <Link href={`/dashboard/channels/${channelId}`}
                className="text-xs text-content-tertiary hover:text-content-primary">
                ← back to channel
              </Link>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value, accent }: {
  label: string; value: string; accent?: 'ok' | 'warn'
}) {
  const color = accent === 'warn' ? 'text-status-warning'
    : accent === 'ok' ? 'text-status-success'
    : 'text-content-primary';
  return (
    <div className="rounded-md border border-border bg-surface-0 p-3">
      <div className="text-[10px] uppercase tracking-wide text-content-tertiary">{label}</div>
      <div className={cn('text-lg font-semibold mt-1 tabular-nums', color)}>{value}</div>
    </div>
  );
}
