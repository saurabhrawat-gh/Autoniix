'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, GitCompare } from 'lucide-react';
import { reviewApi } from '@/lib/api-v2';

/** Line-based LCS diff producing {kind: 'eq'|'add'|'del', text: string}[]. */
function diffLines(aText: string, bText: string) {
  const a = (aText || '').split(/\r?\n/);
  const b = (bText || '').split(/\r?\n/);
  const m = a.length, n = b.length;
  // dp[i][j] = LCS length of a[0..i] vs b[0..j]
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: { kind: 'eq' | 'add' | 'del'; text: string }[] = [];
  let i = 0, j = 0;
  while (i < m && j < n) {
    if (a[i] === b[j]) { out.push({ kind: 'eq', text: a[i] }); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push({ kind: 'del', text: a[i] }); i++; }
    else { out.push({ kind: 'add', text: b[j] }); j++; }
  }
  while (i < m) { out.push({ kind: 'del', text: a[i++] }); }
  while (j < n) { out.push({ kind: 'add', text: b[j++] }); }
  return out;
}

function bodyOf(version: any): string {
  if (!version || !version.content) return '';
  const c = typeof version.content === 'string' ? safeParse(version.content) : version.content;
  if (c && typeof c === 'object' && typeof c.raw === 'string') return c.raw;
  return JSON.stringify(c, null, 2);
}
function safeParse(s: string) { try { return JSON.parse(s); } catch { return s; } }

export default function ScriptDiffPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<any>(null);
  const [aIdx, setAIdx] = useState(1);
  const [bIdx, setBIdx] = useState(0);
  const [view, setView] = useState<'inline' | 'split'>('inline');

  useEffect(() => {
    reviewApi.get(id).then(r => setData(r.data)).catch(() => setData(null));
  }, [id]);

  const versions = useMemo(() => (data?.script_versions || []) as any[], [data]);

  if (!data) return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      <div className="text-content-tertiary text-sm">Loading…</div>
    </main>
  );

  if (versions.length < 2) return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      <Link href={`/dashboard/review/${id}`} className="inline-flex items-center gap-1 text-sm text-content-secondary hover:text-content-primary mb-4">
        <ArrowLeft size={14} /> Back to review
      </Link>
      <div className="rounded-xl border border-border bg-surface-0 p-6 text-sm text-content-tertiary text-center">
        Need at least two versions to diff. This script has {versions.length}.
      </div>
    </main>
  );

  const A = versions[aIdx];
  const B = versions[bIdx];
  const diff = diffLines(bodyOf(A), bodyOf(B));
  const counts = diff.reduce((acc, d) => { acc[d.kind]++; return acc; }, { eq: 0, add: 0, del: 0 });

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      <div className="flex items-center gap-3 mb-4">
        <Link href={`/dashboard/review/${id}`} className="inline-flex items-center gap-1 text-sm text-content-secondary hover:text-content-primary">
          <ArrowLeft size={14} /> Back
        </Link>
        <h1 className="text-lg font-semibold inline-flex items-center gap-2">
          <GitCompare size={16} /> Script diff
        </h1>
        <div className="ml-auto inline-flex items-center gap-1 rounded-lg border border-border p-0.5 bg-surface-1">
          {(['inline', 'split'] as const).map(v => (
            <button key={v} onClick={() => setView(v)}
              className={'px-2 py-1 text-xs rounded ' + (view === v ? 'bg-accent text-white' : 'text-content-secondary hover:text-content-primary')}>
              {v}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <VersionPicker label="Old (A)" value={aIdx} versions={versions} onChange={setAIdx} />
        <VersionPicker label="New (B)" value={bIdx} versions={versions} onChange={setBIdx} />
      </div>

      <div className="text-xs text-content-tertiary mb-2 flex items-center gap-3">
        <span>+{counts.add} additions</span>
        <span>−{counts.del} deletions</span>
        <span>{counts.eq} unchanged</span>
      </div>

      {view === 'inline' ? (
        <pre className="rounded-xl border border-border bg-surface-0 p-3 text-xs font-mono leading-5 overflow-auto max-h-[70vh]">
          {diff.map((d, i) => (
            <div key={i} className={
              d.kind === 'add' ? 'bg-status-success/10 text-status-success' :
              d.kind === 'del' ? 'bg-status-error/10 text-status-error' : ''}>
              <span className="select-none w-4 inline-block opacity-50">
                {d.kind === 'add' ? '+' : d.kind === 'del' ? '−' : ' '}
              </span>
              {d.text || '\u00A0'}
            </div>
          ))}
        </pre>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          <SplitColumn diff={diff} side="A" />
          <SplitColumn diff={diff} side="B" />
        </div>
      )}
    </main>
  );
}

function VersionPicker({ label, value, versions, onChange }: any) {
  return (
    <label className="block">
      <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1">{label}</div>
      <select value={value} onChange={e => onChange(Number(e.target.value))}
        className="w-full px-2 py-1.5 rounded-lg bg-surface-1 border border-border text-sm">
        {versions.map((v: any, i: number) => (
          <option key={v.id} value={i}>
            v{v.version} · {v.source} · {new Date(v.created_at).toLocaleString()}
          </option>
        ))}
      </select>
    </label>
  );
}

function SplitColumn({ diff, side }: { diff: { kind: 'eq' | 'add' | 'del'; text: string }[]; side: 'A' | 'B' }) {
  return (
    <pre className="rounded-xl border border-border bg-surface-0 p-3 text-xs font-mono leading-5 overflow-auto max-h-[70vh]">
      {diff.map((d, i) => {
        const show = side === 'A' ? d.kind !== 'add' : d.kind !== 'del';
        if (!show) return <div key={i}>&nbsp;</div>;
        const cls =
          d.kind === 'add' ? 'bg-status-success/10 text-status-success' :
          d.kind === 'del' ? 'bg-status-error/10 text-status-error' : '';
        return <div key={i} className={cls}>{d.text || '\u00A0'}</div>;
      })}
    </pre>
  );
}
