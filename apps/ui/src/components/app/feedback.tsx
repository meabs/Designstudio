import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Dialog, DialogPopup, DialogHeader, DialogTitle, DialogPanel, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { createStore, useSel, refresh } from '@/lib/store';

/* ---------- toast ---------- */
const toastStore = createStore({ msg: '' });
let toastTimer: number;
export function toast(msg: string) { toastStore.set({ msg }); clearTimeout(toastTimer); toastTimer = window.setTimeout(() => toastStore.set({ msg: '' }), 4500); }
export function Toaster() {
  const msg = useSel(toastStore, (s) => s.msg);
  return <div id="toast" role="status" aria-live="polite" className={cn('fixed bottom-16 left-1/2 z-[100] max-w-[92vw] -translate-x-1/2 rounded-lg bg-foreground px-5 py-3 text-sm text-background shadow-lg lg:bottom-10', !msg && 'hidden')}>{msg}</div>;
}

/* ---------- dialogs: one host, opened imperatively like the old modal() ---------- */
export type DialogSpec = { title: ReactNode; body: ReactNode; submit?: string; onSubmit?: (f: FormData) => Promise<unknown> | unknown; wide?: boolean; plain?: boolean; stay?: boolean; className?: string };
const dialogStore = createStore<{ spec: DialogSpec | null; open: boolean }>({ spec: null, open: false });
export const openDialog = (spec: DialogSpec) => dialogStore.set({ spec, open: true });
export const closeDialog = () => dialogStore.set({ open: false });
export function confirmDialog(title: string, body: ReactNode, submit: string, run: () => Promise<unknown>) { openDialog({ title, body, submit, onSubmit: run }); }

export function DialogHost() {
  const { spec, open } = useSel(dialogStore, (s) => s);
  const [busy, setBusy] = useState(false);
  if (!spec) return null;
  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault(); if (!spec.onSubmit) return; setBusy(true);
    try { await spec.onSubmit(new FormData(e.currentTarget)); await refresh(); if (!spec.stay) closeDialog(); } catch (err: any) { toast(err.message || 'Something went wrong'); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) closeDialog(); }} onOpenChangeComplete={(o) => { if (!o) dialogStore.set({ spec: null }); }}>
      <DialogPopup id="dialog" closeProps={{ id: 'close-dialog' }} className={cn(spec.wide ? 'max-w-3xl' : 'max-w-lg', spec.className)}>
        {spec.plain ? (
          <><DialogHeader><DialogTitle>{spec.title}</DialogTitle></DialogHeader><DialogPanel>{spec.body}</DialogPanel></>
        ) : (
          <form id="modal-form" onSubmit={submit} className="contents">
            <DialogHeader><DialogTitle>{spec.title}</DialogTitle></DialogHeader>
            <DialogPanel className="text-sm">{spec.body}</DialogPanel>
            <DialogFooter>
              <Button type="button" variant="outline" id="cancel-dialog" onClick={closeDialog}>Cancel</Button>
              <Button type="submit" className="primary" disabled={busy}>{spec.submit || 'Save'}</Button>
            </DialogFooter>
          </form>
        )}
      </DialogPopup>
    </Dialog>
  );
}

/* ---------- small shared pieces ---------- */
const BADGE: Record<string, 'outline' | 'success' | 'warning' | 'error' | 'secondary' | 'info'> = { '': 'secondary', success: 'success', warn: 'warning', warning: 'warning', fail: 'error', error: 'error', info: 'info' };
export function Tag({ kind = '', children, className, ...rest }: { kind?: string; children: ReactNode; className?: string } & React.HTMLAttributes<HTMLSpanElement>) {
  return <Badge variant={BADGE[kind] || 'outline'} className={className} {...rest}>{children}</Badge>;
}

export function useInterval(fn: () => void, ms: number, active = true) {
  const ref = useRef(fn); ref.current = fn;
  useEffect(() => { if (!active) return; const t = setInterval(() => ref.current(), ms); return () => clearInterval(t); }, [ms, active]);
}
export const Field = ({ label, htmlFor, children, className }: { label: ReactNode; htmlFor?: string; children: ReactNode; className?: string }) => (
  <div className={cn('mb-3 flex flex-col gap-1.5', className)}><label htmlFor={htmlFor} className="text-xs font-medium text-foreground">{label}</label>{children}</div>
);
export function Note({ kind = 'info', children, className }: { kind?: 'info' | 'warn'; children: ReactNode; className?: string }) {
  return <div className={cn('mb-4 rounded-lg border px-3 py-2.5 text-[13px] leading-relaxed', kind === 'warn' ? 'inline-note warn border-warning/32 bg-warning/6 text-warning-foreground' : 'inline-note border-border bg-muted/60 text-foreground', className)}>{children}</div>;
}
export function Empty({ title, text, children }: { title: string; text: ReactNode; children?: ReactNode }) {
  return <div className="empty mx-auto max-w-md px-6 py-16 text-center"><h2 className="mb-2 text-lg font-semibold">{title}</h2><p className="mb-4 text-sm text-muted-foreground">{text}</p>{children}</div>;
}

import { Card, CardHeader, CardTitle, CardAction, CardPanel } from '@/components/ui/card';
export function Panel({ title, action, children, id, className }: { title?: ReactNode; action?: ReactNode; children: ReactNode; id?: string; className?: string }) {
  return (
    <Card id={id} className={cn('card mb-4', className)}>
      {(title || action) && <CardHeader className="pb-3"><CardTitle render={<h2 />} className="text-base">{title}</CardTitle>{action && <CardAction>{action}</CardAction>}</CardHeader>}
      <CardPanel className={cn('text-sm', !(title || action) && 'pt-6')}>{children}</CardPanel>
    </Card>
  );
}
export const Content = ({ children, className }: { children: ReactNode; className?: string }) => <div className={cn('content max-w-[1120px] p-4 lg:p-7', className)}>{children}</div>;
