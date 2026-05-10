'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { libraryApi, channelsApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import {
  Search, Archive, ShieldCheck, Music, Palette, Type, Film,
  Layout, Headphones, UploadCloud, X, Trash2, FileImage, Music2,
  RotateCw, Tag, Layers, Hash, Boxes,
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
  color: string;
}

const TABS: TabConfig[] = [
  { key: 'stock',     label: 'Stock',     icon: <Archive size={14} />,     purpose: 'Cached Pixabay/Pexels clips & images used by automation',            accept: 'image/*,video/*',       readOnly: true, endpointPrefix: 'assets',    color: 'text-blue-500' },
  { key: 'brand',     label: 'Brand',     icon: <ShieldCheck size={14} />, purpose: 'Per-channel logos, overlays, watermarks, brand kit assets',          accept: 'image/*,video/*',                       endpointPrefix: 'brand',     color: 'text-violet-500' },
  { key: 'music',     label: 'Music',     icon: <Music size={14} />,       purpose: 'Background music tracks for video production',                       accept: 'audio/*',                               endpointPrefix: 'music',     color: 'text-emerald-500' },
  { key: 'bgmusic',   label: 'BG Music',  icon: <Music2 size={14} />,      purpose: 'Ambient/loop tracks — softer than main music',                       accept: 'audio/*',                               endpointPrefix: 'bgmusic',   color: 'text-teal-500' },
  { key: 'sfx',       label: 'Sound FX',  icon: <Headphones size={14} />,  purpose: 'Short audio clips: whoosh, ding, transitions, etc.',                 accept: 'audio/*',                               endpointPrefix: 'sfx',       color: 'text-amber-500' },
  { key: 'luts',      label: 'LUTs',      icon: <Palette size={14} />,     purpose: '.cube color grading files applied by Remotion to match visual style', accept: '.cube,.3dl',                            endpointPrefix: 'luts',      color: 'text-pink-500' },
  { key: 'fonts',     label: 'Fonts',     icon: <Type size={14} />,        purpose: 'Custom typefaces (.ttf/.woff2) used in Remotion text scenes',        accept: '.ttf,.woff,.woff2,.otf',                endpointPrefix: 'fonts',     color: 'text-orange-500' },
  { key: 'broll',     label: 'B-Roll',    icon: <Film size={14} />,        purpose: 'Pre-approved stock video clips for manual curation',                 accept: 'video/*',                               endpointPrefix: 'broll',     color: 'text-red-500' },
  { key: 'templates', label: 'Templates', icon: <Layout size={14} />,      purpose: 'Remotion scene presets (JSON configs) for reusable layouts',         accept: '.json',                                 endpointPrefix: 'templates', color: 'text-cyan-500' },
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
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [selectedItem, setSelectedItem] = useState<any>(null);
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

  const totalItems = TABS.reduce((sum, t) => sum + (t.key === activeTab ? items.length : 0), items.length);

  return (
    <main className="flex-1 flex flex-col min-h-0 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
            <Archive size={18} className="text-accent" /> Asset Library
          </h1>
          <p className="text-xs text-content-tertiary mt-0.5">
            Centralised media DAM — stock cache, brand kits, music, LUTs, fonts and Remotion templates.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {/* View toggle */}
          <div className="flex items-center gap-0.5 bg-surface-1 border border-border rounded-md p-0.5">
            {(['list', 'grid'] as const).map(v => (
              <button key={v} onClick={() => setViewMode(v)}
                className={cn('w-7 h-7 flex items-center justify-center rounded text-xs transition-colors',
                  viewMode === v ? 'bg-surface-0 text-content-primary shadow-sm' : 'text-content-tertiary hover:text-content-secondary')}>
                {v === 'list' ? <Layers size={13} /> : <Boxes size={13} />}
              </button>
            ))}
          </div>
          <button onClick={loadItems} disabled={loading}
            className="h-8 w-8 flex items-center justify-center rounded-md border border-border hover:bg-surface-2 text-content-tertiary transition-colors">
            <RotateCw size={13} className={cn(loading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* Scope summary row */}
      <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2 mb-4">
        {TABS.map(t => (
          <button key={t.key}
            onClick={() => { setActiveTab(t.key); setQ(''); setSelectedItem(null); }}
            className={cn(
              'flex flex-col items-center gap-1 rounded-xl border p-2.5 transition-all text-center',
              activeTab === t.key
                ? 'border-accent/40 bg-accent/5 shadow-sm'
                : 'border-border bg-surface-0 hover:bg-surface-1 hover:border-border-hover'
            )}>
            <span className={cn('transition-colors', activeTab === t.key ? t.color : 'text-content-tertiary')}>
              {t.icon}
            </span>
            <span className={cn('text-[10px] font-medium leading-none',
              activeTab === t.key ? 'text-content-primary' : 'text-content-tertiary')}>
              {t.label}
            </span>
            {t.readOnly && (
              <span className="text-[8px] px-1 rounded bg-surface-2 text-content-tertiary leading-3 py-0.5">AUTO</span>
            )}
          </button>
        ))}
      </div>

      {/* Active tab purpose */}
      <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-md bg-surface-1 border border-border">
        <span className={cn('shrink-0', tab.color)}>{tab.icon}</span>
        <span className="text-xs text-content-secondary">
          <span className="font-medium text-content-primary">{tab.label}: </span>{tab.purpose}
        </span>
        {tab.readOnly && (
          <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-500 font-medium shrink-0">
            Read-only
          </span>
        )}
      </div>

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Main asset area */}
        <div className="flex-1 min-w-0 flex flex-col gap-3">
          {/* Search + filter bar */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative flex-1 min-w-[200px]">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-tertiary pointer-events-none" />
              <input
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder={`Search ${tab.label.toLowerCase()} assets…`}
                className="w-full h-9 pl-9 pr-9 rounded-md bg-surface-0 border border-border text-sm placeholder:text-content-tertiary outline-none focus:border-accent/50 transition-colors"
              />
              {q && (
                <button onClick={() => setQ('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center rounded text-content-tertiary hover:text-content-primary hover:bg-surface-2">
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
            <div className={cn('grid gap-2', viewMode === 'grid' ? 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4' : 'grid-cols-1')}>
              {Array.from({ length: viewMode === 'grid' ? 12 : 6 }).map((_, i) => (
                <div key={i} className={cn('rounded-md bg-surface-2 animate-pulse', viewMode === 'grid' ? 'aspect-video' : 'h-12')} />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="flex-1 py-20 text-center rounded-xl border border-dashed border-border">
              <div className="text-4xl mb-3 opacity-20">{tab.readOnly ? '📦' : '📁'}</div>
              <div className="text-sm font-medium text-content-primary">No {tab.label.toLowerCase()} assets</div>
              <div className="text-xs text-content-tertiary mt-1.5">
                {tab.readOnly ? 'Assets will appear here once automation runs.' : 'Drop files in the upload zone to get started.'}
              </div>
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-2">
              {items.map((item: any, i: number) => (
                <button key={item.id || item.asset_id || item.key || i}
                  onClick={() => setSelectedItem(selectedItem?.id === item.id ? null : item)}
                  className={cn(
                    'rounded-lg border overflow-hidden text-left transition-all hover:shadow-card group',
                    selectedItem?.id === item.id ? 'border-accent ring-1 ring-accent/30' : 'border-border hover:border-border-hover'
                  )}>
                  <div className="aspect-video bg-surface-2 flex items-center justify-center">
                    <FileImage size={20} className="text-content-tertiary opacity-30" />
                  </div>
                  <div className="px-2 py-1.5">
                    <div className="text-[10px] font-medium text-content-primary truncate">
                      {item.file_name || item.title || item.name || item.key?.split('/').pop() || 'Unknown'}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border overflow-hidden">
              {items.map((item: any, i: number) => (
                <AssetRow
                  key={item.id || item.asset_id || item.key || i}
                  item={item} tab={activeTab}
                  selected={selectedItem?.id === item.id}
                  onSelect={() => setSelectedItem(selectedItem?.id === item.id ? null : item)}
                  onDeleted={loadItems}
                />
              ))}
            </div>
          )}
        </div>

        {/* Right panel: upload zone + detail drawer */}
        <div className="w-[260px] shrink-0 space-y-3">
          {/* Upload zone */}
          {!tab.readOnly && (
            <div>
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
                className={cn(
                  'rounded-xl border-2 border-dashed p-5 text-center transition-colors cursor-pointer',
                  dragOver ? 'border-accent bg-accent/5' : 'border-border hover:border-accent/40 hover:bg-surface-1',
                )}
                onClick={() => !uploading && fileInputRef.current?.click()}
              >
                <UploadCloud size={24} className={cn('mx-auto mb-2', dragOver ? 'text-accent' : 'text-content-tertiary')} />
                <div className="text-xs font-medium text-content-primary mb-0.5">
                  {uploading ? 'Uploading…' : 'Drop files here'}
                </div>
                <div className="text-[10px] text-content-tertiary">
                  {uploading ? 'Please wait…' : `or click to browse`}
                </div>
                <div className="mt-1.5 text-[9px] text-content-tertiary font-mono bg-surface-2 rounded px-2 py-0.5 inline-block">
                  {tab.accept}
                </div>
              </div>
              <input ref={fileInputRef} type="file" multiple accept={tab.accept} className="hidden"
                onChange={e => handleUpload(e.target.files)} />
            </div>
          )}

          {/* Asset detail panel */}
          {selectedItem ? (
            <div className="rounded-xl border border-border bg-surface-0 overflow-hidden">
              <div className="px-3 py-2 border-b border-border flex items-center justify-between">
                <span className="text-xs font-semibold text-content-primary">Asset detail</span>
                <button onClick={() => setSelectedItem(null)}
                  className="w-6 h-6 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary">
                  <X size={12} />
                </button>
              </div>
              <div className="p-3 space-y-2.5">
                <div className="aspect-video bg-surface-2 rounded-md flex items-center justify-center">
                  <FileImage size={24} className="text-content-tertiary opacity-30" />
                </div>
                {[
                  ['Name', selectedItem.file_name || selectedItem.title || selectedItem.name || selectedItem.key?.split('/').pop() || '—'],
                  ['Provider', selectedItem.provider || selectedItem.source || '—'],
                  ['Type', selectedItem.media_type || selectedItem.type || '—'],
                  ['Size', selectedItem.file_size ? `${(selectedItem.file_size / 1024).toFixed(0)} KB` : selectedItem.size ? `${(selectedItem.size / 1024).toFixed(0)} KB` : '—'],
                  ['Score', selectedItem.quality_score != null ? `${(selectedItem.quality_score * 100).toFixed(0)}%` : '—'],
                ].map(([label, value]) => (
                  <div key={label as string}>
                    <div className="text-[9px] uppercase tracking-wider text-content-tertiary mb-0.5">{label}</div>
                    <div className="text-xs text-content-primary truncate">{value}</div>
                  </div>
                ))}
                {!tab.readOnly && (
                  <button
                    onClick={async () => {
                      if (!confirm('Delete this asset?')) return;
                      try {
                        const token = typeof window !== 'undefined' ? localStorage.getItem('dashboard_token') : null;
                        const base = process.env.NEXT_PUBLIC_API_URL || '';
                        await fetch(`${base}/api/v2/library/${activeTab}/${selectedItem.id || selectedItem.asset_id}`, {
                          method: 'DELETE',
                          headers: token ? { Authorization: `Bearer ${token}` } : {},
                        });
                        showToast('Asset deleted', 'success');
                        setSelectedItem(null);
                        loadItems();
                      } catch { showToast('Delete failed', 'error'); }
                    }}
                    className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-md border border-red-500/30 text-red-500 text-xs hover:bg-red-500/10 transition-colors mt-1">
                    <Trash2 size={11} /> Delete asset
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center">
              <Tag size={20} className="mx-auto text-content-tertiary opacity-30 mb-2" />
              <div className="text-xs text-content-tertiary">Select an asset to view details</div>
            </div>
          )}

          {/* Tips */}
          {activeTab === 'brand' && (
            <div className="p-3 rounded-xl bg-surface-1 border border-border text-[11px] text-content-tertiary space-y-1">
              <div className="font-medium text-content-secondary">💡 Brand assets</div>
              <p>Logos (PNG/SVG), watermarks, overlays. Scope by channel filter to organise per-channel kits.</p>
            </div>
          )}
          {activeTab === 'luts' && (
            <div className="p-3 rounded-xl bg-surface-1 border border-border text-[11px] text-content-tertiary">
              <div className="font-medium text-content-secondary">💡 LUT format</div>
              <p className="mt-0.5">.cube files (standard 3D LUT). Applied by Remotion post-processing to set a consistent look per channel.</p>
            </div>
          )}
          {activeTab === 'templates' && (
            <div className="p-3 rounded-xl bg-surface-1 border border-border text-[11px] text-content-tertiary">
              <div className="font-medium text-content-secondary">💡 Template format</div>
              <p className="mt-0.5">JSON preset files defining Remotion scene configurations. Becomes a reusable layout for your channels.</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

function AssetRow({ item, tab, selected, onSelect, onDeleted }: {
  item: any; tab: TabKey;
  selected?: boolean;
  onSelect?: () => void;
  onDeleted: () => void;
}) {
  const { showToast } = useToast();

  async function deleteAsset(e: React.MouseEvent) {
    e.stopPropagation();
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

  const name = item.file_name || item.title || item.name || item.key?.split('/').pop() || item.url?.split('/').pop() || 'Unknown';
  const provider = item.provider || item.source || '';
  const type = item.media_type || item.type || '';
  const size = item.file_size ? `${(item.file_size / 1024).toFixed(0)} KB` :
               item.size     ? `${(item.size / 1024).toFixed(0)} KB` : '';
  const score = item.quality_score != null ? `${(item.quality_score * 100).toFixed(0)}%` : '';

  return (
    <button
      onClick={onSelect}
      className={cn(
        'w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors',
        selected ? 'bg-accent/5 border-l-2 border-accent' : 'hover:bg-surface-1 border-l-2 border-transparent'
      )}>
      <div className="w-10 h-8 rounded-md bg-surface-2 shrink-0 flex items-center justify-center">
        <FileImage size={13} className="text-content-tertiary" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-xs font-medium text-content-primary truncate">{name}</div>
        <div className="text-[10px] text-content-tertiary truncate">
          {[provider, type, size, score].filter(Boolean).join(' · ')}
        </div>
      </div>
      {tab !== 'stock' && (
        <button onClick={deleteAsset} title="Delete"
          className="w-7 h-7 flex items-center justify-center rounded hover:bg-red-500/10 text-content-tertiary hover:text-red-500 transition-colors shrink-0">
          <Trash2 size={13} />
        </button>
      )}
    </button>
  );
}
