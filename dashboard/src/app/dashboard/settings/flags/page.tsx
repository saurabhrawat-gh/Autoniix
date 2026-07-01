'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { flagsApi, isLoggedIn } from '@/lib/api-v2';
import { useToast } from '@/lib/toast';
import { PageHeader } from '@/lib/components/PageHeader';
import { Skeleton } from '@/lib/components/Skeleton';
import { Switch } from '@/lib/ui';

type Flag = {
  key: string;
  enabled: boolean;
  description: string;
  payload: any;
};

const SECURITY_KEYS = new Set<string>([
  'providers.admin_credentials.enabled',
  'providers.credentials.rotate.enabled',
]);

function friendlyName(key: string): string {
  return key.replace(/[._]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function FeatureFlagsPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const [flags, setFlags] = useState<Flag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!isLoggedIn()) {
      router.replace('/login');
      return;
    }
    void load();
  }, [router]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await flagsApi.list();
      const sorted = [...(res.data || [])].sort((a, b) => {
        const aSec = SECURITY_KEYS.has(a.key) ? 0 : 1;
        const bSec = SECURITY_KEYS.has(b.key) ? 0 : 1;
        if (aSec !== bSec) return aSec - bSec;
        return a.key.localeCompare(b.key);
      });
      setFlags(sorted);
    } catch (e: any) {
      setError(e?.message || 'Failed to load feature flags');
    } finally {
      setLoading(false);
    }
  }

  async function toggle(flag: Flag, next: boolean) {
    setPending((prev) => new Set(prev).add(flag.key));
    setFlags((prev) =>
      prev.map((f) => (f.key === flag.key ? { ...f, enabled: next } : f)),
    );
    try {
      await flagsApi.set(flag.key, next, flag.payload || {});
      showToast(`${friendlyName(flag.key)} ${next ? 'enabled' : 'disabled'}`, 'success');
    } catch (e: any) {
      setFlags((prev) =>
        prev.map((f) => (f.key === flag.key ? { ...f, enabled: !next } : f)),
      );
      const msg = e?.message || 'Failed to update flag';
      showToast(
        msg.includes('403')
          ? 'You do not have permission to change this flag (owner or admin required)'
          : msg,
        'error',
      );
    } finally {
      setPending((prev) => {
        const updated = new Set(prev);
        updated.delete(flag.key);
        return updated;
      });
    }
  }

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader
        title="Feature Flags"
        subtitle="Toggle workspace-wide feature flags. Changes take effect on the next request — no restart required."
        crumbs={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Settings', href: '/dashboard/settings' },
          { label: 'Feature Flags' },
        ]}
      />
      <div className="max-w-4xl w-full mx-auto px-6 py-6 space-y-4">
        {error && (
          <div className="rounded-lg border border-status-error/30 bg-status-error/10 px-4 py-3 text-sm text-status-error">
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : flags.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface-1 px-4 py-6 text-center text-sm text-content-secondary">
            No feature flags configured.
          </div>
        ) : (
          <div className="card divide-y divide-border">
            {flags.map((flag) => {
              const isSecurity = SECURITY_KEYS.has(flag.key);
              const isPending = pending.has(flag.key);
              return (
                <div
                  key={flag.key}
                  className={`px-5 py-4 transition-colors ${
                    isSecurity ? 'bg-status-warning/5' : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <code className="rounded bg-surface-2 px-2 py-0.5 text-xs font-mono text-content-primary">
                          {flag.key}
                        </code>
                        {isSecurity && (
                          <span className="rounded bg-status-warning/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-status-warning">
                            Security
                          </span>
                        )}
                      </div>
                      {flag.description && (
                        <p className="mt-2 text-sm text-content-secondary">{flag.description}</p>
                      )}
                    </div>
                    <div className="shrink-0 pt-1">
                      <Switch
                        checked={flag.enabled}
                        disabled={isPending}
                        onCheckedChange={(checked: boolean) => void toggle(flag, checked)}
                        aria-label={`Toggle ${flag.key}`}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="rounded-lg border border-border bg-surface-1 px-4 py-3 text-xs text-content-secondary">
          <p>
            <strong className="font-semibold text-content-primary">Note:</strong> Only owners and
            admins can toggle feature flags. Flag reads are not cached — changes apply on the next
            authenticated request.
          </p>
        </div>
      </div>
    </div>
  );
}
