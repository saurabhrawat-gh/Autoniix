'use client';

import { Keyboard } from './Icon';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  Kbd,
} from '@/lib/ui';

interface ShortcutHelpProps {
  open: boolean;
  onClose: () => void;
}

const SHORTCUTS: Array<{ keys: string[]; label: string }> = [
  { keys: ['g', 'd'], label: 'Go to Dashboard' },
  { keys: ['g', 'p'], label: 'Go to Progress' },
  { keys: ['g', 's'], label: 'Go to Settings' },
  { keys: ['g', 'l'], label: 'Go to Library' },
  { keys: ['g', 'q'], label: 'Go to Render Queue' },
  { keys: ['g', 'e'], label: 'Go to Experiments' },
  { keys: ['n'], label: 'New Channel' },
  { keys: ['?'], label: 'Show this help' },
  { keys: ['Esc'], label: 'Close dialog / help' },
];

export function ShortcutHelp({ open, onClose }: ShortcutHelpProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md p-0 gap-0">
        <div className="flex items-center gap-2 px-5 py-4 border-b border-border">
          <Keyboard size={16} className="text-accent" />
          <DialogTitle className="text-sm">Keyboard Shortcuts</DialogTitle>
        </div>
        <ul className="px-5 py-4 space-y-2.5">
          {SHORTCUTS.map((s, i) => (
            <li key={i} className="flex items-center justify-between text-sm">
              <span className="text-content-secondary">{s.label}</span>
              <span className="flex items-center gap-1">
                {s.keys.map((k, j) => (
                  <Kbd key={j} className="min-w-[1.5rem] h-6 px-1.5 text-[11px] text-content-primary">{k}</Kbd>
                ))}
              </span>
            </li>
          ))}
        </ul>
        <div className="px-5 py-3 border-t border-border bg-surface-1/40 text-[11px] text-content-tertiary">
          Shortcuts are disabled while typing in input fields.
        </div>
      </DialogContent>
    </Dialog>
  );
}
