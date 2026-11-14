// Designer tools: audit, rule-break log, style extraction, realistic states, decision log, review documents, responsive preview.
import { useEffect, useState } from 'react';
import { api, refresh, getData, ui, enabledRunners, ensureDraft, live, useData, twinOf, freeOf, profilesOf, activeProfileId, profileOfVariant, useUi, isDirty } from '@/lib/store';
import { navigate, getCurrent, nav, useCurrent } from '@/lib/router';
import { uuid, ago } from '@/lib/format';
import { openDialog, confirmDialog, toast, Tag, Note, Field, Panel } from '@/components/app/feedback';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Ic, type IconName } from '@/components/app/icons';
import { cn } from '@/lib/utils';

/* ---------- audit (manual) ---------- */
const AREA: Record<string, string> = { accessibility: 'Accessibility', legal: 'Legal & compliance', content: 'Content & voice', 'design-review': 'Design review' };
const OUT_ICON: Record<string, [IconName, string]> = { pass: ['check', 'text-success-foreground'], fail: ['x', 'text-destructive-foreground'], review: ['eye', 'text-warning-foreground'], not_assessable: ['eye', 'text-muted-foreground'] };

function AuditRow({ f, v, a }: { f: any; v: any; a: any }) {
  const [ic, cls] = OUT_ICON[f.outcome] || OUT_ICON.review; const d = f.review?.decision;
  const set = async (decision: string) => { try { await api('audit-review', { variant_id: v.id, audit_id: a.id, index: f.index, decision }); await refresh(); } catch (e: any) { toast(e.message); } };
  return (
    <div className="auditrow my-3 flex items-start gap-2.5 text-[13px]" data-audit-outcome={f.outcome}>
      <span className={cn('mt-0.5', cls)}><Ic name={ic} size={13} /></span>
      <span className="min-w-0 flex-1">{f.check}
        <small className="mt-0.5 block text-xs text-muted-foreground">{f.evidence}</small>
        <small className="mt-0.5 block text-[11px] text-muted-foreground">{f.screen_title}{f.source ? ` · ${f.source}` : ''}</small>
        {(f.outcome === 'fail' || f.outcome === 'review') && <span className="mt-1.5 flex flex-wrap items-center gap-2">{d === 'accepted' ? <Tag kind="success">Accepted</Tag> : d === 'needs_change' ? <Tag kind="fail">Needs change</Tag> : <Tag kind="warn">Not yet reviewed</Tag>}<Button size="xs" variant="outline" disabled={d === 'accepted'} onClick={() => set('accepted')}>{f.outcome === 'fail' ? 'Accept as exception' : 'Mark OK'}</Button><Button size="xs" variant="outline" disabled={d === 'needs_change'} onClick={() => set('needs_change')}>Needs change</Button></span>}
      </span>
    </div>
  );
}

