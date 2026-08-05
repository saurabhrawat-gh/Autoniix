'use client';

import { ShieldAlert } from './Icon';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogCloseButton,
  DialogTitle,
  DialogDescription,
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
      <DialogContent size="sm">
        <DialogHeader>
          <div>
            <DialogTitle className="flex items-center gap-2">
              <ShieldAlert size={14} className="text-status-error shrink-0" />
              Switch to Production?
            </DialogTitle>
            <DialogDescription>Paid APIs · real uploads to YouTube</DialogDescription>
          </div>
          <DialogCloseButton onClick={onCancel} />
        </DialogHeader>
        <DialogBody>
          <div className="space-y-3 text-sm">
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
          <DialogFooter>
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
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}
