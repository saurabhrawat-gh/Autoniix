'use client';

/**
 * Phase 6 — Fleet Health panel.
 *
 * Read-only dashboard for ops. Auto-refreshes every 10s.
 * Single endpoint hit (`/api/fleet-health`), so a slow service can only
 * delay the page by ~3.5s (the per-probe timeout × the gather concurrency).
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { systemApi } from '@/lib/api-v2';
import { isLoggedIn } from '@/lib/api';
import { cn } from '@/lib/utils';
import { PageHeader } from '@/lib/components/PageHeader';
import { SkeletonCard } from '@/lib/components/Skeleton';

type Probe = { name: string; ok: boolean; status_code: number; latency_ms: number; error?: string };

type FleetData = {
  overall_ok: boolean;
  services: { ok_count: number; total: number; probes: Probe[] };
  db_pool: { size: number; idle: number; min_size: number; max_size: number; pressure: number | null };
  remotion: { ok: boolean; active?: number; waiting?: number; max?: number; memory_mb?: number; error?: string; status_code?: number };
  scale_config: {
    temporal_production_max_activities: number;
    temporal_scheduler_max_activities: number;
    db_statement_timeout_ms: number;
  };
  pressure_24h: { quality_gate_blocks: number | null; video_failures: number | null };
  gate_calibration?: {
    ok: boolean;
    niches_calibrated?: number;
    dims_auto?: number;
    dims_default?: number;
    last_run?: string | null;
    error?: string;
  };
  niche_pulse?: {
    ok: boolean;
    embedded_rows?: number;
    niches_with_data?: number;
    last_refresh?: string | null;
    error?: string;
  };
  retention_coverage?: {
    ok: boolean;
    eligible?: number;
    with_curve?: number;
    coverage?: number | null;
    last_fetch?: string | null;
    error?: string;
  };
  diversity_floor?: {
    ok: boolean;
    picks_7d?: number;
    forced_7d?: number;
    force_rate?: number | null;
    error?: string;
  };
  calibration?: {
    ok: boolean;
    n?: number;
    brier?: number | null;
    ece?: number | null;
    weighted_fraction?: number | null;
    mean_sample_weight?: number | null;
    error?: string;
  };
  health?: {
    score: number | null;
    band: 'green' | 'yellow' | 'red' | 'unknown';
    n_active?: number;
    n_total?: number;
    subsystems?: Array<{
      name: string;
      score: number | null;
      weight: number;
      reason: string;
    }>;
    error?: string;
  };
};

const SUBSYSTEM_LABELS: Record<string, string> = {
  services:           'Services',
  db_pool:            'DB pool',
  pressure_24h:       'Backpressure (24h)',
  gate_calibration:   'Gate calibration',
  niche_pulse:        'Niche pulse',
  retention_coverage: 'Retention coverage',
  diversity_floor:    'Diversity floor',
  calibration:        'Prediction calibration',
};

const REFRESH_MS = 10_000;

export default function FleetPage() {
  const router = useRouter();
  const [data, setData] = useState<FleetData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    let alive = true;

    const tick = async () => {
      try {
        const res = await systemApi.fleetHealth();
        if (!alive) return;
        setData(res?.data || null);
        setError('');
        setLastUpdated(Date.now());
      } catch (e: any) {
        if (!alive) return;
        setError(e?.message || 'Failed to load fleet health');
      } finally {
        if (alive) setLoading(false);
      }
    };

    tick();
    const id = setInterval(tick, REFRESH_MS);
    return () => { alive = false; clearInterval(id); };
  }, [router]);

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader
        title="Fleet Health"
        subtitle="Live view of services, DB pool, render queue, and recent backpressure"
        crumbs={[{ label: 'Dashboard', href: '/dashboard' }, { label: 'Fleet' }]}
        containerClassName="max-w-5xl"
      />
      <main className="max-w-5xl mx-auto w-full px-6 py-8 space-y-6">
        {loading && <SkeletonCard />}
        {error && (
          <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3">{error}</div>
        )}

        {data && !loading && (
          <>
            {/* Phase 12 — System health hero ─────────── */}
            {data.health && (
              <section
                className={cn(
                  'card p-6 border-2',
                  data.health.band === 'green'  && 'border-status-success/40',
                  data.health.band === 'yellow' && 'border-status-warning/40',
                  data.health.band === 'red'    && 'border-status-error/50',
                  data.health.band === 'unknown' && 'border-content-tertiary/30',
                )}
              >
                <div className="flex items-start justify-between gap-6">
                  <div className="flex-1">
                    <div className="text-xs uppercase tracking-wider text-content-tertiary mb-1">
                      System health
                    </div>
                    <div className="flex items-baseline gap-3">
                      <div className={cn(
                        'text-5xl font-bold tabular-nums',
                        data.health.band === 'green'  && 'text-status-success',
                        data.health.band === 'yellow' && 'text-status-warning',
                        data.health.band === 'red'    && 'text-status-error',
                        data.health.band === 'unknown' && 'text-content-tertiary',
                      )}>
                        {data.health.score !== null && data.health.score !== undefined
                          ? Math.round(data.health.score)
                          : '—'}
                      </div>
                      <div className="text-content-tertiary text-sm">/100</div>
                      <div className={cn(
                        'ml-auto inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-[11px] font-semibold uppercase tracking-wider border',
                        data.health.band === 'green'   && 'bg-status-success/10 text-status-success border-status-success/30',
                        data.health.band === 'yellow'  && 'bg-status-warning/10 text-status-warning border-status-warning/30',
                        data.health.band === 'red'     && 'bg-status-error/10 text-status-error border-status-error/30',
                        data.health.band === 'unknown' && 'bg-content-tertiary/10 text-content-tertiary border-content-tertiary/30',
                      )}>
                        {data.health.band}
                      </div>
                    </div>
                    {data.health.n_active !== undefined && data.health.n_total !== undefined && (
                      <div className="mt-2 text-xs text-content-tertiary">
                        Weighted across {data.health.n_active} of {data.health.n_total} subsystems reporting.
                        {data.health.n_active < data.health.n_total &&
                          ` ${data.health.n_total - data.health.n_active} not yet reporting (cold start).`}
                      </div>
                    )}
                  </div>
                </div>

                {/* Subsystem breakdown ─────────── */}
                {data.health.subsystems && data.health.subsystems.length > 0 && (
                  <div className="mt-5 pt-5 border-t border-content-tertiary/10">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2">
                      {data.health.subsystems.map(sub => (
                        <div key={sub.name} className="flex items-center gap-3 text-xs">
                          <div className={cn(
                            'w-2 h-2 rounded-full shrink-0',
                            sub.score === null && 'bg-content-tertiary/40',
                            sub.score !== null && sub.score >= 80 && 'bg-status-success',
                            sub.score !== null && sub.score >= 50 && sub.score < 80 && 'bg-status-warning',
                            sub.score !== null && sub.score < 50 && 'bg-status-error',
                          )} />
                          <div className="flex-1 min-w-0">
                            <span className="font-medium text-content-primary">
                              {SUBSYSTEM_LABELS[sub.name] || sub.name}
                            </span>
                            <span className="text-content-tertiary"> · {sub.reason}</span>
                          </div>
                          <div className="tabular-nums text-content-tertiary shrink-0">
                            {sub.score === null ? '—' : Math.round(sub.score)}
                            <span className="opacity-50"> ×{sub.weight}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* Overall + freshness ─────────── */}
            <div className="flex items-center justify-between">
              <div className={cn(
                'inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border',
                data.overall_ok
                  ? 'bg-status-success/10 text-status-success border-status-success/30'
                  : 'bg-status-error/10 text-status-error border-status-error/30'
              )}>
                <span className={cn(
                  'w-2 h-2 rounded-full',
                  data.overall_ok ? 'bg-status-success' : 'bg-status-error animate-pulse'
                )} />
                {data.overall_ok ? 'All systems nominal' : 'Degraded'}
              </div>
              {lastUpdated && (
                <div className="text-[11px] text-content-tertiary">
                  Updated {Math.round((Date.now() - lastUpdated) / 1000)}s ago · auto-refresh every 10s
                </div>
              )}
            </div>

            {/* Services grid ─────────── */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold text-content-primary mb-1">
                Services <span className="text-content-tertiary">({data.services.ok_count}/{data.services.total} healthy)</span>
              </h2>
              <p className="text-xs text-content-tertiary mb-4">
                Each probe has a 3-second timeout. p99 latency is the leading indicator that a service is about to fall over.
              </p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {data.services.probes.map(p => (
                  <div key={p.name}
                    className={cn(
                      'rounded-md border-2 p-2.5',
                      p.ok ? 'border-status-success/20 bg-status-success/5'
                           : 'border-status-error/30 bg-status-error/5'
                    )}>
                    <div className="flex items-center justify-between text-xs">
                      <span className={cn('font-medium',
                        p.ok ? 'text-content-primary' : 'text-status-error')}>
                        {p.name}
                      </span>
                      <span className="text-content-tertiary tabular-nums">
                        {p.ok ? `${p.latency_ms}ms` : (p.error || `HTTP ${p.status_code}`)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* DB pool + Remotion + 24h pressure ─────── */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <section className="card p-5">
                <h2 className="text-sm font-semibold text-content-primary mb-2">DB pool</h2>
                <Stat label="In use" value={`${data.db_pool.size} / ${data.db_pool.max_size}`} />
                <Stat label="Idle" value={String(data.db_pool.idle)} />
                <Stat label="Pressure"
                  value={data.db_pool.pressure !== null ? `${Math.round(data.db_pool.pressure * 100)}%` : '—'}
                  accent={
                    data.db_pool.pressure !== null && data.db_pool.pressure > 0.85 ? 'warn'
                    : data.db_pool.pressure !== null && data.db_pool.pressure > 0.5  ? undefined
                    : 'ok'
                  } />
              </section>

              <section className="card p-5">
                <h2 className="text-sm font-semibold text-content-primary mb-2">Render queue</h2>
                {data.remotion.ok ? (
                  <>
                    <Stat label="Active" value={`${data.remotion.active ?? 0} / ${data.remotion.max ?? 0}`} />
                    <Stat label="Waiting" value={String(data.remotion.waiting ?? 0)}
                      accent={(data.remotion.waiting ?? 0) > 5 ? 'warn' : undefined} />
                    <Stat label="Memory" value={`${data.remotion.memory_mb ?? 0} MB`} />
                  </>
                ) : (
                  <div className="text-xs text-status-error">
                    Unreachable {data.remotion.error ? `(${data.remotion.error})` : ''}
                  </div>
                )}
              </section>

              <section className="card p-5">
                <h2 className="text-sm font-semibold text-content-primary mb-2">Last 24h</h2>
                <Stat label="Quality-gate blocks"
                  value={data.pressure_24h.quality_gate_blocks?.toString() ?? '—'} />
                <Stat label="Failed videos"
                  value={data.pressure_24h.video_failures?.toString() ?? '—'}
                  accent={(data.pressure_24h.video_failures ?? 0) > 0 ? 'warn' : 'ok'} />
              </section>
            </div>

            {/* Niche pulse (Phase 8) ─────────── */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold text-content-primary mb-1">
                Niche pulse
              </h2>
              <p className="text-xs text-content-tertiary mb-4">
                External saturation signal: recent competitor videos with title embeddings, used by the opportunity scorer to down-weight crowded topics. Refreshed weekly per niche.
              </p>
              {!data.niche_pulse?.ok ? (
                <div className="text-xs text-content-tertiary italic">
                  Pulse refresh hasn't run yet (no embedded competitor videos).
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-3">
                  <Stat label="Niches with data"
                    value={String(data.niche_pulse.niches_with_data ?? 0)} />
                  <Stat label="Embedded videos"
                    value={String(data.niche_pulse.embedded_rows ?? 0)}
                    accent={(data.niche_pulse.embedded_rows ?? 0) > 0 ? 'ok' : undefined} />
                  <Stat label="Freshness"
                    value={data.niche_pulse.last_refresh
                      ? `${Math.round((Date.now() - new Date(data.niche_pulse.last_refresh).getTime()) / (3600 * 1000))}h`
                      : '—'}
                    accent={
                      data.niche_pulse.last_refresh
                        && (Date.now() - new Date(data.niche_pulse.last_refresh).getTime()) > 14 * 24 * 3600 * 1000
                        ? 'warn' : 'ok'
                    } />
                </div>
              )}
            </section>

            {/* Diversity floor (Phase 10) ─────────── */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold text-content-primary mb-1">
                Diversity floor
              </h2>
              <p className="text-xs text-content-tertiary mb-4">
                Anti-mode-collapse for the bandits. The floor monitors per-channel arm-pick entropy and forces exploration when bandits start repeating themselves. Force rate of 5-15% is healthy; sustained &gt;25% suggests the threshold is too aggressive.
              </p>
              {!data.diversity_floor?.ok ? (
                <div className="text-xs text-content-tertiary italic">
                  No bandit picks audited yet (table empty or workflow off).
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-3">
                  <Stat label="Picks (7d)"
                    value={String(data.diversity_floor.picks_7d ?? 0)} />
                  <Stat label="Forced (7d)"
                    value={String(data.diversity_floor.forced_7d ?? 0)} />
                  <Stat label="Force rate"
                    value={data.diversity_floor.force_rate !== null && data.diversity_floor.force_rate !== undefined
                      ? `${Math.round(data.diversity_floor.force_rate * 100)}%`
                      : '—'}
                    accent={
                      (data.diversity_floor.force_rate ?? 0) > 0.25 ? 'warn'
                        : (data.diversity_floor.force_rate ?? 0) > 0 ? 'ok'
                        : undefined
                    } />
                </div>
              )}
            </section>

            {/* Prediction calibration (Phase 11) ─────────── */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold text-content-primary mb-1">
                Prediction calibration
              </h2>
              <p className="text-xs text-content-tertiary mb-4">
                Brier score and Expected Calibration Error over the last 30 days of scored topic-success predictions. Brier &lt; 0.20 is healthy; ECE &lt; 0.10 means the model&apos;s confidence is well-calibrated. <strong>Weighted fraction</strong> is the share of the latest training run&apos;s rows that received a confidence-weight boost from past misses — non-zero means the correction loop is steering retraining.
              </p>
              {!data.calibration?.ok ? (
                <div className="text-xs text-content-tertiary italic">
                  No scored predictions yet (model not trained, or no actuals back-filled).
                </div>
              ) : (
                <div className="grid grid-cols-4 gap-3">
                  <Stat label="Scored (30d)"
                    value={String(data.calibration.n ?? 0)} />
                  <Stat label="Brier"
                    value={data.calibration.brier !== null && data.calibration.brier !== undefined
                      ? data.calibration.brier.toFixed(3)
                      : '—'}
                    accent={
                      (data.calibration.brier ?? 1) < 0.20 ? 'ok'
                        : (data.calibration.brier ?? 0) > 0.30 ? 'warn'
                        : undefined
                    } />
                  <Stat label="ECE"
                    value={data.calibration.ece !== null && data.calibration.ece !== undefined
                      ? data.calibration.ece.toFixed(3)
                      : '—'}
                    accent={
                      (data.calibration.ece ?? 1) < 0.10 ? 'ok'
                        : (data.calibration.ece ?? 0) > 0.20 ? 'warn'
                        : undefined
                    } />
                  <Stat label="Weighted frac"
                    value={data.calibration.weighted_fraction !== null && data.calibration.weighted_fraction !== undefined
                      ? `${Math.round(data.calibration.weighted_fraction * 100)}%`
                      : '—'} />
                </div>
              )}
            </section>

            {/* Retention coverage (Phase 9) ─────────── */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold text-content-primary mb-1">
                Retention-curve coverage
              </h2>
              <p className="text-xs text-content-tertiary mb-4">
                Of delivered videos in the curve-stable window (7-30 days old), how many have an audience-retention curve fetched. The Phase 7 calibrator uses these curves directly for hook and pacing dimensions; videos without curves fall back to tier-based labels.
              </p>
              {!data.retention_coverage?.ok ? (
                <div className="text-xs text-content-tertiary italic">
                  Coverage query failed (table may not exist yet).
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-3">
                  <Stat label="Eligible videos"
                    value={String(data.retention_coverage.eligible ?? 0)} />
                  <Stat label="With curve"
                    value={String(data.retention_coverage.with_curve ?? 0)}
                    accent={(data.retention_coverage.with_curve ?? 0) > 0 ? 'ok' : undefined} />
                  <Stat label="Coverage"
                    value={data.retention_coverage.coverage !== null && data.retention_coverage.coverage !== undefined
                      ? `${Math.round(data.retention_coverage.coverage * 100)}%`
                      : '—'}
                    accent={
                      (data.retention_coverage.coverage ?? 0) >= 0.7 ? 'ok'
                        : (data.retention_coverage.coverage ?? 1) < 0.3 ? 'warn'
                        : undefined
                    } />
                </div>
              )}
              {data.retention_coverage?.last_fetch && (
                <div className="text-[11px] text-content-tertiary mt-3">
                  Last fetch {new Date(data.retention_coverage.last_fetch).toLocaleString()}
                </div>
              )}
            </section>

            {/* Gate calibration ─────────── */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold text-content-primary mb-1">
                Quality-gate calibration
              </h2>
              <p className="text-xs text-content-tertiary mb-4">
                Per-niche thresholds learned from real outcomes (Phase 7). Auto rows mean the gate is using a tuned floor; default rows mean the niche hasn't accumulated enough data yet.
              </p>
              {!data.gate_calibration?.ok ? (
                <div className="text-xs text-content-tertiary italic">
                  Calibrator hasn't run yet (table empty or workflow not deployed).
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-3">
                  <Stat label="Niches calibrated"
                    value={String(data.gate_calibration.niches_calibrated ?? 0)} />
                  <Stat label="Tuned dimensions"
                    value={String(data.gate_calibration.dims_auto ?? 0)}
                    accent="ok" />
                  <Stat label="Awaiting data"
                    value={String(data.gate_calibration.dims_default ?? 0)} />
                </div>
              )}
              {data.gate_calibration?.last_run && (
                <div className="text-[11px] text-content-tertiary mt-3">
                  Last run {new Date(data.gate_calibration.last_run).toLocaleString()}
                </div>
              )}
            </section>

            {/* Scale config ─────────── */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold text-content-primary mb-2">Scale configuration</h2>
              <p className="text-xs text-content-tertiary mb-3">
                Read-only snapshot of the env-driven knobs. Change via env vars + restart workers.
              </p>
              <div className="grid grid-cols-3 gap-3">
                <Stat label="Prod max activities" value={String(data.scale_config.temporal_production_max_activities)} />
                <Stat label="Scheduler max activities" value={String(data.scale_config.temporal_scheduler_max_activities)} />
                <Stat label="Statement timeout" value={`${data.scale_config.db_statement_timeout_ms}ms`} />
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: 'ok' | 'warn' }) {
  const color = accent === 'warn' ? 'text-status-warning'
    : accent === 'ok' ? 'text-status-success'
    : 'text-content-primary';
  return (
    <div className="flex items-center justify-between text-xs py-1">
      <span className="text-content-tertiary">{label}</span>
      <span className={cn('font-semibold tabular-nums', color)}>{value}</span>
    </div>
  );
}