const DOC_LABEL: Record<string, string> = { fails: 'Agent says it fails', unclear: 'Agent could not tell', meets: 'Agent says it meets' };
function DocReview({ v, p }: { v: any; p: any }) {
  const data = useData(); const runners = enabledRunners(); const [rid, setRid] = useState(''); const [busy, setBusy] = useState(false);
  const jobs = data.job.filter((j: any) => j.type === 'audit_review' && j.target_variant_id === v.id).sort((a: any, b: any) => b.created_at - a.created_at);
  const active = jobs.find((j: any) => ['queued', 'running'].includes(j.status)); const failed = !active && jobs[0]?.status !== 'succeeded' && jobs[0] && !jobs[0].retried_by ? jobs[0] : null;
  const dr = (v.doc_reviews || []).at(-1); const chosen = rid || runners[0]?.id || '';
  const go = async () => { setBusy(true); try { await api('audit-docs', { variant_id: v.id, runner_id: chosen }); await refresh(); toast('Agent is reading your documents'); } catch (e: any) { toast(e.message); } finally { setBusy(false); } };
  const order = ['fails', 'unclear', 'meets'];
  return (
    <div className="mt-5 border-t pt-4" id="doc-review">
      <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Agent reading of your documents</h3>
      <p className="mb-2 text-xs text-muted-foreground">For the checklist items that can’t be matched literally. An agent reads your documents and these screens and gives its opinion. It is unverified and costs an agent run. Never a sign-off.</p>
      {!p.review_folder ? <p className="text-xs text-muted-foreground">Set a review documents folder first.</p> : <div className="flex gap-2"><select aria-label="Agent for document review" value={chosen} onChange={(e) => setRid(e.target.value)} className="h-9 min-w-0 flex-1 rounded-lg border border-input bg-background px-2 text-sm">{runners.map((x: any) => <option key={x.id} value={x.id}>{x.name}{x.type === 'fixture' ? ' (template; cannot read)' : ''}</option>)}</select><Button variant="outline" data-action="audit-docs" disabled={busy || !!active || !chosen} onClick={go}>{active ? 'Reading…' : dr ? 'Read again' : 'Read'}</Button></div>}
      {active && <p className="mt-2 text-xs text-muted-foreground" role="status">{active.events.at(-1)?.message || 'Queued'}</p>}
      {failed && <Note kind="warn">The last attempt {failed.status === 'failed' ? 'failed' : failed.status.replace('_', ' ')}: {failed.events.at(-1)?.message}</Note>}
      {dr && <div className="mt-3"><div className="mb-1 flex flex-wrap items-center gap-1.5"><Tag kind="warn">Agent opinion · unverified</Tag><span className="text-xs text-muted-foreground">{dr.runner_name} · {ago(dr.at)}</span></div>
        <div className="mb-2 flex gap-1.5"><Tag kind={dr.counts.fails ? 'fail' : ''}>{dr.counts.fails} fail</Tag><Tag>{dr.counts.unclear} unclear</Tag><Tag>{dr.counts.meets} meet</Tag></div>
        {dr.summary && <p className="mb-2 text-xs">{dr.summary}</p>}
        {order.map((k) => dr.findings.filter((f: any) => f.outcome === k).map((f: any) => <div key={f.criterion_id} className="my-3 text-[13px]" data-doc-outcome={k}><span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{DOC_LABEL[k]}</span><br />{f.text}<small className="mt-0.5 block text-xs text-muted-foreground">{f.evidence}</small><small className="block text-[11px] text-muted-foreground">{f.doc}:{f.line}{f.screen_ids?.length ? ` · screens ${f.screen_ids.join(', ')}` : ''}</small></div>))}
        {dr.limitations?.length > 0 && <p className="text-[11px] text-muted-foreground">Limits it reported: {dr.limitations.join(' ')}</p>}
        <p className="mt-2 text-[11px] text-muted-foreground">{dr.note}</p></div>}
    </div>
  );
}

export function AuditTab({ v }: { v: any }) {
  const { p } = useCurrent(); const a = (v.audits || []).at(-1); const [busy, setBusy] = useState(false);
  const run = async () => { setBusy(true); try { await api('audit', { variant_id: v.id }); await refresh(); toast('Audit complete'); } catch (e: any) { toast(e.message); } finally { setBusy(false); } };
  const groups = a ? Object.keys(AREA).map((k) => [k, a.findings.filter((f: any) => f.area === k)] as const).filter(([, l]) => l.length) : [];
  return (
    <div className="px-4 py-3.5" id="audit-panel">
      <p className="mb-2 text-xs text-muted-foreground">Runs only when you press the button, on this exact version. Static checks of the delivered screens plus the criteria in your review documents. Evidence for a reviewer, not a certification.</p>
      <p className="mb-3 text-xs">{p.review_folder ? <>Review documents: <span className="font-mono">{p.review_folder}</span></> : <>No review documents folder set, so only built-in accessibility checks run. <a className="underline" href="/settings/agents" onClick={(e) => { e.preventDefault(); navigate('/settings/agents'); }}>Add one in Settings</a>.</>}</p>
      <Button className="primary mb-3 w-full" data-action="run-audit" disabled={busy} onClick={run}><Ic name="shield" size={13} /> {busy ? 'Auditing…' : a ? 'Run audit again' : 'Run audit on this version'}</Button>
      {a && <>
        <div className="mb-1 flex flex-wrap items-center gap-1.5"><Tag kind={a.counts.fail ? 'fail' : 'success'}>{a.counts.fail} fail</Tag><Tag kind="warn">{a.counts.review} to review</Tag><Tag>{a.counts.pass} pass</Tag><span className="text-xs text-muted-foreground">{ago(a.at)} · {a.docs.length} document{a.docs.length === 1 ? '' : 's'}</span></div>
        {a.folder_error && <Note kind="warn">{a.folder_error}</Note>}
        {a.skipped.length > 0 && <p className="text-xs text-muted-foreground">Skipped: {a.skipped.join('; ')}</p>}
        {groups.map(([k, list]) => {
          const bad = list.filter((f: any) => f.outcome === 'fail'); const rev = list.filter((f: any) => f.outcome === 'review'); const na = list.filter((f: any) => f.outcome === 'not_assessable'); const ok = list.filter((f: any) => f.outcome === 'pass');
          return <div key={k} className="mt-4"><h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{AREA[k]}</h3>
            {[...bad, ...rev].map((f: any) => <AuditRow key={f.index} f={f} v={v} a={a} />)}
            {(na.length > 0 || ok.length > 0) && <details className="text-xs"><summary className="cursor-pointer text-muted-foreground">{ok.length} passed{na.length ? ` · ${na.length} not assessable` : ''}</summary>{[...na, ...ok].map((f: any) => <AuditRow key={f.index} f={f} v={v} a={a} />)}</details>}
          </div>;
        })}
        <p className="mt-4 text-[11px] text-muted-foreground">{a.note}</p>
      </>}
      <DocReview v={v} p={p} />
    </div>
  );
}

