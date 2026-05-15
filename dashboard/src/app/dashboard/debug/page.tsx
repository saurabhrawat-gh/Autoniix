'use client';

import { useEffect, useState } from 'react';
import { systemApi, notifyApi } from '@/lib/api-v2';

export default function Debug() {
  const [fleet, setFleet] = useState<any>(null);
  const [crit, setCrit] = useState<any[]>([]);
  const [recentDeliveries, setRecentDeliveries] = useState<any[]>([]);

  useEffect(() => {
    systemApi.fleetHealth().then(r => setFleet(r?.data || r)).catch(() => setFleet(null));
    notifyApi.list(false, 'critical', 20).then(r => setCrit(r.data || []));
    notifyApi.deliveries(undefined, 30).then(r => setRecentDeliveries(r.data || []));
  }, []);

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full"><div className="space-y-5">
      <h1 className="text-2xl font-semibold">Debug</h1>
      <p className="text-sm opacity-70">Centralized view of recent failures, fleet health, and notification deliveries. Wire <code>SENTRY_DSN</code> for the full debugger experience.</p>

      <section>
        <h2 className="text-sm font-medium mb-2 opacity-80">Fleet health</h2>
        <pre className="rounded-xl border border-border bg-surface-0 p-3 text-xs overflow-auto max-h-64">
          {fleet ? JSON.stringify(fleet, null, 2) : 'unavailable'}
        </pre>
      </section>

      <section>
        <h2 className="text-sm font-medium mb-2 opacity-80">Critical alerts (last 20)</h2>
        <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border">
          {crit.length === 0 && <div className="p-4 text-sm opacity-60 text-center">No critical alerts.</div>}
          {crit.map(n => (
            <div key={n.id} className="p-3 text-sm">
              <div className="font-medium">{n.title}</div>
              <div className="text-xs opacity-60">{n.event_type} · {new Date(n.created_at).toLocaleString()}</div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-medium mb-2 opacity-80">Recent deliveries</h2>
        <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border">
          {recentDeliveries.map(d => (
            <div key={d.id} className="p-2.5 text-xs flex items-center gap-2">
              <span className={'px-1.5 py-0.5 rounded uppercase ' + (d.status === 'sent' ? 'bg-status-success/15 text-status-success' : d.status === 'failed' ? 'bg-status-error/15 text-status-error' : '')}>{d.status}</span>
              <span>{d.channel}</span>
              {d.error && <span className="text-status-error truncate">{d.error}</span>}
              <span className="ml-auto opacity-50">{new Date(d.created_at).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      </section>
    </div></main>
  );
}
