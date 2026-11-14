import { useEffect } from 'react';
import { useCurrent, Link } from '@/lib/router';
import { useUi, ui, contextsOf, ensureDraft, isDirty, effectiveOf, tokenState, ctxVersion, refresh, api } from '@/lib/store';
import { renderMarkdown, contextDiff, diffSummary, diffIsEmpty, fmtTime, fmtHash } from '@/lib/format';
import { Heading } from '@/components/app/chrome';
import { Tag, Panel, Content, Note, toast } from '@/components/app/feedback';
import { Ic } from '@/components/app/icons';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { OverrideList, ruleModal, saveDraft } from '@/actions';
import { ImportPanel } from '@/tools';
import { cn } from '@/lib/utils';

function DiffBlock({ d }: { d: any }) {
  if (d.initial) return <p className="text-xs text-muted-foreground">Initial version.</p>;
  if (diffIsEmpty(d)) return <p className="text-xs text-muted-foreground">No content changes.</p>;
  const list = (label: string, arr: string[], cls: string) => arr.length ? <div key={label} className={cn('diff my-1 text-[13px]', cls)}><strong>{label}</strong> {arr.map((x) => <span key={x} className="mr-2 rounded bg-muted px-1.5 py-0.5 text-xs">{x}</span>)}</div> : null;
  return <>{list('+ Guideline lines', d.markdown.added, 'add')}{list('− Guideline lines', d.markdown.removed, 'del')}{list('+ Tokens', d.tokens.added, 'add')}{list('~ Tokens', d.tokens.changed, 'chg')}{list('− Tokens', d.tokens.removed, 'del')}{list('+ Rules', d.rules.added, 'add')}{list('~ Rules', d.rules.changed, 'chg')}{list('− Rules', d.rules.removed, 'del')}</>;
}
const th = 'px-2.5 py-2 text-left text-xs font-medium text-muted-foreground'; const td = 'px-2.5 py-2 align-top';

