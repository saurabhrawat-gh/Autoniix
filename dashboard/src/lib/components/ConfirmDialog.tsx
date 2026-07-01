'use client';

/**
 * Reusable confirmation + prompt dialog primitives + a global imperative API
 * (`confirmDialog()` and `promptDialog()`) so any callsite can replace native
 * `confirm()` / `prompt()` / `alert()` with a single async call.
 *
 * Usage (declarative):
 *   <ConfirmDialog
 *     open={isOpen}
 *     onCancel={...}
 *     onConfirm={...}
 *     title="Delete this asset?"
 *     description="This cannot be undone."
 *     destructive
 *   />
 *
 * Usage (imperative — from anywhere in the React tree below <ConfirmDialogProvider/>):
 *   const ok = await confirmDialog({ title: 'Delete?', destructive: true });
 *   if (!ok) return;
 *
 *   const value = await promptDialog({ title: 'Type WIPE to confirm', match: 'WIPE' });
 *   if (value === null) return;
 *
 * Mount once at the root of the dashboard layout (already wired in the
 * dashboard layout) so every page can call the imperative API.
 */
import * as React from 'react';
import { AlertTriangle, Info } from 'lucide-react';
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
  Input,
  Label,
} from '../ui';

export interface ConfirmOptions {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  /** Hides the cancel button — turns the dialog into an alert. */
  alertOnly?: boolean;
}

export interface PromptOptions extends Omit<ConfirmOptions, 'alertOnly'> {
  label?: string;
  placeholder?: string;
  defaultValue?: string;
  /** When set, the confirm button is only enabled when input === match. */
  match?: string;
  /** When true, allows empty string as a valid value (no match required). */
  allowEmpty?: boolean;
  inputType?: 'text' | 'password' | 'email' | 'number';
}

export function ConfirmDialog(props: {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  loading?: boolean;
  title: string;
  description?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  alertOnly?: boolean;
}) {
  const {
    open, onCancel, onConfirm, loading,
    title, description,
    confirmLabel = 'Confirm', cancelLabel = 'Cancel',
    destructive = false, alertOnly = false,
  } = props;

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) onCancel(); }}>
      <DialogContent size="sm">
        <DialogHeader>
          <div>
            <DialogTitle className="flex items-center gap-2">
              {destructive
                ? <AlertTriangle size={14} className="text-status-error shrink-0" />
                : <Info size={14} className="text-accent shrink-0" />}
              {title}
            </DialogTitle>
            {description && <DialogDescription>{description}</DialogDescription>}
          </div>
          <DialogCloseButton onClick={onCancel} />
        </DialogHeader>
        <DialogBody>
          <DialogFooter>
            {!alertOnly && (
              <Button variant="outline" size="sm" onClick={onCancel} disabled={loading}>
                {cancelLabel}
              </Button>
            )}
            <Button
              variant={destructive ? 'destructive' : 'primary'}
              size="sm"
              onClick={onConfirm}
              loading={loading}
            >
              {confirmLabel}
            </Button>
          </DialogFooter>
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}

export function PromptDialog(props: {
  open: boolean;
  onCancel: () => void;
  onConfirm: (value: string) => void;
  loading?: boolean;
  title: string;
  description?: React.ReactNode;
  label?: string;
  placeholder?: string;
  defaultValue?: string;
  match?: string;
  allowEmpty?: boolean;
  inputType?: 'text' | 'password' | 'email' | 'number';
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}) {
  const {
    open, onCancel, onConfirm, loading,
    title, description,
    label, placeholder, defaultValue = '', match, allowEmpty = false,
    inputType = 'text',
    confirmLabel = 'Confirm', cancelLabel = 'Cancel',
    destructive = false,
  } = props;

  const [value, setValue] = React.useState(defaultValue);

  React.useEffect(() => {
    if (open) setValue(defaultValue);
  }, [open, defaultValue]);

  const isValid = match ? value === match : (allowEmpty || value.length > 0);

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) onCancel(); }}>
      <DialogContent size="sm">
        <DialogHeader>
          <div>
            <DialogTitle className="flex items-center gap-2">
              {destructive
                ? <AlertTriangle size={14} className="text-status-error shrink-0" />
                : <Info size={14} className="text-accent shrink-0" />}
              {title}
            </DialogTitle>
            {description && <DialogDescription>{description}</DialogDescription>}
          </div>
          <DialogCloseButton onClick={onCancel} />
        </DialogHeader>
        <DialogBody>
          <form
            onSubmit={e => { e.preventDefault(); if (isValid) onConfirm(value); }}
            className="space-y-2"
          >
            {label && <Label className="text-[11px] text-content-secondary">{label}</Label>}
            <Input
              type={inputType}
              value={value}
              onChange={e => setValue(e.target.value)}
              placeholder={placeholder}
              autoFocus
            />
          </form>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={onCancel} disabled={loading}>
              {cancelLabel}
            </Button>
            <Button
              variant={destructive ? 'destructive' : 'primary'}
              size="sm"
              onClick={() => isValid && onConfirm(value)}
              disabled={!isValid}
              loading={loading}
            >
              {confirmLabel}
            </Button>
          </DialogFooter>
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}

