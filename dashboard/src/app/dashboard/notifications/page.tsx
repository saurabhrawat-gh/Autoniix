'use client';

import { useEffect, useState } from 'react';
import { Bell, AlertTriangle, AlertCircle, Info, Settings as Cog } from 'lucide-react';
import { notifyApi } from '@/lib/api-v2';
import { wsEvents } from '@/lib/api';

export default function Notifications() {
  const [tab, setTab] = useState<'inbox'|'routes'|'deliveries'>('inbox');
  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full"><div className="space-y-5">
      <h1 className="text-2xl font-semibold">Notifications</h1>
      <div className="flex gap-1 border-b border-border">
        {(['inbox','routes','deliveries'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={'px-3 py-2 text-sm border-b-2 -mb-px ' +
              (tab === t ? 'border-accent text-accent' : 'border-transparent opacity-70 hover:opacity-100')}>
            {t}
          </button>
        ))}
      </div>
      {tab === 'inbox' && <Inbox />}
      {tab === 'routes' && <Routes />}
      {tab === 'deliveries' && <Deliveries />}
    </div>
    </main>
  );
}

function Inbox() {
  const [rows, setRows] = useState<any[]>([]);
  const [sev, setSev] = useState<string>('');
  const refresh = () => { notifyApi.list(false, sev || undefined).then(r => setRows(r.data || [])); };
  useEffect(() => { refresh(); }, [sev]);

  // Live updates — listen for "notification" events on the global event WS
  // and re-fetch. Cheap and keeps inbox in sync across tabs.
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnect: any;
    let alive = true;
    const connect = () => {
      try {
        ws = wsEvents();
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (msg?.type === 'notification') refresh();
          } catch { /* noop */ }
        };
        ws.onclose = () => { if (alive) reconnect = setTimeout(connect, 4000); };
        ws.onerror = () => { ws?.close(); };
      } catch { /* noop */ }
    };
    connect();
    return () => { alive = false; clearTimeout(reconnect); ws?.close(); };
  }, [sev]);
  return (
    <div>
      <div className="flex gap-2 mb-3">
        {['','info','warn','error','critical'].map(s => (
          <button key={s} onClick={() => setSev(s)}
            className={'px-2 py-1 text-xs rounded ' + (sev === s ? 'bg-accent text-white' : 'border border-border')}>
            {s || 'all'}
          </button>
        ))}
      </div>
      <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border">
        {rows.length === 0 && <div className="p-6 text-sm opacity-60 text-center">No notifications.</div>}
        {rows.map(n => {
          const Icon = n.severity === 'critical' || n.severity === 'error' ? AlertCircle :
                       n.severity === 'warn' ? AlertTriangle : Info;
          const color = n.severity === 'critical' ? 'text-red-500' : n.severity === 'error' ? 'text-red-400' :
                        n.severity === 'warn' ? 'text-amber-500' : 'text-blue-500';
          return (
            <div key={n.id} className="p-3 flex gap-3">
              <Icon size={16} className={color + ' shrink-0 mt-0.5'} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{n.title}</div>
                {n.body && <div className="text-xs opacity-70 mt-0.5">{n.body}</div>}
                <div className="text-[11px] opacity-50 mt-1">
                  {n.event_type} · {new Date(n.created_at).toLocaleString()}
                </div>
              </div>
              <button onClick={() => notifyApi.read(n.id)} className="text-xs opacity-60 hover:opacity-100">mark read</button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Routes() {
  const [rows, setRows] = useState<any[]>([]);
  const refresh = () => { notifyApi.routes().then(r => setRows(r.data || [])); };
  useEffect(() => { refresh(); }, []);
  return (
    <div className="space-y-3">
      <p className="text-sm opacity-70">Route rules decide where notifications are delivered. Slack and webhook channels need a configured URL.</p>
      <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border">
        {rows.map(r => (
          <div key={r.id} className="p-3 flex items-center gap-3">
            <Cog size={14} className="opacity-50" />
            <div className="flex-1">
              <div className="text-sm font-medium">{r.name}</div>
              <div className="text-xs opacity-60 font-mono">
                {r.event_pattern} · ≥{r.severity_min} → {r.channels.join(', ')}
              </div>
            </div>
            <button onClick={async () => {
              await notifyApi.updateRoute(r.id, { ...r, enabled: !r.enabled });
              refresh();
            }} className={'px-2 py-1 text-xs rounded ' + (r.enabled ? 'bg-emerald-500 text-white' : 'border border-border')}>
              {r.enabled ? 'enabled' : 'disabled'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function Deliveries() {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => { notifyApi.deliveries().then(r => setRows(r.data || [])); }, []);
  return (
    <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border">
      {rows.length === 0 && <div className="p-6 text-sm opacity-60 text-center">No delivery records.</div>}
      {rows.map(d => (
        <div key={d.id} className="p-3 text-sm flex items-center gap-3">
          <span className={'text-[10px] uppercase px-1.5 py-0.5 rounded ' +
            (d.status === 'sent' ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
             : d.status === 'failed' ? 'bg-red-500/15 text-red-700 dark:text-red-300'
             : 'bg-surface-3/15 text-content-tertiary')}>{d.status}</span>
          <span className="opacity-80">{d.channel}</span>
          {d.error && <span className="text-xs text-red-400 truncate">{d.error}</span>}
          <span className="ml-auto text-xs opacity-50">{new Date(d.created_at).toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}
