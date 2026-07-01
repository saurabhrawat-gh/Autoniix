'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { PageHeader } from '@/lib/components/PageHeader';
import { usePermissions } from '@/lib/hooks/usePermissions';
import { lookupValuesApi, LookupValue } from '@/lib/api-v2';
import { useToast } from '@/lib/toast';
import {
  Button, Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/lib/ui';
import { Plus, Edit2, PowerOff, Check, X } from '@/lib/components/Icon';
import { cn } from '@/lib/utils';


const VALUE_TYPES = [
  { value: 'niche',            label: 'Niche' },
  { value: 'sub_niche',        label: 'Sub-niche' },
  { value: 'language',         label: 'Language' },
  { value: 'geography',        label: 'Geography' },
  { value: 'age_group',        label: 'Age group' },
  { value: 'audience_tag',     label: 'Audience tag' },
  { value: 'content_type_tag', label: 'Content type tag' },
  { value: 'lut',              label: 'LUT preset' },
];


export default function LookupValuesPage() {
  const { globalRole, loading } = usePermissions();
  const router = useRouter();
  const { showToast } = useToast();

  const [selectedType, setSelectedType] = useState<string>(VALUE_TYPES[0].value);
  const [rows, setRows] = useState<LookupValue[]>([]);
  const [fetching, setFetching] = useState(false);
  const [showInactive, setShowInactive] = useState(false);

  const [addValue, setAddValue] = useState('');
  const [addLabel, setAddLabel] = useState('');
  const [addParent, setAddParent] = useState('');
  const [addSort, setAddSort] = useState('0');
  const [saving, setSaving] = useState(false);

  const [editId, setEditId] = useState<number | null>(null);
  const [editLabel, setEditLabel] = useState('');
  const [editSort, setEditSort] = useState('');

  useEffect(() => {
    if (!loading && globalRole !== 'superadmin') router.replace('/dashboard');
  }, [loading, globalRole, router]);

  const load = useCallback(async () => {
    setFetching(true);
    try {
      const res = await lookupValuesApi.list(selectedType);
      const data = (res.data ?? []).filter((r: LookupValue) => showInactive || r.is_active);
      setRows(data);
    } catch {
      showToast('Failed to load lookup values', 'error');
    } finally {
      setFetching(false);
    }
  }, [selectedType, showInactive, showToast]);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    if (!addValue.trim() || !addLabel.trim()) return;
    setSaving(true);
    try {
      await lookupValuesApi.createGlobal({
        type: selectedType,
        value: addValue.trim(),
        label: addLabel.trim(),
        parent_value: addParent.trim() || undefined,
        sort_order: Number(addSort) || 0,
      });
      showToast('Added', 'success');
      setAddValue(''); setAddLabel(''); setAddParent(''); setAddSort('0');
      load();
    } catch (e: any) {
      showToast(e.message ?? 'Failed to add', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveEdit = async (id: number) => {
    try {
      await lookupValuesApi.update(id, { label: editLabel, sort_order: Number(editSort) });
      showToast('Updated', 'success');
      setEditId(null);
      load();
    } catch (e: any) {
      showToast(e.message ?? 'Failed to update', 'error');
    }
  };

  const handleToggle = async (row: LookupValue) => {
    try {
      if (row.is_active) {
        await lookupValuesApi.deactivate(row.id);
      } else {
        await lookupValuesApi.update(row.id, { is_active: true });
      }
      load();
    } catch (e: any) {
      showToast(e.message ?? 'Failed to toggle', 'error');
    }
  };

  if (loading || globalRole !== 'superadmin') return null;

  const isParentType = selectedType === 'sub_niche';

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <PageHeader
        title="Lookup Values"
        subtitle="Manage global dropdown options visible to all workspaces."
      />

      {/* Type selector + toggle */}
      <div className="flex items-center gap-3 flex-wrap">
        <Select value={selectedType} onValueChange={setSelectedType}>
          <SelectTrigger className="w-52"><SelectValue /></SelectTrigger>
          <SelectContent>
            {VALUE_TYPES.map(t => (
              <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <label className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={e => setShowInactive(e.target.checked)}
            className="rounded"
          />
          Show inactive
        </label>
        <span className="text-xs opacity-50 ml-auto">{rows.length} values</span>
      </div>

      {/* Add row */}
      <div className="rounded-lg border border-border bg-surface-1 p-4">
        <div className="text-xs font-semibold opacity-60 uppercase tracking-wide mb-3">Add global value</div>
        <div className="flex flex-wrap gap-2 items-end">
          <div className="flex flex-col gap-1">
            <label className="text-xs opacity-60">Value (key)</label>
            <Input className="w-36" placeholder="ai_ml" value={addValue} onChange={e => setAddValue(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs opacity-60">Label (display)</label>
            <Input className="w-48" placeholder="AI & Machine Learning" value={addLabel} onChange={e => setAddLabel(e.target.value)} />
          </div>
          {isParentType && (
            <div className="flex flex-col gap-1">
              <label className="text-xs opacity-60">Parent value</label>
              <Input className="w-36" placeholder="technology" value={addParent} onChange={e => setAddParent(e.target.value)} />
            </div>
          )}
          <div className="flex flex-col gap-1">
            <label className="text-xs opacity-60">Sort order</label>
            <Input className="w-20" type="number" value={addSort} onChange={e => setAddSort(e.target.value)} />
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={handleAdd}
            disabled={saving || !addValue.trim() || !addLabel.trim()}
            className="self-end"
          >
            <Plus size={14} className="mr-1" /> Add
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-surface-1 border-b border-border">
            <tr>
              <th className="px-4 py-2 text-left font-medium opacity-60">Value</th>
              <th className="px-4 py-2 text-left font-medium opacity-60">Label</th>
              {isParentType && <th className="px-4 py-2 text-left font-medium opacity-60">Parent</th>}
              <th className="px-4 py-2 text-right font-medium opacity-60">Sort</th>
              <th className="px-4 py-2 text-center font-medium opacity-60">Active</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {fetching ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center opacity-40">Loading…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center opacity-40">No values yet</td></tr>
            ) : rows.map(row => (
              <tr key={row.id} className={cn('border-b border-border last:border-0 hover:bg-surface-1/50', !row.is_active && 'opacity-40')}>
                <td className="px-4 py-2 font-mono text-xs">{row.value}</td>
                <td className="px-4 py-2">
                  {editId === row.id ? (
                    <Input className="h-7 text-sm w-full" value={editLabel} onChange={e => setEditLabel(e.target.value)} />
                  ) : row.label}
                </td>
                {isParentType && <td className="px-4 py-2 font-mono text-xs opacity-60">{row.parent_value ?? '—'}</td>}
                <td className="px-4 py-2 text-right">
                  {editId === row.id ? (
                    <Input className="h-7 text-sm w-16 ml-auto" type="number" value={editSort} onChange={e => setEditSort(e.target.value)} />
                  ) : row.sort_order}
                </td>
                <td className="px-4 py-2 text-center">
                  <span className={cn('w-2 h-2 rounded-full inline-block', row.is_active ? 'bg-status-success' : 'bg-border')} />
                </td>
                <td className="px-4 py-2">
                  <div className="flex justify-end gap-1">
                    {editId === row.id ? (
                      <>
                        <Button size="icon-sm" variant="ghost" onClick={() => handleSaveEdit(row.id)} title="Save"><Check size={13} /></Button>
                        <Button size="icon-sm" variant="ghost" onClick={() => setEditId(null)} title="Cancel"><X size={13} /></Button>
                      </>
                    ) : (
                      <>
                        <Button size="icon-sm" variant="ghost" onClick={() => { setEditId(row.id); setEditLabel(row.label); setEditSort(String(row.sort_order)); }} title="Edit">
                          <Edit2 size={13} />
                        </Button>
                        <Button size="icon-sm" variant="ghost" onClick={() => handleToggle(row)} title={row.is_active ? 'Deactivate' : 'Activate'}
                          className={row.is_active ? 'text-status-error hover:bg-status-error/10' : 'text-status-success hover:bg-status-success/10'}>
                          <PowerOff size={13} />
                        </Button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
