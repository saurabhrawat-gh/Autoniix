'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { LayoutGrid, RotateCw } from 'lucide-react';
import { contentApi, channelsApi } from '@/lib/api-v2';
import { Button, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/lib/ui';

const COLUMNS: { key: string; label: string; matches: (s: string) => boolean }[] = [
  { key: 'pending',         label: 'Pending',          matches: s => s === 'pending' },
  { key: 'running',         label: 'In progress',      matches: s => ['running', 'researching', 'scripting', 'generating_voice', 'generating_assets', 'directing', 'rendering'].includes(s) },
  { key: 'review',          label: 'Awaiting review',  matches: s => s === 'pending_review' },
  { key: 'published',       label: 'Published',        matches: s => ['published', 'delivered', 'test_delivered', 'completed'].includes(s) },
  { key: 'failed',          label: 'Failed / stopped', matches: s => ['failed', 'stopped', 'rejected'].includes(s) },
];

export default function KanbanPage() {
  const [channels, setChannels] = useState<any[]>([]);
  const [channelId, setChannelId] = useState<string>('');
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { channelsApi.list(false).then(r => setChannels(r.data || [])); }, []);

  const refresh = () => {
    setLoading(true);
    contentApi.list({ channel_id: channelId || undefined, group: 'month', limit: 200 })
      .then(r => setItems((r.data?.groups || []).flatMap((g: any) => g.items)))
      .finally(() => setLoading(false));
  };
  useEffect(() => { refresh(); }, [channelId]);

  const byCol = COLUMNS.map(c => ({ ...c, items: items.filter(v => c.matches(v.status)) }));

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1600px] mx-auto w-full">
      <div className="flex items-center gap-3 mb-5">
        <h1 className="text-xl font-semibold text-content-primary inline-flex items-center gap-2">
          <LayoutGrid size={18} /> Pipeline board
        </h1>
        <span className="text-xs text-content-tertiary">{items.length} videos</span>
        <div className="ml-auto min-w-[180px]">
          <Select value={channelId || '__all__'} onValueChange={(v: string) => setChannelId(v === '__all__' ? '' : v)}>
            <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="All channels" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All channels</SelectItem>
              {channels.map(c => <SelectItem key={c.channel_id} value={c.channel_id}>{c.channel_name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Button
          type="button"
          variant="outline"
          size="icon-sm"
          onClick={refresh}
          title="Refresh"
          aria-label="Refresh"
        >
          <RotateCw size={14} className={loading ? 'animate-spin' : ''} />
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {byCol.map(col => (
          <div key={col.key} className="rounded-xl border border-border bg-surface-1 flex flex-col min-h-[60vh]">
            <div className="px-3 py-2 border-b border-border flex items-center gap-2">
              <span className="text-xs font-medium uppercase tracking-wide text-content-secondary">{col.label}</span>
              <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-content-tertiary">{col.items.length}</span>
            </div>
            <div className="p-2 space-y-2 flex-1 overflow-auto">
              {col.items.length === 0 && (
                <div className="text-[11px] text-content-tertiary text-center py-6">empty</div>
              )}
              {col.items.map(v => (
                <Link key={v.content_id} href={`/dashboard/review/${v.content_id}`}
                  className="block rounded-lg border border-border bg-surface-0 p-2 hover:border-accent/40 transition">
                  <div className="text-xs font-medium truncate">{v.title || v.topic || v.content_id}</div>
                  <div className="text-[10px] text-content-tertiary mt-1 flex items-center gap-1.5">
                    {v.content_mode && (
                      <span className={v.content_mode === 'short' ? 'chip-short' : 'chip-long'}>
                        {v.content_mode === 'short' ? 'Short' : 'Long'}
                      </span>
                    )}
                    <span>{v.channel_id}</span>
                    {v.authenticity_score != null && (
                      <span className="ml-auto font-mono">a {Number(v.authenticity_score).toFixed(2)}</span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