/* ---------- rule-break log (free runs) ---------- */
export function RuleBreaks({ v }: { v: any }) {
  const rb = v.rule_breaks; if (!rb) return null;
  const bad = rb.results.filter((r: any) => r.outcome === 'fail'); const rev = rb.results.filter((r: any) => r.outcome === 'review'); const ok = rb.results.filter((r: any) => r.outcome === 'pass').length;
  return (
    <div className="inspect-block border-b px-4 py-3.5" id="rule-breaks">
      <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Rule-break log · free run</h3>
      <p className="mb-2 text-xs text-muted-foreground">Nothing was enforced on this run. Against guideline v{rb.context_version}: {bad.length} would have failed, {rev.length} need your eye, {ok} pass. A break you like is a candidate guideline change.</p>
      {bad.map((r: any, i: number) => <div key={i} className="my-2 flex items-start gap-2 text-[13px]"><span className="mt-0.5 text-destructive-foreground"><Ic name="x" size={13} /></span><span className="flex-1">{r.check}<small className="block text-xs text-muted-foreground">{r.evidence}</small><Button size="xs" variant="outline" className="mt-1" data-propose={i} onClick={() => proposeRule(r.check)}>Propose a guideline change</Button></span></div>)}
      {rev.length > 0 && <details className="text-xs"><summary className="cursor-pointer text-muted-foreground">{rev.length} for your review</summary>{rev.map((r: any, i: number) => <p key={i} className="my-1.5">{r.check}</p>)}</details>}
    </div>
  );
}
export function ProfileTag({ v, b }: { v: any; b?: any }) {
  const data = useData(); const p = data.project.find((x: any) => x.id === v.project_id); if (profilesOf(p).length < 2 || (b?.blind && !b.revealed)) return null;
  return <Tag data-profile-tag>{profileOfVariant(v, data).name}</Tag>;
}
export function proposeRule(check: string) {
  const { ctx, r } = getCurrent(); if (!ctx) return; ensureDraft(ctx); const d = ui.get().draft as any; const existing = d.rules.findIndex((x: any) => x.description === check);
  openDialog({ title: 'Propose a guideline change', submit: 'Add to guideline draft', body: <>
    <p className="mb-2 text-xs text-muted-foreground">{existing >= 0 ? 'Rewrite this rule so it allows what you liked.' : 'Add a rule that captures what you liked.'} It goes into your unsaved guideline draft; nothing changes for other runs until you save a version.</p>
    <Field label="Rule wording" htmlFor="pr-text"><Textarea id="pr-text" name="text" rows={3} required defaultValue={existing >= 0 ? check : ''} placeholder="What should the guideline say?" /></Field></>,
  onSubmit: (f) => {
    const dd = ui.get().draft as any; const text = String(f.get('text')).trim(); const rules = [...dd.rules];
    if (existing >= 0 && rules[existing]) rules[existing] = { ...rules[existing], description: text, justification: 'Proposed from a free-exploration run' };
    else rules.push({ id: 'PROP-' + (rules.length + 1), description: text, scope: 'project', severity: 'warning', verification: 'human_review', enabled: true, justification: 'Proposed from a free-exploration run' });
    ui.set({ draft: { ...dd, rules } }); toast('Added to your guideline draft. Review and save it in Guidelines.'); navigate(nav(r, 'context'));
  } });
}