type Resolver<T> = (v: T) => void;

interface ConfirmRequest {
  kind: 'confirm';
  options: ConfirmOptions;
  resolve: Resolver<boolean>;
}

interface PromptRequest {
  kind: 'prompt';
  options: PromptOptions;
  resolve: Resolver<string | null>;
}

type Request = ConfirmRequest | PromptRequest;

let pushRequest: ((r: Request) => void) | null = null;

export function confirmDialog(options: ConfirmOptions): Promise<boolean> {
  return new Promise(resolve => {
    if (!pushRequest) {
      // eslint-disable-next-line no-alert
      resolve(typeof window !== 'undefined' ? window.confirm(options.title) : false);
      return;
    }
    pushRequest({ kind: 'confirm', options, resolve });
  });
}

export function promptDialog(options: PromptOptions): Promise<string | null> {
  return new Promise(resolve => {
    if (!pushRequest) {
      // eslint-disable-next-line no-alert
      const v = typeof window !== 'undefined' ? window.prompt(options.title, options.defaultValue ?? '') : null;
      resolve(v);
      return;
    }
    pushRequest({ kind: 'prompt', options, resolve });
  });
}

export function alertDialog(options: ConfirmOptions): Promise<void> {
  return new Promise(resolve => {
    confirmDialog({ ...options, alertOnly: true, confirmLabel: options.confirmLabel ?? 'OK' })
      .then(() => resolve());
  });
}

export function ConfirmDialogProvider({ children }: { children: React.ReactNode }) {
  const [request, setRequest] = React.useState<Request | null>(null);

  React.useEffect(() => {
    pushRequest = (r: Request) => setRequest(r);
    return () => { pushRequest = null; };
  }, []);

  const handleCancel = React.useCallback(() => {
    if (!request) return;
    if (request.kind === 'confirm') request.resolve(false);
    else request.resolve(null);
    setRequest(null);
  }, [request]);

  const handleConfirm = React.useCallback((value?: string) => {
    if (!request) return;
    if (request.kind === 'confirm') request.resolve(true);
    else request.resolve(value ?? '');
    setRequest(null);
  }, [request]);

  return (
    <>
      {children}
      {request?.kind === 'confirm' && (
        <ConfirmDialog
          open
          onCancel={handleCancel}
          onConfirm={() => handleConfirm()}
          title={request.options.title}
          description={request.options.description}
          confirmLabel={request.options.confirmLabel}
          cancelLabel={request.options.cancelLabel}
          destructive={request.options.destructive}
          alertOnly={request.options.alertOnly}
        />
      )}
      {request?.kind === 'prompt' && (
        <PromptDialog
          open
          onCancel={handleCancel}
          onConfirm={v => handleConfirm(v)}
          title={request.options.title}
          description={request.options.description}
          label={request.options.label}
          placeholder={request.options.placeholder}
          defaultValue={request.options.defaultValue}
          match={request.options.match}
          allowEmpty={request.options.allowEmpty}
          inputType={request.options.inputType}
          confirmLabel={request.options.confirmLabel}
          cancelLabel={request.options.cancelLabel}
          destructive={request.options.destructive}
        />
      )}
    </>
  );
}
