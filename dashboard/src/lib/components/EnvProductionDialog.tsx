'use client';

import { ShieldAlert } from './Icon';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  Button,
} from '@/lib/ui';

interface EnvProductionDialogProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  switching?: boolean;
}

export function EnvProductionDialog({ open, onCancel, onConfirm, switching }: EnvProductionDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onCancel(); }}>
      <DialogContent className="max-w-md p-0 gap-0">
        <DialogHeader className="flex-row items-center gap-2 px-5 py-4 border-b border-border">
          <ShieldAlert size={18} className="text-status-error" />
          <DialogTitle className="text-sm">Switch to Production?</DialogTitle>
        </DialogHeader>
        <div className="px-5 py-4 space-y-3 text-sm">
          <p className="text-content-secondary">
            Production mode uses <span className="font-semibold text-content-primary">paid APIs</span> and
            <span className="font-semibold text-content-primary"> uploads to YouTube</span>.
          </p>
          <ul className="text-xs text-content-tertiary list-disc list-inside space-y-0.5">
            <li>Each video may cost $0.12–$0.35.</li>
            <li>Daily budget &amp; per-day limits apply.</li>
            <li>Generated videos are real and visible.</li>
          </ul>
        </div>
        <DialogFooter className="px-5 py-3 border-t border-border bg-surface-1/40">
          <Button variant="ghost" size="sm" onClick={onCancel}>Cancel</Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={onConfirm}
            disabled={switching}
            loading={switching}
          >
            {switching ? 'Switching…' : 'Switch to Production'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
