"use client";

import { useEffect, useState, useCallback } from "react";
import { PageHeader } from "@/lib/components/PageHeader";
import { usePermissions } from "@/lib/hooks/usePermissions";
import { lookupValuesApi, LookupValue } from "@/lib/api-v2";
import { useToast } from "@/lib/toast";
import { Button, Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/lib/ui";
import { Plus, Edit2, PowerOff, Check, X } from "@/lib/components/Icon";
import { cn } from "@/lib/utils";

const OWNER_TYPES = [
  { value: "niche", label: "Niche" },
  { value: "sub_niche", label: "Sub-niche" },
  { value: "audience_tag", label: "Audience tag" },
  { value: "content_type_tag", label: "Content type tag" },
];

export default function CustomizationsPage() {
  const { role, loading } = usePermissions();
  const { showToast } = useToast();

  const [selectedType, setSelectedType] = useState<string>(OWNER_TYPES[0].value);
  const [rows, setRows] = useState<LookupValue[]>([]);
  const [fetching, setFetching] = useState(false);

  const globalRows = rows.filter((r) => r.workspace_id === null);
  const customRows = rows.filter((r) => r.workspace_id !== null);

  const [addValue, setAddValue] = useState("");
  const [addLabel, setAddLabel] = useState("");
  const [addParent, setAddParent] = useState("");
  const [saving, setSaving] = useState(false);

  const [editId, setEditId] = useState<number | null>(null);
  const [editLabel, setEditLabel] = useState("");

  const load = useCallback(async () => {
    setFetching(true);
    try {
      const res = await lookupValuesApi.list(selectedType);
      setRows(res.data ?? []);
    } catch {
      showToast("Failed to load values", "error");
    } finally {
      setFetching(false);
    }
  }, [selectedType, showToast]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAdd = async () => {
    if (!addValue.trim() || !addLabel.trim()) return;
    setSaving(true);
    try {
      await lookupValuesApi.createWorkspace({
        type: selectedType,
        value: addValue.trim(),
        label: addLabel.trim(),
        parent_value: addParent.trim() || undefined,
      });
      showToast("Custom value added", "success");
      setAddValue("");
      setAddLabel("");
      setAddParent("");
      load();
    } catch (e: any) {
      showToast(e.message ?? "Failed to add", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveEdit = async (id: number) => {
    try {
      await lookupValuesApi.update(id, { label: editLabel });
      showToast("Updated", "success");
      setEditId(null);
      load();
    } catch (e: any) {
      showToast(e.message ?? "Failed to update", "error");
    }
  };

  const handleDeactivate = async (id: number) => {
    try {
      await lookupValuesApi.deactivate(id);
      load();
    } catch (e: any) {
      showToast(e.message ?? "Failed to remove", "error");
    }
  };

  const isParentType = selectedType === "sub_niche";

  if (loading) return null;

  const canEdit = role === "owner";

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <PageHeader
        title="Customizations"
        subtitle="Add workspace-specific dropdown values on top of the global defaults."
      />

      {/* Type selector */}
      <div className="flex items-center gap-3">
        <Select value={selectedType} onValueChange={setSelectedType}>
          <SelectTrigger className="w-52">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OWNER_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-xs opacity-50">
          {customRows.length} custom + {globalRows.length} global defaults
        </span>
      </div>

      {/* Add custom value (owner only) */}
      {canEdit && (
        <div className="rounded-lg border border-border bg-surface-1 p-4">
          <div className="text-xs font-semibold opacity-60 uppercase tracking-wide mb-3">
            Add custom value
            <span className="ml-2 font-normal normal-case opacity-60">— visible only in this workspace</span>
          </div>
          <div className="flex flex-wrap gap-2 items-end">
            <div className="flex flex-col gap-1">
              <label className="text-xs opacity-60">Value (key)</label>
              <Input
                className="w-36"
                placeholder="my_niche"
                value={addValue}
                onChange={(e) => setAddValue(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs opacity-60">Label (display)</label>
              <Input
                className="w-48"
                placeholder="My Custom Niche"
                value={addLabel}
                onChange={(e) => setAddLabel(e.target.value)}
              />
            </div>
            {isParentType && (
              <div className="flex flex-col gap-1">
                <label className="text-xs opacity-60">Parent niche value</label>
                <Input
                  className="w-36"
                  placeholder="technology"
                  value={addParent}
                  onChange={(e) => setAddParent(e.target.value)}
                />
              </div>
            )}
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
      )}

      {/* Custom values table */}
      <section className="space-y-2">
        <h3 className="text-sm font-semibold">
          Custom values
          <span className="ml-2 text-xs font-normal opacity-50">— only your workspace sees these</span>
        </h3>
        <ValueTable
          rows={customRows}
          isParentType={isParentType}
          fetching={fetching}
          editId={editId}
          editLabel={editLabel}
          setEditLabel={setEditLabel}
          onStartEdit={(row) => {
            setEditId(row.id);
            setEditLabel(row.label);
          }}
          onSaveEdit={handleSaveEdit}
          onCancelEdit={() => setEditId(null)}
          onDeactivate={handleDeactivate}
          canEdit={canEdit}
          emptyMessage="No custom values yet — add your own above."
        />
      </section>

      {/* Global defaults (read-only reference) */}
      <section className="space-y-2">
        <h3 className="text-sm font-semibold">
          Global defaults
          <span className="ml-2 text-xs font-normal opacity-50">
            — managed by superadmin, visible to all workspaces
          </span>
        </h3>
        <ValueTable
          rows={globalRows}
          isParentType={isParentType}
          fetching={fetching}
          editId={null}
          editLabel=""
          setEditLabel={() => {}}
          onStartEdit={() => {}}
          onSaveEdit={async () => {}}
          onCancelEdit={() => {}}
          onDeactivate={async () => {}}
          canEdit={false}
          emptyMessage="No global defaults for this type."
        />
      </section>
    </div>
  );
}

interface ValueTableProps {
  rows: LookupValue[];
  isParentType: boolean;
  fetching: boolean;
  editId: number | null;
  editLabel: string;
  setEditLabel: (v: string) => void;
  onStartEdit: (row: LookupValue) => void;
  onSaveEdit: (id: number) => Promise<void>;
  onCancelEdit: () => void;
  onDeactivate: (id: number) => Promise<void>;
  canEdit: boolean;
  emptyMessage: string;
}

function ValueTable({
  rows,
  isParentType,
  fetching,
  editId,
  editLabel,
  setEditLabel,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onDeactivate,
  canEdit,
  emptyMessage,
}: ValueTableProps) {
  const colSpan = isParentType ? 4 : 3;

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-surface-1 border-b border-border">
          <tr>
            <th className="px-4 py-2 text-left font-medium opacity-60">Value</th>
            <th className="px-4 py-2 text-left font-medium opacity-60">Label</th>
            {isParentType && <th className="px-4 py-2 text-left font-medium opacity-60">Parent</th>}
            {canEdit && <th className="px-4 py-2 w-20" />}
          </tr>
        </thead>
        <tbody>
          {fetching ? (
            <tr>
              <td colSpan={colSpan} className="px-4 py-6 text-center opacity-40">
                Loading…
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={colSpan} className="px-4 py-6 text-center opacity-40">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={row.id}
                className={cn(
                  "border-b border-border last:border-0 hover:bg-surface-1/50",
                  !row.is_active && "opacity-40"
                )}
              >
                <td className="px-4 py-2 font-mono text-xs">{row.value}</td>
                <td className="px-4 py-2">
                  {canEdit && editId === row.id ? (
                    <Input
                      className="h-7 text-sm w-full"
                      value={editLabel}
                      onChange={(e) => setEditLabel(e.target.value)}
                    />
                  ) : (
                    row.label
                  )}
                </td>
                {isParentType && <td className="px-4 py-2 font-mono text-xs opacity-60">{row.parent_value ?? "—"}</td>}
                {canEdit && (
                  <td className="px-4 py-2">
                    <div className="flex justify-end gap-1">
                      {editId === row.id ? (
                        <>
                          <Button size="icon-sm" variant="ghost" onClick={() => onSaveEdit(row.id)} title="Save">
                            <Check size={13} />
                          </Button>
                          <Button size="icon-sm" variant="ghost" onClick={onCancelEdit} title="Cancel">
                            <X size={13} />
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button size="icon-sm" variant="ghost" onClick={() => onStartEdit(row)} title="Edit">
                            <Edit2 size={13} />
                          </Button>
                          <Button
                            size="icon-sm"
                            variant="ghost"
                            onClick={() => onDeactivate(row.id)}
                            title="Remove"
                            className="text-status-error hover:bg-status-error/10"
                          >
                            <PowerOff size={13} />
                          </Button>
                        </>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