export function ContextView() {
  const { p, ctx } = useCurrent(); const s = useUi((x) => x);
  useEffect(() => { if (ctx) ensureDraft(ctx); }, [ctx?.id, s.draftFor]);
  if (!ctx || !s.draft || s.draftFor !== ctx.id) return <Heading title="Design context" sub="The shared source of truth for every agent, every variation, every revision." />;
  const d = s.draft; const dirty = isDirty(ctx, s); const versions = contextsOf(p.id); const tok = tokenState(d.tokens); const eff = effectiveOf(d.rules);
  const setDraft = (patch: Partial<typeof d>) => ui.set({ draft: { ...d, ...patch } });
  const quickAdd = () => {
    const el = document.getElementById('quick-rules') as HTMLTextAreaElement; const lines = el.value.split('\n').map((x) => x.trim()).filter(Boolean); if (!lines.length) return toast('Enter at least one instruction');
    let n = Math.max(0, ...d.rules.map((r: any) => +(/^GUIDANCE-(\d+)$/.exec(r.id)?.[1] || 0))); const add = lines.map((description) => ({ id: 'GUIDANCE-' + String(++n).padStart(3, '0'), description, scope: 'project', severity: 'warning', verification: 'human_review', enabled: true }));
    setDraft({ rules: [...d.rules, ...add] }); el.value = '';
  };
  const applyJson = () => { let rules; try { rules = JSON.parse((document.getElementById('rules-json') as HTMLTextAreaElement).value); if (!Array.isArray(rules)) throw 0; } catch { return toast('Rules JSON must be a valid array'); } setDraft({ rules }); };
  const save = async () => { try { const c = await saveDraft(); toast('Saved context version ' + (c.version || '')); } catch (e: any) { toast(e.message); } };
  return (
    <>
      <Heading title="Design context" sub="The shared source of truth for every agent, every variation, every revision." />
      <Content>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><span id="dirty-badge" className={cn('badge inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium', dirty ? 'warn bg-warning/10 text-warning-foreground' : 'success bg-success/10 text-success-foreground')}>{dirty ? 'Unsaved changes' : 'Saved · version ' + (ctx.version || versions.length)}</span>
          <div className="flex gap-2"><Button variant="outline" data-action="discard-draft" disabled={!dirty} onClick={() => ui.set({ draftFor: '' })}>Discard changes</Button><Button className="primary" data-action="save-context" disabled={!dirty || !!tok.err} onClick={save}>Save new version</Button></div></div>
        <ImportPanel />
        <Note>Every job snapshots the <em>saved</em> version, never unsaved edits. New guidance affects new variations; existing images keep their original context. Template fixtures apply tokens and simple colour directives only; select a local coding agent for broader guidance.</Note>
        <Panel title={<>Brand guidelines <Tag>DESIGN.md</Tag></>}><div className="grid gap-5 md:grid-cols-2"><div><label className="mb-1.5 block text-xs font-medium" htmlFor="guidelines">Edit</label><Textarea id="guidelines" rows={12} data-draft="markdown" value={d.markdown} onChange={(e) => setDraft({ markdown: e.target.value })} /></div><div><span className="label mb-1.5 block text-xs font-medium">Preview</span><div className="md min-h-40 rounded-lg border bg-muted/30 p-4" id="md-preview" dangerouslySetInnerHTML={{ __html: renderMarkdown(d.markdown) }} /></div></div></Panel>
        <Panel id="tokens" title="Design tokens" action={<label className="button-like inline-flex h-8 cursor-pointer items-center gap-2 rounded-lg border bg-background px-3 text-sm font-medium"><Ic name="download" size={13} /> Import JSON<input type="file" id="token-file" accept=".json,application/json" hidden onChange={async (e) => { try { const f = e.target.files?.[0]; if (!f) return; if (f.size > 200000) throw Error('Token file is too large'); setDraft({ tokens: JSON.stringify(JSON.parse(await f.text()), null, 2) }); } catch (er: any) { toast(er.message); } e.target.value = ''; }} /></label>}>
          <div className="grid gap-5 md:grid-cols-2"><div><label className="mb-1.5 block text-xs font-medium" htmlFor="tokens-json">tokens.json (flat object)</label><Textarea id="tokens-json" rows={10} data-draft="tokens" className="font-mono" value={d.tokens} onChange={(e) => setDraft({ tokens: e.target.value })} /><p className="error-text mt-1.5 text-xs text-destructive-foreground" id="token-err" role="alert">{tok.err}</p></div>
            <div id="token-table">{tok.tokens ? <table className="table w-full text-[13px]"><thead><tr><th className={th}>Token</th><th className={th}>Value</th></tr></thead><tbody>{Object.entries(tok.tokens).map(([k, v]) => <tr key={k} className="border-t"><td className={td}>{k}</td><td className={td}>{/^#[0-9a-f]{3,8}$/i.test(String(v)) ? <span className="swatch mr-2 inline-block size-3.5 rounded border align-middle" style={{ background: String(v) }} /> : null}<span className="font-mono text-xs">{String(v)}</span></td></tr>)}</tbody></table> : <p className="text-muted-foreground">Fix the JSON to see the token table.</p>}</div></div>
        </Panel>
        <Panel id="rules" title="Rules" action={<Button variant="outline" size="sm" data-action="add-rule" onClick={() => ruleModal()}><Ic name="plus" size={13} /> Add rule</Button>}>
          <p className="mb-3 text-muted-foreground">Rule IDs are stable and versioned: saving a changed rule increments its version.</p>
          <div className="overflow-x-auto"><table className="table rules w-full text-[13px]"><thead><tr><th className={th} /><th className={th}>Rule</th><th className={th}>Scope</th><th className={th}>Severity</th><th className={th}>Verification</th><th className={th}>Description</th><th className={th} /></tr></thead><tbody>
            {d.rules.map((r: any, i: number) => <tr key={i} className="border-t"><td className={td}><input type="checkbox" data-rule-toggle={i} checked={r.enabled !== false} aria-label={`Enable ${r.id}`} onChange={(e) => { const rules = d.rules.map((x: any, j: number) => j === i ? { ...x, enabled: e.target.checked } : x); setDraft({ rules }); }} /></td><td className={td}><strong>{r.id}</strong> <span className="text-xs text-muted-foreground">v{r.version || 'new'}</span></td><td className={td}><Tag>{r.scope || 'project'}</Tag></td><td className={td}>{r.severity || 'warning'}</td><td className={td}>{r.verification}</td><td className={td}>{r.description}{r.check ? <div className="text-xs text-muted-foreground">check: {r.check} {r.parameters ? JSON.stringify(r.parameters) : ''}</div> : null}</td><td className={cn(td, 'whitespace-nowrap text-right')}><Button variant="ghost" size="icon-xs" data-rule-edit={i} aria-label={`Edit ${r.id}`} onClick={() => ruleModal(i)}><Ic name="edit" size={13} /></Button><Button variant="ghost" size="icon-xs" data-rule-delete={i} aria-label={`Delete ${r.id}`} onClick={() => setDraft({ rules: d.rules.filter((_: any, j: number) => j !== i) })}><Ic name="trash" size={13} /></Button></td></tr>)}
            {!d.rules.length && <tr><td colSpan={7} className="p-3 text-muted-foreground">No rules yet.</td></tr>}</tbody></table></div>
          <label className="mb-1.5 mt-4 block text-xs font-medium" htmlFor="quick-rules">Quick add · one plain-language instruction per line (stored as human-review rules with stable GUIDANCE-nnn IDs)</label><Textarea id="quick-rules" rows={2} placeholder="Use pink text" /><Button variant="outline" size="sm" className="mt-2" data-action="quick-rules" onClick={quickAdd}><Ic name="plus" size={13} /> Add instructions as rules</Button>
          <details className="mt-3.5"><summary className="cursor-pointer text-xs text-muted-foreground">Advanced · edit rules as JSON</summary><Textarea id="rules-json" rows={8} className="mt-2 font-mono" key={JSON.stringify(d.rules)} defaultValue={JSON.stringify(d.rules.map((r: any) => ({ ...r, version: undefined })), null, 2)} /><Button variant="outline" size="sm" className="mt-2" data-action="apply-rules-json" onClick={applyJson}>Apply JSON to draft</Button></details>
        </Panel>
        <Panel id="effective" title="Effective context"><p className="mb-2 text-muted-foreground">Workspace defaults → project overrides → job overrides. Rules merge by stable ID; the most specific scope wins{dirty ? ' (shown for your unsaved draft)' : ''}.</p>{eff.overrides.length ? <OverrideList overrides={eff.overrides} /> : <p>No rule conflicts in this version.</p>}
          <table className="table mt-3 w-full text-[13px]"><thead><tr><th className={th}>Rule</th><th className={th}>Winning scope</th><th className={th}>Verification</th></tr></thead><tbody>{eff.rules.map((r: any) => <tr key={r.id + r.scope} className="border-t"><td className={td}>{r.id}</td><td className={td}>{r.scope || 'project'}</td><td className={td}>{r.verification}</td></tr>)}</tbody></table><div className="detail-json mt-3 break-all font-mono text-[11px] text-muted-foreground">Saved snapshot SHA-256 {ctx.hash}</div></Panel>
        <Panel id="versions" title="Version history">{versions.slice().reverse().map((c, i, arr) => { const prev = arr[i + 1]; const diff = contextDiff(prev, c); return (
          <details key={c.id} className="version border-b py-2 last:border-0"><summary className="cursor-pointer text-[13px]"><strong>v{c.version || versions.indexOf(c) + 1}</strong> · {fmtTime(c.created_at)} · <span className="font-mono">{fmtHash(c.hash)}</span> · {diffSummary(diff)}{c.id === ctx.id ? <> <Tag kind="success">Current</Tag></> : null}</summary>
            <div className="py-2"><DiffBlock d={diff} />{c.id !== ctx.id && <Button variant="outline" size="sm" className="mt-2" data-load-version={c.id} onClick={() => { ui.set({ draft: { markdown: c.markdown, tokens: JSON.stringify(c.tokens, null, 2), rules: structuredClone(c.rules) }, draftFor: ctx.id }); toast(`Loaded v${c.version} into the editor. Save to create a new version.`); window.scrollTo(0, 0); document.getElementById('main')?.scrollTo(0, 0); }}>Load into editor (saves as a new version)</Button>}</div></details>); })}</Panel>
      </Content>
    </>
  );
}
void Link; void ctxVersion; void refresh; void api;
