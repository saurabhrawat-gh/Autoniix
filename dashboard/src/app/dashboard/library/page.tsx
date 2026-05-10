'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { libraryApi, channelsApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import {
  Search, Archive, ShieldCheck, Music, Palette, Type, Film,
  Layout, Headphones, UploadCloud, X, Trash2, FileImage, Music2
} from '@/lib/components/Icon';

type TabKey = 'stock' | 'brand' | 'music' | 'bgmusic' | 'sfx' | 'luts' | 'fonts' | 'broll' | 'templates';

interface TabConfig {
  key: TabKey;
  label: string;
  icon: React.ReactNode;
  purpose: string;
  accept: string;
  readOnly?: boolean;
  endpointPrefix: string;
}

const TABS: TabConfig[] = [
  { key: 'stock',     label: 'Stock',     icon: <Archive size={14} />,     purpose: 'Cached Pixabay/Pexels clips & images used by automation',         accept: 'image/*,video/*', readOnly: true,  endpointPrefix: 'assets' },
  { key: 'brand',     label: 'Brand',     icon: <ShieldCheck size={14} />, purpose: 'Per-channel logos, overlays, watermarks',                          accept: 'image/*,video/*', endpointPrefix: 'brand' },
  { key: 'music',     label: 'Music',     icon: <Music size={14} />,       purpose: 'Background music tracks for video production',                     accept: 'audio/*',         endpointPrefix: 'music' },
  { key: 'bgmusic',   label: 'BG Music',  icon: <Music2 size={14} />,      purpose: 'Ambient/loop tracks — softer than main music',                     accept: 'audio/*',         endpointPrefix: 'bgmusic' },
  { key: 'sfx',       label: 'Sound FX',  icon: <Headphones size={14} />,  purpose: 'Short audio clips: whoosh, ding, transitions, etc.',               accept: 'audio/*',         endpointPrefix: 'sfx' },
  { key: 'luts',      label: 'LUTs',      icon: <Palette size={14} />,     purpose: '.cube color grading files applied by Remotion to match visual style', accept: '.cube,.3dl',     endpointPrefix: 'luts' },
  { key: 'fonts',     label: 'Fonts',     icon: <Type size={14} />,        purpose: 'Custom typefaces (.ttf/.woff2) used in Remotion text scenes',      accept: '.ttf,.woff,.woff2,.otf', endpointPrefix: 'fonts' },
  { key: 'broll',     label: 'B-Roll',    icon: <Film size={14} />,        purpose: 'Pre-approved stock video clips for manual curation',               accept: 'video/*',         endpointPrefix: 'broll' },
  { key: 'templates', label: 'Templates', icon: <Layout size={14} />,      purpose: 'Remotion scene presets (JSON configs) for reusable layouts',        accept: '.json',           endpointPrefix: 'templates' },
];