/* ---------- pull style into the guidelines ---------- */
function StylePicker({ v }: { v: any }) {
  const [rows, setRows] = useState<any[] | null>(null);
  useEffect(() => { api('extract-style', { variant_id: v.id }).then(setRows).catch((e) => { toast(e.message); setRows([]); }); }, [v.id]);
  if (!rows) return <p className="text-sm text-muted-foreground">Reading the screens…</p>;
  if (!rows.length) return <p className="text-sm text-muted-foreground">No colours, fonts or radii found in this version.</p>;
  return <>
    <p className="mb-2 text-xs text-muted-foreground">Values found in this version’s screens, most used first. Tick what to adopt and name it. Saving creates a new guideline version; earlier jobs keep their own snapshot.</p>
    {rows.map((x, i) => <div key={i} className="my-1.5 flex items-center gap-2 text-sm">
      <input type="checkbox" name={`use:${i}`} className="size-4" disabled={x.known} defaultChecked={false} aria-label={`Adopt ${x.value}`} />
      {x.kind === 'color' ? <span className="size-5 shrink-0 rounded border" style={{ background: x.value }} /> : <span className="w-5 shrink-0 text-center text-xs">{x.kind === 'font' ? 'Aa' : '◜'}</span>}
      <Input name={`name:${i}`} defaultValue={x.name} className="w-32" aria-label={`Token name for ${x.value}`} /><input type="hidden" name={`value:${i}`} value={x.value} />
      <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground" title={x.value}>{x.value}</span><span className="text-xs text-muted-foreground">{x.known ? 'already a token' : `×${x.count}`}</span></div>)}
  </>;
}
export function styleModal(v: any) {
  const { p } = getCurrent();
  openDialog({ title: 'Pull this style into the guidelines', submit: 'Save as new guideline version', wide: true, body: <StylePicker v={v} />,
    onSubmit: async (f) => {
      const tokens: Record<string, string> = {}; for (const k of [...f.keys()]) if (k.startsWith('use:')) { const i = k.slice(4); tokens[String(f.get('name:' + i)).trim()] = String(f.get('value:' + i)); }
      if (!Object.keys(tokens).length) throw Error('Tick at least one value');
      const pid = profileOfVariant(v).id; const c = await api('apply-style', { project_id: p.id, tokens, ...(profilesOf(getData().project.find((x) => x.id === p.id)).some((x: any) => x.id === pid) ? { profile_id: pid } : {}) }); await refresh(); toast(`Guidelines saved as v${c.version}`);
    } });
}

/* ---------- realistic states ---------- */
export function statesModal(v: any) {
  const { p, b, r } = getCurrent(); if (!b) return;
  confirmDialog('Add realistic states', <p>Asks the agent to add empty, loading, error and long-content states to every screen of <strong>{v.runner_name} v{v.version}</strong>. It becomes a new revision; this version is untouched.</p>, 'Add states', async () => {
    const rid = v.runner_id || enabledRunners()[0]?.id; await api('revise', { project_id: p.id, board_id: b.id, parent_id: v.id, brief: b.brief, runner_ids: [rid], states: true, idempotency_key: uuid() });
    toast('Revision queued: adding realistic states'); await refresh(); navigate(nav(r, 'boards') + '/' + b.id);
  });
}

/* ---------- set aside + decision log ---------- */
export function setAsideModal(v: any) {
  openDialog({ title: `Set aside ${v.runner_name} v${v.version}`, submit: 'Set aside', body: <>
    <p className="mb-2 text-xs text-muted-foreground">Nothing is deleted; the version stays on the board. Your reason goes in the decision log.</p>
    <Field label="Why? (one line)" htmlFor="sa-note"><Textarea id="sa-note" name="note" rows={2} placeholder="e.g. Too dense for a first step" /></Field></>,
  onSubmit: async (f) => { await api('set-aside', { id: v.id, note: f.get('note') }); await refresh(); toast('Recorded in the decision log'); } });
}
const DEC: Record<string, string> = { approved: 'Chose', set_aside: 'Set aside', accepted: 'Accepted revision', reverted: 'Reverted revision' };
const decLabel = (data: any, d: any) => { const x = data.variant.find((y: any) => y.id === d.variant_id); return x ? `${x.runner_name} v${x.version}` : 'a version'; };
export function decisionMarkdown(data: any, b: any) {
  return `## Decisions: ${b.title}\n\n_Brief: ${b.brief}_\n\n` + (b.decisions || []).map((d: any) => `- **${new Date(d.at * 1000).toLocaleString()}** · ${DEC[d.decision]} **${decLabel(data, d)}**${d.note ? ` — ${d.note}` : ''}`).join('\n') + '\n';
}
export function DecisionLog({ b }: { b: any }) {
  const data = useData(); const list = (b.decisions || []) as any[]; if (!list.length) return null;
  const copy = () => { const md = decisionMarkdown(data, b); try { navigator.clipboard.writeText(md).then(() => toast('Copied as Markdown')).catch(() => show(md)); } catch { show(md); } };
  const show = (md: string) => openDialog({ title: 'Decision log as Markdown', plain: true, wide: true, body: <Textarea readOnly rows={12} defaultValue={md} onFocus={(e) => e.currentTarget.select()} /> });
  return <div className="mb-4" data-decision-log={b.id}><div className="mb-1.5 flex items-center justify-between"><h3 className="font-semibold">{b.title}</h3><Button size="xs" variant="outline" onClick={copy}>Copy as Markdown</Button></div>
    <ol className="space-y-1.5 border-l pl-3">{list.slice().reverse().map((d) => <li key={d.id} className="text-[13px]"><span className="text-xs text-muted-foreground">{new Date(d.at * 1000).toLocaleString()}</span><br />{DEC[d.decision]} <strong>{decLabel(data, d)}</strong>{d.note ? <span className="text-muted-foreground"> · “{d.note}”</span> : <span className="text-xs text-muted-foreground"> · no reason recorded</span>}</li>)}</ol></div>;
}
export function DecisionsPanel() {
  const { boards } = useCurrent(); const withDec = boards.filter((b: any) => (b.decisions || []).length); if (!withDec.length) return null;
  return <Panel title="Decision log">{withDec.map((b: any) => <DecisionLog key={b.id} b={b} />)}</Panel>;
}

/* ---------- review documents (settings) ---------- */
export function ReviewDocsPanel() {
  const { p } = useCurrent(); const [info, setInfo] = useState<any>(null); const [path, setPath] = useState(p.review_folder || '');
  useEffect(() => { setPath(p.review_folder || ''); api('review-docs', { project_id: p.id }).then(setInfo).catch(() => setInfo(null)); }, [p.id, p.review_folder]);
  const save = async () => { try { const r = await api('set-review-folder', { project_id: p.id, folder: path }); setInfo({ ...r, folder: r.project.review_folder, error: '' }); await refresh(); toast(path.trim() ? 'Review documents folder saved' : 'Review documents folder cleared'); } catch (e: any) { toast(e.message); } };
  return (
    <Panel title="Review documents" id="review-docs">
      <p className="mb-3 text-xs text-muted-foreground">Point this project at a folder of Markdown files (design reviews, accessibility and legal checklists, brand notes). The audit reads them, read-only, each time you run it. Checklist lines like <code>- [ ] Must include “Representative APR”</code> or <code>- [ ] Never say “guaranteed approval”</code> are checked against the screens; everything else becomes a review item with its source line. Set from the computer running the studio.</p>
      <div className="flex gap-2"><Input id="review-folder" value={path} onChange={(e) => setPath(e.target.value)} placeholder="/home/you/design-reviews" aria-label="Review documents folder" /><Button variant="outline" data-action="save-review-folder" onClick={save}>Save</Button></div>
      {info?.error && <p className="mt-2 text-xs text-destructive-foreground">{info.error}</p>}
      {info?.docs?.length > 0 && <ul className="mt-3 space-y-1 text-xs">{info.docs.map((d: any) => <li key={d.file}><span className="font-mono">{d.file}</span> · {d.title} · {d.criteria} criteria</li>)}</ul>}
      {info?.folder && !info.error && !info.docs?.length && <p className="mt-2 text-xs text-muted-foreground">No .md files found in that folder.</p>}
      {info?.skipped?.length > 0 && <p className="mt-2 text-xs text-muted-foreground">Skipped: {info.skipped.join('; ')}</p>}
    </Panel>
  );
}

/* ---------- responsive preview ---------- */
const WIDTHS: [string, number | null][] = [['Phone', 390], ['Tablet', 768], ['Desktop', null]];
export function LivePreview({ v, sid }: { v: any; sid: string }) {
  const target = getData().board.find((x: any) => x.id === v.board_id)?.target; const [w, setW] = useState<number | null>(target === 'mobile' ? 390 : null); const url = live(v, sid);
  return <>
    <div className="mb-2 flex items-center gap-1.5" role="group" aria-label="Preview width">{WIDTHS.map(([l, x]) => <Button key={l} size="xs" variant={w === x ? 'default' : 'outline'} aria-pressed={w === x} data-preview-width={l.toLowerCase()} onClick={() => setW(x)}>{l}{x ? ` ${x}` : ''}</Button>)}</div>
    <div className="flex justify-center rounded-md bg-muted/40 p-0"><iframe className="live-frame h-[64vh] rounded-md border bg-white max-sm:h-[calc(100dvh-11rem)]" style={{ width: w ? Math.min(w, 2000) : '100%', maxWidth: '100%' }} title="Live preview of generated screen" sandbox="allow-scripts allow-forms" src={url} /></div>
    <p className="mt-2 flex items-center justify-between text-xs text-muted-foreground"><span>Sandboxed preview. Interactions are mocked; nothing is submitted.</span><a className="underline" target="_blank" rel="noopener" href={url}>Full page <Ic name="external" size={11} className="inline" /></a></p>
  </>;
}

/* ---------- compare twin helper ---------- */
export function twinLink(v: any) {
  const t = twinOf(v); if (!t) return null; const free = freeOf(v) ? v : t; const normal = freeOf(v) ? t : v; return { left: normal.id, right: free.id, twin: t };
}
void getData;


/* ---------- import existing guideline files (DESIGN.md, rules, tokens) into the draft ---------- */
const readFiles = async (list: FileList | File[]) => Promise.all([...list].map(async (f: any) => ({ name: f.webkitRelativePath || f.name, text: await f.text() })));
export function ImportPanel() {
  const { p, ctx } = useCurrent(); const [folder, setFolder] = useState(p.guidelines_folder || ''); const [res, setRes] = useState<any>(null); const [busy, setBusy] = useState(false);
  const [useDocs, setUseDocs] = useState<Set<string>>(new Set()); const [useRules, setUseRules] = useState<Set<number>>(new Set()); const [useTok, setUseTok] = useState<Set<string>>(new Set()); const [replace, setReplace] = useState(false);
  useEffect(() => { setFolder(p.guidelines_folder || ''); }, [p.id, p.guidelines_folder]);
  const show = (r: any) => {
    const d = (ui.get().draft as any) || ctx; const have = new Set((d.rules || []).map((x: any) => String(x.description).toLowerCase())); let tokens: any = {}; try { tokens = JSON.parse(d.tokens || '{}'); } catch { /* ignore */ }
    setRes(r); setUseDocs(new Set(r.docs.filter((x: any) => x.use).map((x: any) => x.file))); setUseRules(new Set(r.rules.filter((x: any) => !have.has(x.description.toLowerCase())).map((x: any) => x.n)));
    setUseTok(new Set(r.tokens.filter((x: any) => String(tokens[x.name]) !== x.value).map((x: any) => x.name)));
  };
  const run = async (body: any) => { setBusy(true); try { const r = await api('scan-guidelines', body); show(r); if (body.folder) await refresh(); if (!r.docs.length && !r.rules.length && !r.tokens.length) toast('Nothing importable found in those files'); } catch (e: any) { toast(e.message); } finally { setBusy(false); } };
  const toggle = <T,>(set: Set<T>, k: T, on: boolean, fn: (s: Set<T>) => void) => { const n = new Set(set); on ? n.add(k) : n.delete(k); fn(n); };
  const apply = () => {
    ensureDraft(ctx); const dd = ui.get().draft as any; const docs = res.docs.filter((x: any) => useDocs.has(x.file));
    let markdown = dd.markdown; if (docs.length) { const text = docs.map((x: any) => (docs.length > 1 ? `<!-- from ${x.file} -->\n` : '') + x.text.trim()).join('\n\n'); markdown = replace || !markdown.trim() ? text : markdown.trimEnd() + '\n\n' + text; }
    let tokens: any = {}; if (!replace) { try { tokens = JSON.parse(dd.tokens); } catch { return toast('Fix the tokens JSON in your draft first'); } } for (const t of res.tokens) if (useTok.has(t.name)) tokens[t.name] = t.value;
    const rules = replace && useRules.size ? [] : [...dd.rules]; const ids = new Set(rules.map((r: any) => r.id)); const have = new Set(rules.map((r: any) => String(r.description).toLowerCase())); let added = 0;
    for (const r of res.rules) { if (!useRules.has(r.n) || have.has(r.description.toLowerCase())) continue; let id = r.id || 'IMPORT-' + String(r.n).padStart(3, '0'); while (ids.has(id)) id += '-b'; ids.add(id); rules.push({ id, description: r.description, scope: 'project', severity: r.severity, verification: 'human_review', enabled: true, justification: `Imported from ${r.source}` }); added++; }
    ui.set({ draft: { markdown, tokens: JSON.stringify(tokens, null, 2), rules } }); toast(`Loaded into your draft: ${docs.length} document${docs.length === 1 ? '' : 's'}, ${added} rules, ${[...useTok].length} tokens. Review, then Save new version.`);
  };
  const pick = async (e: React.ChangeEvent<HTMLInputElement>) => { const fl = e.target.files; if (fl?.length) await run({ files: await readFiles(fl) }); e.target.value = ''; };
  const n = useDocs.size + useRules.size + useTok.size;
  return (
    <Panel id="import-panel" title="Import from your files">
      <p className="mb-3 text-xs text-muted-foreground">Already have a DESIGN.md, a rules file or design tokens? Point at the folder (or choose files) and pick what to bring in. Nothing is saved until you review the draft and press Save new version.</p>
      <div className="flex flex-wrap gap-2"><Input id="import-folder" className="min-w-56 flex-1" value={folder} onChange={(e) => setFolder(e.target.value)} placeholder="/home/you/brand-docs (folder on this computer)" aria-label="Guidelines folder" />
        <Button variant="outline" data-action="scan-folder" disabled={busy || !folder.trim()} onClick={() => run({ folder, project_id: p.id })}>{p.guidelines_folder === folder.trim() && res ? 'Re-scan' : 'Scan folder'}</Button>
        <label className="inline-flex h-8.5 cursor-pointer items-center rounded-lg border bg-background px-3 text-sm font-medium sm:h-7.5">Choose files…<input id="import-files" type="file" multiple accept=".md,.markdown,.json,.css" hidden onChange={pick} /></label>
        <label className="inline-flex h-8.5 cursor-pointer items-center rounded-lg border bg-background px-3 text-sm font-medium max-sm:hidden sm:h-7.5">Choose folder…<input id="import-dir" type="file" hidden onChange={pick} {...({ webkitdirectory: '', directory: '' } as any)} /></label></div>
      {res && <div className="mt-4" id="import-result">
        {res.docs.length > 0 && <><h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Guidelines text (DESIGN.md)</h3>
          {res.docs.map((d: any) => <label key={d.file} className="my-1 flex items-center gap-2 text-sm font-normal"><input type="checkbox" className="size-4" checked={useDocs.has(d.file)} onChange={(e) => toggle(useDocs, d.file, e.target.checked, setUseDocs)} /><span className="font-mono text-xs">{d.file}</span><span className="text-muted-foreground">· {d.title} · {d.chars} chars{d.rule_count ? ` · ${d.rule_count} rule-like lines` : ''}</span></label>)}</>}
        {res.rules.length > 0 && <><h3 className="mb-1 mt-4 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Rules ({useRules.size}/{res.rules.length}) <button className="font-normal normal-case underline" type="button" onClick={() => setUseRules(new Set(useRules.size ? [] : res.rules.map((r: any) => r.n)))}>{useRules.size ? 'none' : 'all'}</button></h3>
          <div className="max-h-56 overflow-auto rounded-md border p-2">{res.rules.map((r: any) => <label key={r.n} className="my-1 flex items-start gap-2 text-[13px] font-normal"><input type="checkbox" className="mt-1 size-4" checked={useRules.has(r.n)} onChange={(e) => toggle(useRules, r.n, e.target.checked, setUseRules)} /><span><Tag>{r.id || 'auto ID'}</Tag> {r.description}<small className="block text-[11px] text-muted-foreground">{r.source} · {r.severity}</small></span></label>)}</div></>}
        {res.tokens.length > 0 && <><h3 className="mb-1 mt-4 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Tokens ({useTok.size}/{res.tokens.length})</h3>
          <div className="max-h-44 overflow-auto rounded-md border p-2">{res.tokens.map((t: any) => <label key={t.name} className="my-1 flex items-center gap-2 text-[13px] font-normal"><input type="checkbox" className="size-4" checked={useTok.has(t.name)} onChange={(e) => toggle(useTok, t.name, e.target.checked, setUseTok)} />{/^#[0-9a-f]{3,8}$/i.test(t.value) && <span className="size-4 rounded border" style={{ background: t.value }} />}<span>{t.name}</span><span className="font-mono text-xs text-muted-foreground">{t.value}</span><span className="ml-auto text-[11px] text-muted-foreground">{t.source}</span></label>)}</div></>}
        {res.skipped.length > 0 && <p className="mt-3 text-xs text-muted-foreground">Skipped: {res.skipped.join('; ')}</p>}
        {(res.docs.length > 0 || res.rules.length > 0 || res.tokens.length > 0) && <div className="mt-4 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm font-normal"><input type="radio" name="imp-mode" className="size-4" checked={!replace} onChange={() => setReplace(false)} /> Add to my draft</label>
          <label className="flex items-center gap-2 text-sm font-normal"><input type="radio" name="imp-mode" className="size-4" checked={replace} onChange={() => setReplace(true)} /> Replace what I picked</label>
          <Button className="primary" data-action="import-apply" disabled={!n} onClick={apply}><Ic name="download" size={13} /> Load into my draft</Button></div>}
      </div>}
    </Panel>
  );
}


/* ---------- guideline profiles ---------- */
export function ProfileBar({ dirty }: { dirty: boolean }) {
  const { p, ctx } = useCurrent(); const profs = profilesOf(p); const active = activeProfileId(p); const cur = ctx?.profile_id || 'main'; const prof = profs.find((x) => x.id === cur) || profs[0];
  const switchTo = (id: string) => { if (dirty) return toast('Save or discard your changes to this profile first'); ui.set({ viewProfile: id, draftFor: '' }); };
  const create = () => openDialog({ title: 'New guidelines profile', submit: 'Create profile', body: <>
    <p className="mb-2 text-xs text-muted-foreground">A profile is its own set of guidelines text, rules and tokens with its own version history. Use one per idea you want to test, then pick profiles when you generate and compare the results.</p>
    <Field label="Name" htmlFor="pf-name"><Input id="pf-name" name="name" required maxLength={40} placeholder="e.g. Looser tone, Strict compliance" /></Field>
    <Field label="Start from" htmlFor="pf-from"><select id="pf-from" name="from" defaultValue={prof.id} className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm">{profs.map((x) => <option key={x.id} value={x.id}>{x.name} (current version)</option>)}<option value="blank">Blank defaults</option></select></Field></>,
  onSubmit: async (f) => { const r = await api('profile-create', { project_id: p.id, name: f.get('name'), copy_from: f.get('from') }); await refresh(); const made = profilesOf(r).at(-1); ui.set({ viewProfile: made.id, draftFor: '' }); toast(`Profile “${made.name}” created. Edit it, then save a version.`); } });
  const rename = () => openDialog({ title: `Rename “${prof.name}”`, submit: 'Rename', body: <Field label="Name" htmlFor="pf-rn"><Input id="pf-rn" name="name" required maxLength={40} defaultValue={prof.name} /></Field>, onSubmit: async (f) => { await api('profile-update', { project_id: p.id, profile_id: prof.id, name: f.get('name') }); await refresh(); } });
  const makeDefault = async () => { try { await api('profile-update', { project_id: p.id, profile_id: prof.id, make_default: true }); await refresh(); toast(`“${prof.name}” is now the default for new runs`); } catch (e: any) { toast(e.message); } };
  const remove = () => confirmDialog(`Delete “${prof.name}”?`, <p>The profile is removed from the list. Variants already generated with it keep their own snapshot and stay on their boards.</p>, 'Delete profile', async () => { await api('profile-delete', { project_id: p.id, profile_id: prof.id }); ui.set({ viewProfile: '', draftFor: '' }); await refresh(); });
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border bg-card p-3" id="profile-bar">
      <span className="text-xs font-medium text-muted-foreground">Profile</span>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Guidelines profile">{profs.map((x) => <Button key={x.id} size="sm" variant={x.id === prof.id ? 'default' : 'outline'} data-profile={x.id} aria-pressed={x.id === prof.id} onClick={() => switchTo(x.id)}>{x.name}{x.id === active ? ' · default' : ''}</Button>)}</div>
      <Button size="sm" variant="ghost" data-action="new-profile" onClick={create}><Ic name="plus" size={13} /> New profile</Button>
      <span className="ml-auto flex flex-wrap gap-1.5"><Button size="xs" variant="outline" onClick={rename}>Rename</Button>{prof.id !== active && <><Button size="xs" variant="outline" data-action="profile-default" onClick={makeDefault}>Make default</Button><Button size="xs" variant="outline" data-action="profile-delete" onClick={remove}>Delete</Button></>}</span>
      {profs.length > 1 && <p className="basis-full text-xs text-muted-foreground">Editing <strong>{prof.name}</strong>. New runs use <strong>{profs.find((x) => x.id === active)?.name}</strong> unless you choose profiles in Generate.</p>}
    </div>
  );
}

/* ---------- profile choice inside the generate dialog ---------- */
export function GenProfiles({ projectId, initial }: { projectId: string; initial?: string }) {
  const data = useData(); const p = data.project.find((x: any) => x.id === projectId); const profs = profilesOf(p); const active = activeProfileId(p); const start = profs.some((x: any) => x.id === initial) ? initial! : active; const [sel, setSel] = useState<string[]>([start]);
  const set = (next: string[]) => { setSel(next); ui.set({ genProfile: next[0] || '' }); };
  useEffect(() => { ui.set({ genProfile: start }); }, [start]);
  if (profs.length < 2) return null;
  return <div className="mb-3 rounded-md border bg-background p-2.5" id="gen-profiles">
    <div className="mb-1 text-xs font-medium">Guidelines profiles · each ticked profile runs every agent</div>
    {profs.map((x: any) => <label key={x.id} className="row flex items-center gap-2 text-sm font-normal"><input type="checkbox" name="profiles" value={x.id} checked={sel.includes(x.id)} className="size-4" onChange={(e) => set(e.target.checked ? [...sel, x.id] : sel.filter((i) => i !== x.id))} /> {x.name}{x.id === active ? <span className="text-xs text-muted-foreground"> · default</span> : null}</label>)}
    {sel.length > 1 && <p className="mt-1 text-xs text-muted-foreground">{sel.length} profiles × your agents = more runs and cost. Compare the results on the board; the rules shown below are for {profs.find((x: any) => x.id === sel[0])?.name}.</p>}
  </div>;
}
void useUi; void isDirty;
