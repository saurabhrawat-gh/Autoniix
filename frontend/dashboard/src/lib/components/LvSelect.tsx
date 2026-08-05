'use client';

import { useState } from 'react';
import { Button, Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/lib/ui';
import type { LvOption } from '@/lib/hooks/useLookupValues';

interface LvSelectProps {
  opts: LvOption[];
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  /** Allow the user to type a free-text value not in the list */
  allowOther?: boolean;
  disabled?: boolean;
}

/**
 * A Select backed by `lookup_values` rows.
 * When `allowOther` is true, choosing "Other…" reveals a free-text Input.
 * If the current value is not in `opts` it auto-switches to text mode.
 */
export function LvSelect({
  opts,
  value,
  onChange,
  placeholder = '— Select —',
  allowOther = false,
  disabled = false,
}: LvSelectProps) {
  const inList = opts.some(o => o.value === value);
  const [showCustom, setShowCustom] = useState(allowOther && value !== '' && !inList);

  if (showCustom) {
    return (
      <div className="flex gap-2">
        <Input
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder="Type custom value…"
          className="flex-1"
          disabled={disabled}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => { setShowCustom(false); onChange(''); }}
          title="Back to list"
        >
          ↩
        </Button>
      </div>
    );
  }

  const selectVal = inList ? value : '__none__';

  return (
    <Select
      value={selectVal}
      onValueChange={(v: string) => {
        if (v === '__other__') { setShowCustom(true); onChange(''); }
        else if (v === '__none__') onChange('');
        else onChange(v);
      }}
      disabled={disabled}
    >
      <SelectTrigger>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__none__">{placeholder}</SelectItem>
        {opts.map(o => (
          <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
        ))}
        {allowOther && (
          <SelectItem value="__other__">Other (type custom)…</SelectItem>
        )}
      </SelectContent>
    </Select>
  );
}