export default function LibraryPage() {
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState<TabKey>('stock');
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState('');
  const [channels, setChannels] = useState<any[]>([]);
  const [channelId, setChannelId] = useState('');
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const tab = TABS.find(t => t.key === activeTab)!;

  useEffect(() => { channelsApi.list(false).then(r => setChannels(r.data || [])); }, []);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      let data: any[] = [];
      if (activeTab === 'stock') {
        const r = await libraryApi.assets({ q: q || undefined, limit: 100 });
        data = r.data || [];
      } else if (activeTab === 'brand') {
        const r = await libraryApi.brand(channelId || undefined);
        data = r.data || [];
      } else if (activeTab === 'music') {
        const r = await libraryApi.music();
        data = r.data || [];
      } else {
        data = [];
      }
      setItems(q && activeTab === 'stock' ? data : data);
    } catch { setItems([]); }
    setLoading(false);
  }, [activeTab, q, channelId]);

  useEffect(() => { loadItems(); }, [loadItems]);

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    if (tab.readOnly) { showToast('Stock assets are read-only — populated automatically', 'error'); return; }
    setUploading(true);
    try {
      const formData = new FormData();
      Array.from(files).forEach(f => formData.append('files', f));
      formData.append('type', activeTab);
      if (channelId) formData.append('channel_id', channelId);

      const token = typeof window !== 'undefined' ? localStorage.getItem('dashboard_token') : null;
      const base = process.env.NEXT_PUBLIC_API_URL || '';
      const res = await fetch(`${base}/api/v2/library/upload`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const result = await res.json();
      showToast(`Uploaded ${result.count ?? files.length} file(s)`, 'success');
      loadItems();
    } catch (e: any) {
      showToast(e?.message || 'Upload failed', 'error');
    }
    setUploading(false);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  }

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      {/* Header */}
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-content-primary">Asset Library</h1>
        <p className="text-xs text-content-tertiary mt-0.5">
          Manage all media assets used across your automation pipeline. Upload assets to make them available to Remotion and production services.
        </p>
      </div>

      {/* Tab bar (scrollable) */}
      <div className="flex items-center gap-0.5 bg-surface-1 p-0.5 rounded-md mb-4 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.key} onClick={() => { setActiveTab(t.key); setQ(''); }}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium whitespace-nowrap transition-all shrink-0',
              activeTab === t.key ? 'bg-surface-0 text-content-primary shadow-sm' : 'text-content-tertiary hover:text-content-secondary'
            )}>
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* Purpose banner */}
      <div className="mb-4 text-xs text-content-tertiary bg-surface-1 border border-border rounded-md px-3 py-2">
        {tab.icon} <span className="text-content-secondary font-medium ml-1.5">{tab.label}:</span>
        <span className="ml-1">{tab.purpose}</span>
        {tab.readOnly && <span className="ml-2 text-amber-400">(read-only — populated by automation)</span>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-4">
        {/* Main content */}
        <div className="space-y-3">
          {/* Search + filter bar */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative flex-1 min-w-[200px]">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-tertiary pointer-events-none" />
              <input
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder={`Search ${tab.label.toLowerCase()} assets…`}
                className="w-full h-9 pl-9 pr-9 rounded-md bg-surface-0 border border-border text-sm placeholder:text-content-tertiary outline-none focus:border-accent/50 focus:ring-2 focus:ring-accent/15 transition-colors"
              />
              {q && (
                <button
                  onClick={() => setQ('')}
                  aria-label="Clear search"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center rounded text-content-tertiary hover:text-content-primary hover:bg-surface-2"
                >
                  <X size={12} />
                </button>
              )}
            </div>
            {activeTab === 'brand' && (
              <select value={channelId} onChange={e => setChannelId(e.target.value)}
                className="h-9 px-2.5 rounded-md bg-surface-0 border border-border text-xs focus:outline-none focus:border-accent/50">
                <option value="">All channels</option>
                {channels.map(c => <option key={c.channel_id} value={c.channel_id}>{c.channel_name}</option>)}
              </select>
            )}
            <span className="text-xs text-content-tertiary whitespace-nowrap">{items.length} item{items.length !== 1 ? 's' : ''}</span>
          </div>

          {/* Asset grid/list */}
          {loading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="rounded-md bg-surface-2 animate-pulse aspect-video" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="py-16 text-center rounded-md border border-dashed border-border">
              <div className="text-3xl mb-3 opacity-30">{tab.readOnly ? '📦' : '📁'}</div>
              <div className="text-sm font-medium text-content-primary">No {tab.label.toLowerCase()} assets</div>
              <div className="text-xs text-content-tertiary mt-1">
                {tab.readOnly ? 'Assets will appear here once automation runs.' : 'Upload files using the panel →'}
              </div>
            </div>
          ) : (
            <div className="rounded-md border border-border bg-surface-0 divide-y divide-border overflow-hidden">
              {items.map((item: any, i: number) => (
                <AssetRow key={item.id || item.asset_id || i} item={item} tab={activeTab} onDeleted={loadItems} />
              ))}
            </div>
          )}
        </div>

        {/* Upload panel */}
        {!tab.readOnly && (
          <div>
            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              className={cn(
                'rounded-md border-2 border-dashed p-6 text-center transition-colors cursor-pointer',
                dragOver ? 'border-accent bg-accent/5' : 'border-border hover:border-accent/40 hover:bg-surface-1',
              )}
              onClick={() => !uploading && fileInputRef.current?.click()}
            >
              <UploadCloud size={28} className={cn('mx-auto mb-3', dragOver ? 'text-accent' : 'text-content-tertiary')} />
              <div className="text-sm font-medium text-content-primary mb-1">
                {uploading ? 'Uploading…' : 'Drop files here'}
              </div>
              <div className="text-xs text-content-tertiary">
                {uploading ? 'Please wait…' : `or click to browse · ${tab.accept}`}
              </div>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={tab.accept}
              className="hidden"
              onChange={e => handleUpload(e.target.files)}
            />

            {activeTab === 'brand' && (
              <div className="mt-3 p-3 rounded-md bg-surface-1 border border-border text-xs text-content-tertiary space-y-1">
                <div className="font-medium text-content-secondary">💡 Brand assets</div>
                <p>Upload per-channel logos (PNG/SVG), watermark overlays, and brand kit images. Select a channel filter to scope uploads to a specific channel.</p>
              </div>
            )}
            {activeTab === 'luts' && (
              <div className="mt-3 p-3 rounded-md bg-surface-1 border border-border text-xs text-content-tertiary">
                <div className="font-medium text-content-secondary">💡 LUT format</div>
                <p className="mt-0.5">Upload .cube files (standard 3D LUT format). These are applied during Remotion post-processing to set a consistent visual style per channel.</p>
              </div>
            )}
            {activeTab === 'templates' && (
              <div className="mt-3 p-3 rounded-md bg-surface-1 border border-border text-xs text-content-tertiary">
                <div className="font-medium text-content-secondary">💡 Template format</div>
                <p className="mt-0.5">Upload JSON preset files that define Remotion scene configurations. These become reusable layout options for your channels.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

function AssetRow({ item, tab, onDeleted }: { item: any; tab: TabKey; onDeleted: () => void }) {
  const { showToast } = useToast();

  async function deleteAsset() {
    if (!confirm('Delete this asset?')) return;
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('dashboard_token') : null;
      const base = process.env.NEXT_PUBLIC_API_URL || '';
      await fetch(`${base}/api/v2/library/${tab}/${item.id || item.asset_id}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      showToast('Asset deleted', 'success');
      onDeleted();
    } catch { showToast('Delete failed', 'error'); }
  }

  const name = item.file_name || item.title || item.name || item.url?.split('/').pop() || 'Unknown';
  const provider = item.provider || item.source || '';
  const type = item.media_type || item.type || '';
  const size = item.file_size ? `${(item.file_size / 1024).toFixed(0)} KB` : '';

  return (
    <div className="flex items-center gap-3 px-3 py-2.5 hover:bg-surface-1 transition-colors">
      <div className="w-10 h-8 rounded bg-surface-2 shrink-0 flex items-center justify-center">
        <FileImage size={13} className="text-content-tertiary" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-xs font-medium text-content-primary truncate">{name}</div>
        <div className="text-[10px] text-content-tertiary truncate">
          {[provider, type, size].filter(Boolean).join(' · ')}
        </div>
      </div>
      {tab !== 'stock' && (
        <button onClick={deleteAsset} title="Delete"
          className="w-7 h-7 flex items-center justify-center rounded hover:bg-red-500/10 text-content-tertiary hover:text-red-500 transition-colors shrink-0">
          <Trash2 size={13} />
        </button>
      )}
    </div>
  );
}
