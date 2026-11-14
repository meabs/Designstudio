import { useEffect, useState } from 'react';
import { api, refresh, referencesOf, refUrl, useData } from '@/lib/store';
import { useRoute } from '@/lib/router';
import { Ic } from './icons';
import { toast } from './feedback';
import { cn } from '@/lib/utils';

const REF_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif']; const REF_MAX = 5_000_000;
const toBase64 = (file: File) => new Promise<string>((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1]); r.onerror = rej; r.readAsDataURL(file); });
const bus = new EventTarget();

export async function uploadRefs(files: File[], projectId: string) {
  const ids: string[] = [];
  for (const f of files) {
    if (!REF_TYPES.includes(f.type)) { toast(`${f.name}: use PNG, JPEG, WebP or GIF`); continue; }
    if (f.size > REF_MAX) { toast(`${f.name} is larger than 5 MB`); continue; }
    try { ids.push((await api('reference-upload', { project_id: projectId, name: f.name.replace(/\.[^.]+$/, ''), data: await toBase64(f) })).id); } catch (err: any) { toast(err.message); }
  }
  if (!ids.length) return ids;
  await refresh(); bus.dispatchEvent(new CustomEvent('uploaded', { detail: ids })); toast(`${ids.length} reference image${ids.length === 1 ? '' : 's'} added`); return ids;
}

// Picker used in the generate, research and handoff forms: tick images to send with the request; drop or paste to add.
export function RefPicker({ selected = [], projectId, id }: { selected?: string[]; projectId?: string; id?: string }) {
  const r = useRoute(); const pid = projectId || r.project?.id; useData(); const refs = referencesOf(pid);
  const [on, setOn] = useState<Set<string>>(new Set(selected)); const [over, setOver] = useState(false);
  useEffect(() => {
    const add = (e: Event) => setOn((s) => new Set([...s, ...((e as CustomEvent).detail as string[])]));
    bus.addEventListener('uploaded', add); return () => bus.removeEventListener('uploaded', add);
  }, []);
  useEffect(() => {
    const paste = (e: ClipboardEvent) => { const files = [...(e.clipboardData?.files || [])].filter((f) => f.type.startsWith('image/')); if (files.length) { e.preventDefault(); uploadRefs(files, pid); } };
    document.addEventListener('paste', paste); return () => document.removeEventListener('paste', paste);
  }, [pid]);
  return (
    <div id={id} data-ref-picker data-dropzone className={cn('refpicker mb-3 rounded-xl border border-dashed bg-background p-2.5', over && 'over border-foreground bg-muted')}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); uploadRefs([...e.dataTransfer.files], pid); }}>
      <div className="refgrid grid grid-cols-[repeat(auto-fill,minmax(92px,1fr))] gap-2">
        {refs.map((x) => (
          <label key={x.id} className={cn('refitem relative m-0 block cursor-pointer overflow-hidden rounded-md border bg-background', on.has(x.id) && 'on ring-2 ring-foreground')} title={x.name + (x.note ? ' · ' + x.note : '')}>
            <input type="checkbox" name="references" value={x.id} checked={on.has(x.id)} onChange={(e) => setOn((s) => { const n = new Set(s); e.target.checked ? n.add(x.id) : n.delete(x.id); return n; })} className="absolute left-1.5 top-1.5 z-10 size-4" />
            <img src={refUrl(x)} alt={x.name} className="aspect-square w-full object-cover" /><span className="block truncate px-1.5 py-1 text-[11px]">{x.name}</span>
          </label>
        ))}
        <label className="refadd m-0 grid min-h-24 cursor-pointer content-center justify-items-center gap-1 rounded-md border border-dashed text-[11px] text-muted-foreground hover:bg-muted"><Ic name="upload" size={16} /><span>Add images</span>
          <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" multiple hidden data-ref-upload onChange={(e) => { const files = [...(e.target.files || [])]; e.target.value = ''; uploadRefs(files, pid); }} /></label>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{refs.length ? 'Tick the images to send with this request. ' : ''}Drop or paste images here. PNG, JPEG, WebP or GIF, up to 5 MB each. Sent to the agent as files; the fixture runner cannot interpret them.</p>
    </div>
  );
}
