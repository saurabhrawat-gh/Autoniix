'use client';

import * as React from 'react';
import { X, Search, Check, ChevronDown } from 'lucide-react';
import { cn } from './cn';

export interface MultiSelectOption {
  value: string;
  label: string;
}

export interface MultiSelectProps {
  options: MultiSelectOption[];
  value?: string[];
  onChange?: (value: string[]) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  label?: string;
  hint?: string;
  error?: boolean;
  disabled?: boolean;
  id?: string;
  className?: string;
}

export function MultiSelect({
  options,
  value = [],
  onChange,
  placeholder = 'Select…',
  searchPlaceholder = 'Search…',
  label,
  hint,
  error,
  disabled,
  id,
  className,
}: MultiSelectProps) {
  const [open, setOpen] = React.useState(false);
  const [search, setSearch] = React.useState('');
  const containerRef = React.useRef<HTMLDivElement>(null);
  const searchRef = React.useRef<HTMLInputElement>(null);

  const filtered = React.useMemo(
    () =>
      options.filter((o) =>
        o.label.toLowerCase().includes(search.toLowerCase())
      ),
    [options, search]
  );

  const toggle = (optValue: string) => {
    if (!onChange) return;
    onChange(
      value.includes(optValue)
        ? value.filter((v) => v !== optValue)
        : [...value, optValue]
    );
  };

  const removeTag = (optValue: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onChange?.(value.filter((v) => v !== optValue));
  };

  React.useEffect(() => {
    if (open) {
      setTimeout(() => searchRef.current?.focus(), 50);
    } else {
      setSearch('');
    }
  }, [open]);

  React.useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const selectedLabels = value
    .map((v) => options.find((o) => o.value === v))
    .filter(Boolean) as MultiSelectOption[];

  return (
    <div className={cn('w-full', className)} ref={containerRef}>
      {label && (
        <label
          htmlFor={id}
          className="block text-caption font-medium text-content-secondary mb-1.5"
        >
          {label}
        </label>
      )}

      <div
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-multiselectable="true"
        onClick={() => !disabled && setOpen((o) => !o)}
        className={cn(
          'relative flex min-h-[48px] flex-wrap items-center gap-1.5 px-3 py-2 rounded-md border bg-surface-0',
          'cursor-pointer select-none',
          'transition-[border-color,box-shadow] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)]',
          open && !error && 'border-accent ring-2 ring-accent/10',
          !open && !error && 'border-border hover:border-border-hover',
          error && 'border-status-error ring-2 ring-status-error/15',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
      >
        {selectedLabels.map((opt) => (
          <span
            key={opt.value}
            role="option"
            aria-selected="true"
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-xs font-medium bg-surface-2 border border-border text-content-primary"
          >
            {opt.label}
            <button
              type="button"
              aria-label={`Remove ${opt.label}`}
              onClick={(e) => removeTag(opt.value, e)}
              className="ml-0.5 text-content-tertiary hover:text-content-primary transition-colors"
            >
              <X size={11} strokeWidth={2.5} />
            </button>
          </span>
        ))}

        {selectedLabels.length === 0 && (
          <span className="text-sm text-content-tertiary">{placeholder}</span>
        )}

        <ChevronDown
          size={15}
          className={cn(
            'ml-auto flex-shrink-0 text-content-tertiary transition-transform duration-150',
            open && 'rotate-180'
          )}
        />
      </div>

      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-md border border-border bg-surface-0 shadow-elevated overflow-hidden"
          style={{ minWidth: containerRef.current?.offsetWidth }}
        >
          <div className="p-2 border-b border-border">
            <div className="relative">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-content-tertiary pointer-events-none" />
              <input
                ref={searchRef}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={searchPlaceholder}
                className="w-full pl-8 pr-3 py-1.5 text-sm bg-surface-1 border border-border rounded-sm text-content-primary placeholder:text-content-tertiary focus:outline-none focus:border-accent"
                onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}
              />
            </div>
          </div>

          <ul role="listbox" className="max-h-48 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-content-muted text-center">No options</li>
            ) : (
              filtered.map((opt) => {
                const selected = value.includes(opt.value);
                return (
                  <li
                    key={opt.value}
                    role="option"
                    aria-selected={selected}
                    onClick={() => toggle(opt.value)}
                    className={cn(
                      'flex items-center justify-between px-3 py-2 text-sm cursor-pointer',
                      'transition-colors duration-[80ms]',
                      selected
                        ? 'bg-accent-light text-content-primary'
                        : 'text-content-secondary hover:bg-surface-2 hover:text-content-primary'
                    )}
                  >
                    {opt.label}
                    {selected && <Check size={13} className="text-accent flex-shrink-0" />}
                  </li>
                );
              })
            )}
          </ul>
        </div>
      )}

      {hint && (
        <p className={cn('mt-1.5 text-xs', error ? 'text-status-error' : 'text-content-tertiary')}>
          {hint}
        </p>
      )}
    </div>
  );
}
