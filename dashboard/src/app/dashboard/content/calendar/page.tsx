'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon, Sparkles } from 'lucide-react';
import { contentApi, channelsApi } from '@/lib/api-v2';

function startOfMonth(d: Date) { return new Date(d.getFullYear(), d.getMonth(), 1); }
function endOfMonth(d: Date) { return new Date(d.getFullYear(), d.getMonth() + 1, 1); }
function fmtISO(d: Date) {
  return d.toISOString().slice(0, 10);
}
function monthLabel(d: Date) {
  return d.toLocaleString(undefined, { month: 'long', year: 'numeric' });
}

export default function ContentCalendarPage() {
  const [cursor, setCursor] = useState<Date>(() => startOfMonth(new Date()));
  const [channels, setChannels] = useState<any[]>([]);
  const [channelId, setChannelId] = useState<string>('');
  const [data, setData] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => { channelsApi.list(false).then(r => setChannels(r.data || [])); }, []);

  useEffect(() => {
    setLoading(true);
    const start = fmtISO(startOfMonth(cursor));
    const end = fmtISO(endOfMonth(cursor));
    contentApi.calendar(start, end, channelId || undefined)
      .then(r => setData(r.data || {}))
      .finally(() => setLoading(false));
  }, [cursor, channelId]);

  const grid = useMemo(() => {
    // Build a 6-row x 7-col grid starting from the Sunday on/before
    // the first of the month.
    const first = startOfMonth(cursor);
    const startDow = first.getDay();
    const totalDays = endOfMonth(cursor).getDate();
    const cells: { date: Date; inMonth: boolean }[] = [];
    for (let i = 0; i < 42; i++) {
      const d = new Date(first);
      d.setDate(d.getDate() - startDow + i);
      cells.push({ date: d, inMonth: d.getMonth() === cursor.getMonth() });
    }
    return cells;
  }, [cursor]);

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      <div className="flex items-center gap-3 mb-5">
        <h1 className="text-xl font-semibold text-content-primary inline-flex items-center gap-2">
          <CalendarIcon size={18} /> Calendar
        </h1>
        <span className="text-xs text-content-tertiary">{monthLabel(cursor)}</span>
        <div className="ml-auto flex items-center gap-2">
          <select value={channelId} onChange={e => setChannelId(e.target.value)}
            className="px-2 py-1.5 rounded-lg bg-surface-1 border border-border text-xs">
            <option value="">All channels</option>
            {channels.map(c => <option key={c.channel_id} value={c.channel_id}>{c.channel_name}</option>)}
          </select>
          <button onClick={() => setCursor(startOfMonth(new Date()))}
            className="px-2 py-1.5 text-xs rounded-lg border border-border hover:bg-surface-2">
            Today
          </button>
          <button onClick={() => setCursor(c => new Date(c.getFullYear(), c.getMonth() - 1, 1))}
            className="size-7 inline-flex items-center justify-center rounded-lg border border-border hover:bg-surface-2">
            <ChevronLeft size={14} />
          </button>
          <button onClick={() => setCursor(c => new Date(c.getFullYear(), c.getMonth() + 1, 1))}
            className="size-7 inline-flex items-center justify-center rounded-lg border border-border hover:bg-surface-2">
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-px rounded-xl overflow-hidden border border-border bg-border">
        {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => (
          <div key={d} className="bg-surface-1 px-2 py-1.5 text-[10px] uppercase tracking-wide text-content-tertiary">{d}</div>
        ))}
        {grid.map(({ date, inMonth }, i) => {
          const key = fmtISO(date);
          const items = data[key] || [];
          const isToday = key === fmtISO(new Date());
          return (
            <div key={i} className={'min-h-[110px] p-1.5 bg-surface-0 ' + (inMonth ? '' : 'opacity-40')}>
              <div className={'text-[11px] mb-1 flex items-center gap-1 ' +
                (isToday ? 'text-accent font-semibold' : 'text-content-tertiary')}>
                {date.getDate()}
                {items.length > 0 && (
                  <span className="ml-auto text-[10px] px-1 rounded bg-surface-2">{items.length}</span>
                )}
              </div>
              <div className="space-y-1">
                {items.slice(0, 3).map(v => (
                  <Link key={v.content_id} href={`/dashboard/review/${v.content_id}`}
                    className={'block px-1 py-0.5 rounded text-[10px] truncate ' +
                      (v.status === 'published' ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                       : v.status === 'failed' ? 'bg-red-500/15 text-red-700 dark:text-red-300'
                       : v.status === 'scheduled' ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
                       : 'bg-surface-2 text-content-secondary')}>
                    {v.title || v.content_id}
                  </Link>
                ))}
                {items.length > 3 && (
                  <div className="text-[10px] text-content-tertiary pl-1">+{items.length - 3} more</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {loading && <div className="text-xs text-content-tertiary mt-3">Loading…</div>}
    </main>
  );
}
