'use client';

import { useEffect, useState, useRef, useCallback, useDeferredValue } from 'react';
import { damApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import {
  Search, Archive, ShieldCheck, Palette, Type, Film,
  Layout, UploadCloud, X, Trash2, FileImage,
  RotateCw, Tag, Layers, Hash, Boxes, FolderOpen, Plus, ChevronRight,
  ChevronDown, Loader2, Star, ImageIcon, Video, FileAudio,
} from '@/lib/components/Icon';
import { Button, Input } from '@/lib/ui';
import { confirmDialog } from '@/lib/components/ConfirmDialog';

// constants

type Scope = 'system' | 'workspace' | 'brand' | 'channel';
type Kind = 'all' | 'image' | 'video' | 'audio' | 'font' | 'lut' | 'template' | 'document' | 'other';
type ViewMode = 'grid' | 'list';

const SCOPES: { key: Scope; label: string; icon: React.ReactNode; color: string }[] = [
  { key: 'system',    label: 'System',    icon: <Archive size={13} />,     color: 'text-slate-400' },
  { key: 'workspace', label: 'Workspace', icon: <Boxes size={13} />,       color: 'text-blue-500' },
  { key: 'brand',     label: 'Brand',     icon: <ShieldCheck size={13} />, color: 'text-violet-500' },
  { key: 'channel',   label: 'Channel',   icon: <Video size={13} />,       color: 'text-red-500' },
];

const KINDS: { key: Kind; label: string; icon: React.ReactNode; accept: string }[] = [
  { key: 'all',      label: 'All',       icon: <Boxes size={12} />,        accept: '*' },
  { key: 'image',    label: 'Images',    icon: <ImageIcon size={12} />,    accept: 'image/*' },
  { key: 'video',    label: 'Video',     icon: <Video size={12} />,        accept: 'video/*' },
  { key: 'audio',    label: 'Audio',     icon: <FileAudio size={12} />,    accept: 'audio/*' },
  { key: 'font',     label: 'Fonts',     icon: <Type size={12} />,         accept: '.ttf,.woff,.woff2,.otf' },
  { key: 'lut',      label: 'LUTs',      icon: <Palette size={12} />,      accept: '.cube,.3dl' },
  { key: 'template', label: 'Templates', icon: <Layout size={12} />,       accept: '.json' },
  { key: 'document', label: 'Docs',      icon: <Hash size={12} />,         accept: '.pdf,.md,.txt' },
];

function kindIcon(kind: string) {
  const map: Record<string, React.ReactNode> = {
    image: <ImageIcon size={13} className="text-sky-400" />,
    video: <Film size={13} className="text-red-400" />,
    audio: <FileAudio size={13} className="text-emerald-400" />,
    font:  <Type size={13} className="text-orange-400" />,
    lut:   <Palette size={13} className="text-pink-400" />,
    template: <Layout size={13} className="text-cyan-400" />,
    document: <Hash size={13} className="text-amber-400" />,
  };
  return map[kind] ?? <FileImage size={13} className="text-content-tertiary" />;
}

function fmtBytes(b: number | null | undefined): string {
  if (!b) return '—';
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

// Main page
export default function LibraryPage() {
  const { showToast } = useToast();
  // scope + kind
  const [scope, setScope] = useState<Scope>('workspace');
  const [kind, setKind] = useState<Kind>('all');
  // assets
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState('');
  const deferredQ = useDeferredValue(q);
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [detailAsset, setDetailAsset] = useState<any>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  // collections
  const [collections, setCollections] = useState<any[]>([]);
  const [collectionsOpen, setCollectionsOpen] = useState(true);
  const [newColName, setNewColName] = useState('');
  // brand kits
  const [brandKits, setBrandKits] = useState<any[]>([]);
  const [brandKitsOpen, setBrandKitsOpen] = useState(false);
  const [newKitName, setNewKitName] = useState('');
  // tags sidebar
  const [availableTags, setAvailableTags] = useState<string[]>([]);
  const [activeTag, setActiveTag] = useState<string | null>(null);
  // upload
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const acceptForKind = KINDS.find(k => k.key === kind)?.accept ?? '*';

  // data loading

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { scope, limit: 100 };
      if (kind !== 'all') params.kind = kind;
      if (deferredQ) params.q = deferredQ;
      if (activeTag) params.tag = activeTag;
      const r = await damApi.list(params);
      setItems(r.data || []);
    } catch { setItems([]); }
    setLoading(false);
  }, [scope, kind, deferredQ, activeTag]);

  const loadSidebar = useCallback(async () => {
    damApi.collections(scope).then(r => setCollections(r.data || [])).catch(() => {});
    damApi.brandKits('brand').then(r => setBrandKits(r.data || [])).catch(() => {});
    damApi.tags(scope).then(r => setAvailableTags(r.data || [])).catch(() => {});
  }, [scope]);

  useEffect(() => { loadItems(); }, [loadItems]);
  useEffect(() => { loadSidebar(); }, [loadSidebar]);

  const openDetail = async (item: any) => {
    setSelectedItem(item);
    setLoadingDetail(true);
    try {
      const r = await damApi.get(item.id);
      setDetailAsset(r.data);
    } catch { setDetailAsset(null); }
    setLoadingDetail(false);
  };

  // upload

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('dashboard_token') : null;
      const base = process.env.NEXT_PUBLIC_API_URL || '';
      const formData = new FormData();
      Array.from(files).forEach(f => formData.append('files', f));
      formData.append('scope', scope);
      formData.append('kind', kind === 'all' ? 'image' : kind);
      const res = await fetch(`${base}/api/v2/library/dam/upload`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const result = await res.json();
      const dedups = (result.results || []).filter((r: any) => r.dedup).length;
      showToast(`Uploaded ${result.count} file(s)${dedups ? ` · ${dedups} duplicate(s) skipped` : ''}`, 'success');
      loadItems();
    } catch (e: any) {
      showToast(e?.message || 'Upload failed', 'error');
    }
    setUploading(false);
  };

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  }

  const deleteAsset = async (id: number) => {
    const ok = await confirmDialog({
      title: 'Delete this asset?',
      description: 'This permanently removes the asset from your library.',
      destructive: true,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    await damApi.delete(id);
    showToast('Asset deleted', 'success');
    if (selectedItem?.id === id) { setSelectedItem(null); setDetailAsset(null); }
    loadItems();
  };

  const createCollection = async () => {
    if (!newColName.trim()) return;
    await damApi.createCollection({ name: newColName, scope });
    setNewColName('');
    loadSidebar();
  };

  const createBrandKit = async () => {
    if (!newKitName.trim()) return;
    await damApi.createBrandKit({ name: newKitName });
    setNewKitName('');
    loadSidebar();
  };

  // render

  return (
    <main className="flex-1 flex flex-col min-h-0 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
            <Archive size={18} className="text-accent" /> Asset Library
          </h1>
          <p className="text-xs text-content-tertiary mt-0.5">
            Scoped DAM — images, video, audio, fonts, LUTs, templates · SHA-256 dedup · semantic search
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          {/* Scope switcher */}
          {SCOPES.map(s => (
            <Button
              key={s.key}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => { setScope(s.key); setSelectedItem(null); setDetailAsset(null); }}
              className={cn(
                'h-7 px-2.5 text-xs',
                scope === s.key
                  ? 'border-accent/40 bg-accent/5 text-accent'
                  : 'border-border bg-surface-0 hover:bg-surface-1 text-content-tertiary'
              )}>
              <span className={scope === s.key ? s.color : ''}>{s.icon}</span>
              {s.label}
            </Button>
          ))}
          {/* View toggle + refresh */}
          <div className="flex items-center gap-0.5 bg-surface-1 border border-border rounded-md p-0.5">
            {(['grid', 'list'] as const).map(v => (
              <Button
                key={v}
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() => setViewMode(v)}
                aria-label={v === 'grid' ? 'Grid view' : 'List view'}
                className={cn('w-7 h-7',
                  viewMode === v ? 'bg-surface-0 text-content-primary shadow-sm hover:bg-surface-0' : 'text-content-tertiary hover:text-content-secondary')}>
                {v === 'grid' ? <Boxes size={13} /> : <Layers size={13} />}
              </Button>
            ))}
          </div>
          <Button variant="outline" size="icon-sm" onClick={loadItems} disabled={loading} aria-label="Refresh">
            <RotateCw size={13} className={cn(loading && 'animate-spin')} />
          </Button>
        </div>
      </div>

      {/* Kind filter + search bar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="flex items-center gap-1 flex-wrap">
          {KINDS.map(k => (
            <Button
              key={k.key}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setKind(k.key)}
              className={cn(
                'h-7 px-2.5 text-[11px]',
                kind === k.key
                  ? 'border-accent/40 bg-accent/5 text-accent'
                  : 'border-border bg-surface-0 hover:bg-surface-1 text-content-tertiary'
              )}>
              {k.icon} {k.label}
            </Button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[180px]">
          <Input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Search assets…"
            leftIcon={<Search size={12} />}
            className="h-8 text-xs pr-8"
          />
          {q && (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => setQ('')}
              aria-label="Clear search"
              className="absolute right-1 top-1/2 -translate-y-1/2 w-5 h-5 text-content-tertiary hover:text-content-primary"
            >
              <X size={11} />
            </Button>
          )}
        </div>
        <span className="text-[11px] text-content-tertiary shrink-0">{items.length} asset{items.length !== 1 ? 's' : ''}</span>
      </div>

      {/* 3-column layout */}
      <div className="flex gap-3 flex-1 min-h-0">

        {/* ── Left sidebar: Collections + Tags ── */}
        <div className="w-[180px] shrink-0 flex flex-col gap-3 overflow-y-auto">

          {/* Collections */}
          <div className="rounded-xl border border-border bg-surface-0 overflow-hidden">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setCollectionsOpen(o => !o)}
              className="w-full justify-between px-3 py-2 h-auto rounded-none text-[11px] font-semibold text-content-secondary"
            >
              <span className="flex items-center gap-1.5"><FolderOpen size={12} /> Collections</span>
              {collectionsOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
            </Button>
            {collectionsOpen && (
              <div className="border-t border-border divide-y divide-border">
                {collections.map(col => (
                  <Button
                    key={col.id}
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="w-full justify-start gap-1.5 px-3 py-1.5 h-auto rounded-none text-left">
                    <FolderOpen size={11} className="text-content-tertiary shrink-0" />
                    <span className="text-[11px] text-content-secondary truncate">{col.name}</span>
                    {col.kind === 'smart' && <Star size={9} className="text-status-warning shrink-0 ml-auto" />}
                  </Button>
                ))}
                {collections.length === 0 && (
                  <div className="px-3 py-2 text-[10px] text-content-tertiary italic">No collections yet</div>
                )}
                <div className="p-2 flex gap-1">
                  <Input value={newColName} onChange={e => setNewColName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && createCollection()}
                    placeholder="New collection…"
                    className="flex-1 h-6 text-[10px]" />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    onClick={createCollection}
                    aria-label="Create collection"
                    className="w-6 h-6"
                  >
                    <Plus size={10} />
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Brand Kits */}
          <div className="rounded-xl border border-border bg-surface-0 overflow-hidden">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setBrandKitsOpen(o => !o)}
              className="w-full justify-between px-3 py-2 h-auto rounded-none text-[11px] font-semibold text-content-secondary"
            >
              <span className="flex items-center gap-1.5"><ShieldCheck size={12} /> Brand Kits</span>
              {brandKitsOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
            </Button>
            {brandKitsOpen && (
              <div className="border-t border-border divide-y divide-border">
                {brandKits.map(kit => (
                  <Button
                    key={kit.id}
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="w-full justify-start gap-1.5 px-3 py-1.5 h-auto rounded-none text-left">
                    <ShieldCheck size={11} className="text-violet-400 shrink-0" />
                    <span className="text-[11px] text-content-secondary truncate">{kit.name}</span>
                    <span className="ml-auto text-[9px] text-content-tertiary">v{kit.version_no}</span>
                  </Button>
                ))}
                {brandKits.length === 0 && (
                  <div className="px-3 py-2 text-[10px] text-content-tertiary italic">No brand kits yet</div>
                )}
                <div className="p-2 flex gap-1">
                  <Input value={newKitName} onChange={e => setNewKitName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && createBrandKit()}
                    placeholder="New kit…"
                    className="flex-1 h-6 text-[10px]" />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    onClick={createBrandKit}
                    aria-label="Create brand kit"
                    className="w-6 h-6"
                  >
                    <Plus size={10} />
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Tags */}
          {availableTags.length > 0 && (
            <div className="rounded-xl border border-border bg-surface-0 overflow-hidden">
              <div className="px-3 py-2 text-[11px] font-semibold text-content-secondary border-b border-border flex items-center gap-1.5">
                <Tag size={11} /> Tags
              </div>
              <div className="p-2 flex flex-wrap gap-1">
                {availableTags.slice(0, 20).map(t => (
                  <Button
                    key={t}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setActiveTag(activeTag === t ? null : t)}
                    className={cn(
                      'h-auto text-[10px] px-1.5 py-0.5',
                      activeTag === t
                        ? 'border-accent/40 bg-accent/5 text-accent'
                        : 'border-border text-content-tertiary hover:border-border-hover hover:text-content-secondary'
                    )}>
                    {t}
                  </Button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── Centre: Asset grid/list ── */}
        <div className="flex-1 min-w-0 flex flex-col gap-2 overflow-y-auto">
          {loading ? (
            <div className={cn('grid gap-2', viewMode === 'grid' ? 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4' : 'grid-cols-1')}>
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className={cn('rounded-lg bg-surface-2 animate-pulse', viewMode === 'grid' ? 'aspect-video' : 'h-11')} />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                'flex-1 py-20 flex flex-col items-center justify-center rounded-xl border-2 border-dashed cursor-pointer transition-colors',
                dragOver ? 'border-accent bg-accent/5' : 'border-border hover:border-accent/30 hover:bg-surface-1'
              )}>
              <UploadCloud size={28} className={cn('mb-3', dragOver ? 'text-accent' : 'text-content-tertiary opacity-40')} />
              <div className="text-sm font-medium text-content-primary">No assets in {scope} · {kind === 'all' ? 'all kinds' : kind}</div>
              <div className="text-xs text-content-tertiary mt-1">Drop files here or click to upload</div>
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-2">
              {items.map((item: any, i: number) => (
                <Button
                  key={item.id || i}
                  type="button"
                  variant="ghost"
                  onClick={() => openDetail(item)}
                  className={cn(
                    'rounded-lg border h-auto p-0 overflow-hidden text-left transition-all hover:shadow-card group flex-col items-stretch justify-start',
                    selectedItem?.id === item.id ? 'border-accent ring-1 ring-accent/20' : 'border-border hover:border-border-hover'
                  )}>
                  <div className="aspect-video bg-surface-2 flex items-center justify-center relative">
                    {item.thumbnail_key
                      ? <img src={`/api/v2/storage/thumb?key=${encodeURIComponent(item.thumbnail_key)}`} alt="" className="w-full h-full object-cover" />
                      : <div className="opacity-30">{kindIcon(item.kind)}</div>
                    }
                    <div className="absolute top-1 left-1">
                      <span className="text-[9px] px-1 py-0.5 rounded bg-surface-0/80 backdrop-blur-sm text-content-secondary">{item.kind}</span>
                    </div>
                  </div>
                  <div className="px-2 py-1.5">
                    <div className="text-[10px] font-medium text-content-primary truncate">{item.display_name}</div>
                    <div className="text-[9px] text-content-tertiary">{fmtBytes(item.bytes)}</div>
                  </div>
                </Button>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border overflow-hidden">
              {items.map((item: any, i: number) => (
                <Button
                  key={item.id || i}
                  type="button"
                  variant="ghost"
                  onClick={() => openDetail(item)}
                  className={cn(
                    'w-full justify-start gap-3 px-3 py-2.5 h-auto rounded-none text-left',
                    selectedItem?.id === item.id
                      ? 'bg-accent/5 border-l-2 border-accent'
                      : 'hover:bg-surface-1 border-l-2 border-transparent'
                  )}>
                  <div className="w-8 h-8 rounded-md bg-surface-2 shrink-0 flex items-center justify-center">
                    {kindIcon(item.kind)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-medium text-content-primary truncate">{item.display_name}</div>
                    <div className="text-[10px] text-content-tertiary truncate">
                      {[item.kind, item.mime_type, fmtBytes(item.bytes), item.origin].filter(Boolean).join(' · ')}
                    </div>
                  </div>
                  {(item.tags || []).slice(0, 2).map((t: string) => (
                    <span key={t} className="text-[9px] px-1.5 py-0.5 rounded-full bg-surface-2 text-content-tertiary shrink-0">{t}</span>
                  ))}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={e => { e.stopPropagation(); deleteAsset(item.id); }}
                    aria-label="Delete asset"
                    className="w-7 h-7 shrink-0 text-content-tertiary hover:text-status-error hover:bg-status-error/10"
                  >
                    <Trash2 size={12} />
                  </Button>
                </Button>
              ))}
            </div>
          )}
        </div>

        {/* ── Right rail: Upload + Detail ── */}
        <div className="w-[240px] shrink-0 flex flex-col gap-3 overflow-y-auto">
          {/* Upload dropzone */}
          <div
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
            className={cn(
              'rounded-xl border-2 border-dashed p-4 text-center transition-colors cursor-pointer',
              dragOver ? 'border-accent bg-accent/5' : 'border-border hover:border-accent/30 hover:bg-surface-1'
            )}>
            {uploading
              ? <Loader2 size={20} className="mx-auto text-accent animate-spin mb-1.5" />
              : <UploadCloud size={20} className={cn('mx-auto mb-1.5', dragOver ? 'text-accent' : 'text-content-tertiary')} />}
            <div className="text-xs font-medium text-content-primary mb-0.5">
              {uploading ? 'Uploading…' : 'Drop files here'}
            </div>
            <div className="text-[10px] text-content-tertiary">
              Scope: <span className="font-medium">{scope}</span> · Kind: <span className="font-medium">{kind === 'all' ? 'image' : kind}</span>
            </div>
            <div className="mt-1.5 text-[9px] text-content-tertiary font-mono bg-surface-2 rounded px-1.5 py-0.5 inline-block">
              {acceptForKind}
            </div>
          </div>
          <input ref={fileInputRef} type="file" multiple accept={acceptForKind} className="hidden"
            onChange={e => handleUpload(e.target.files)} />

          {/* Asset detail */}
          {selectedItem ? (
            <div className="rounded-xl border border-border bg-surface-0 overflow-hidden flex-1">
              <div className="px-3 py-2 border-b border-border flex items-center justify-between">
                <span className="text-xs font-semibold text-content-primary">Detail</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => { setSelectedItem(null); setDetailAsset(null); }}
                  aria-label="Close detail"
                  className="w-6 h-6 text-content-tertiary"
                >
                  <X size={12} />
                </Button>
              </div>
              <div className="p-3 space-y-3">
                {/* Preview placeholder */}
                <div className="aspect-video bg-surface-2 rounded-md flex items-center justify-center">
                  {loadingDetail
                    ? <Loader2 size={18} className="text-content-tertiary animate-spin" />
                    : <div className="opacity-30">{kindIcon(selectedItem.kind)}</div>}
                </div>
                {/* Meta */}
                {[
                  ['Name', selectedItem.display_name],
                  ['Kind', selectedItem.kind],
                  ['Size', fmtBytes(selectedItem.bytes)],
                  ['Origin', selectedItem.origin],
                  ['License', selectedItem.license || '—'],
                  ['Scope', `${selectedItem.scope}${selectedItem.scope_id ? `/${selectedItem.scope_id}` : ''}`],
                ].map(([l, v]) => (
                  <div key={l as string}>
                    <div className="text-[9px] uppercase tracking-wider text-content-tertiary">{l}</div>
                    <div className="text-xs text-content-primary truncate">{v || '—'}</div>
                  </div>
                ))}
                {/* Tags */}
                {(detailAsset || selectedItem).tags?.length > 0 && (
                  <div>
                    <div className="text-[9px] uppercase tracking-wider text-content-tertiary mb-1">Tags</div>
                    <div className="flex flex-wrap gap-1">
                      {(detailAsset || selectedItem).tags.map((t: string) => (
                        <span key={t} className="text-[9px] px-1.5 py-0.5 rounded-full bg-surface-2 border border-border text-content-secondary">{t}</span>
                      ))}
                    </div>
                  </div>
                )}
                {/* AI Tags */}
                {detailAsset?.ai_tags && Object.keys(detailAsset.ai_tags).length > 0 && (
                  <div>
                    <div className="text-[9px] uppercase tracking-wider text-content-tertiary mb-1">AI Tags</div>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(detailAsset.ai_tags).slice(0, 8).map(([t, c]: [string, any]) => (
                        <span key={t} className="text-[9px] px-1.5 py-0.5 rounded-full bg-accent/10 border border-accent/20 text-accent">
                          {t} {Math.round(Number(c) * 100)}%
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {/* Versions */}
                {detailAsset?.versions?.length > 0 && (
                  <div>
                    <div className="text-[9px] uppercase tracking-wider text-content-tertiary mb-1">Versions ({detailAsset.versions.length})</div>
                    {detailAsset.versions.slice(0, 3).map((v: any) => (
                      <div key={v.id} className="flex items-center gap-1.5 py-0.5">
                        <span className="text-[9px] text-content-tertiary font-mono">v{v.version_no}</span>
                        <span className="text-[9px] text-content-tertiary">{fmtBytes(v.bytes)}</span>
                        <span className="text-[9px] text-content-tertiary ml-auto">{new Date(v.created_at).toLocaleDateString()}</span>
                      </div>
                    ))}
                  </div>
                )}
                {/* Pipeline jobs */}
                {detailAsset?.media_jobs?.length > 0 && (
                  <div>
                    <div className="text-[9px] uppercase tracking-wider text-content-tertiary mb-1">Pipeline</div>
                    <div className="space-y-0.5">
                      {detailAsset.media_jobs.slice(0, 5).map((j: any, i: number) => (
                        <div key={i} className="flex items-center gap-1.5">
                          <span className={cn('w-1.5 h-1.5 rounded-full shrink-0',
                            j.status === 'done' ? 'bg-status-success' :
                            j.status === 'failed' ? 'bg-status-error' :
                            j.status === 'running' ? 'bg-status-warning animate-pulse' : 'bg-surface-3')} />
                          <span className="text-[9px] text-content-tertiary">{j.kind}</span>
                          <span className="text-[9px] text-content-tertiary ml-auto">{j.status}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {/* Delete */}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => deleteAsset(selectedItem.id)}
                  leftIcon={<Trash2 size={11} />}
                  className="w-full border-status-error/30 text-status-error hover:bg-status-error/10 hover:text-status-error"
                >
                  Delete asset
                </Button>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border px-4 py-10 text-center">
              <Tag size={18} className="mx-auto text-content-tertiary opacity-30 mb-2" />
              <div className="text-xs text-content-tertiary">Select an asset to inspect</div>
            </div>
          )}
        </div>

      </div>
    </main>
  );
}
