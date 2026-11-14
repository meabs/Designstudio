import type { ReactNode } from 'react';
import { useCurrent, boardPath, Link, navigate } from '@/lib/router';
import { profilesOf, profileOfVariant, useData, useUi, ui, checksOf, variantStatus, ctxVersion, jobRefUrl, api } from '@/lib/store';
import { fmtHash } from '@/lib/format';
import { Tabs, TabsList, TabsTab } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Ic } from '@/components/app/icons';
import { Tag, toast } from '@/components/app/feedback';
import { runAction, openRef, pinEdit, pinDelete, acceptRevision, revertRevision, blindPick, OverrideList } from '@/actions';
import { ProfileTag, AuditTab, RuleBreaks, styleModal, statesModal, setAsideModal, twinLink } from '@/tools';
import { refresh } from '@/lib/store';
import { cn } from '@/lib/utils';

const OUTCOME: Record<string, string> = { pass: 'Passed deterministic checks', fail: 'Failed deterministic checks', not_assessable: 'Not assessable (missing instrumentation)', review: 'Needs designer review' };
const Block = ({ title, children, className }: { title?: string; children: ReactNode; className?: string }) => <div className={cn('inspect-block border-b px-4 py-3.5', className)}>{title && <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>}{children}</div>;
const Prop = ({ k, children }: { k: string; children: ReactNode }) => <div className="prop flex h-7 items-center justify-between text-[13px] text-muted-foreground"><span>{k}</span><span className="text-foreground">{children}</span></div>;

function ReviewControls({ x, v }: { x: any; v: any }) {
  const d = x.review?.decision;
  const set = async (decision: string) => { try { await api('review-check', { variant_id: v.id, index: Number(x.index), decision }); await refresh(); } catch (e: any) { toast(e.message); } };
  return <div className="review-actions mt-1.5 flex flex-wrap items-center gap-2" role="group" aria-label="Designer review">{d === 'accepted' ? <Tag kind="success">Reviewed · OK</Tag> : d === 'needs_change' ? <Tag kind="fail">Needs change</Tag> : <Tag kind="warn">Not yet reviewed</Tag>}<Button size="xs" variant="outline" data-review-check={x.index} data-decision="accepted" disabled={d === 'accepted'} onClick={() => set('accepted')}>Mark OK</Button><Button size="xs" variant="outline" data-review-check={x.index} data-decision="needs_change" disabled={d === 'needs_change'} onClick={() => set('needs_change')}>Needs change</Button></div>;
}

export function Inspector() {
  const { r, v, ctx, b } = useCurrent(); const data = useData(); const s = useUi((x) => x);
  const shell = 'inspector overflow-auto border-t bg-background lg:border-l lg:border-t-0';
  if (!v || !b) return <aside className={shell}><div className="inspector-title border-b px-4 py-3 text-sm font-semibold">Design</div><Block title="Nothing selected"><p className="text-xs text-muted-foreground">Select a frame to see its properties, checks and comments.</p></Block><Block title="Shared design context"><p className="text-xs text-muted-foreground">{ctx?.effective_rules.length || 0} effective rules<br />{Object.keys(ctx?.tokens || {}).length} design tokens<br />Immutable context snapshot</p></Block></aside>;
  const annotations = data.annotation.filter((a) => a.variant_id === v.id); const open = annotations.filter((a) => a.status !== 'applied'); const chosen = open.filter((a) => a.selected !== false);
  const parent = data.variant.find((x) => x.id === v.parent_id); const children = data.variant.filter((x) => x.parent_id === v.id); const [label, kind] = variantStatus(v); const checks = checksOf(v);
  const vctx = data.context.find((c) => c.id === v.context_id) || ctx; const failed = checks.filter((c: any) => c.outcome === 'fail').length; const tab = s.inspTab; const screenTitle = b.screens[Number(s.screen)];
  const colors = Object.entries(v.applied_tokens || vctx?.tokens || {}).filter(([, val]) => /^#[0-9a-f]{3,8}$/i.test(String(val)));
  const twin = twinLink(v); const job = data.job.find((j) => j.id === v.job_id); const ro = job?.context?.run_overrides; const rep = job?.agent_report;

  const design = <>
    <Block><div className="insp-layer mb-2 flex items-center gap-2.5"><Ic name="frame" size={14} /><div><strong className="text-sm">{screenTitle}</strong><div className="text-xs text-muted-foreground">{v.runner_name} · v{v.version}</div></div></div><Tag kind={kind}>{label}</Tag></Block>
    <Block title="Frame"><Prop k="Width">720</Prop><Prop k="Height">960</Prop><Prop k="Version">v{v.version}</Prop>{profilesOf(data.project.find((x) => x.id === v.project_id)).length > 1 && !(b.blind && !b.revealed) && <Prop k="Profile">{profileOfVariant(v, data).name}</Prop>}<Prop k="Context"><span className="font-mono text-xs">v{ctxVersion(vctx)} · {fmtHash(vctx?.hash)}</span></Prop></Block>
    {colors.length > 0 && <Block title={`Fill · tokens${v.applied_tokens ? ' applied' : ''}`}>{colors.map(([k, val]) => <div key={k} className="fillrow flex h-7 items-center gap-2 text-[13px]"><span className="swatch size-3.5 rounded border" style={{ background: String(val) }} /><span>{k}</span><span className="ml-auto font-mono text-xs text-muted-foreground">{String(val).toUpperCase()}</span></div>)}</Block>}
    {(v.references || []).length > 0 && <Block title="Reference images"><div className="refstrip mb-2 flex flex-wrap gap-2">{v.references.map((x: any) => <button key={x.file} className="refthumb size-10 overflow-hidden rounded-md border p-0" data-ref-open={`${v.job_id}:${x.file}:${x.name}`} title={x.name + (x.note ? ' · ' + x.note : '')} onClick={() => openRef(`${v.job_id}:${x.file}:${x.name}`)}><img src={jobRefUrl(v.job_id, x)} alt={x.name} className="size-full object-cover" /></button>)}</div><p className="text-xs text-muted-foreground">Passed to the agent with the brief. Whether they were applied needs your review.</p></Block>}
    {ro && <Block title="Run-only experiment overrides"><p className="mb-1.5 text-xs text-muted-foreground">Applied to this run only. Not part of the project guidelines.</p>{ro.free && <p className="mb-1.5 text-xs font-medium">Free exploration · {ro.free === 'open' ? 'fully open, no guidelines or rules' : 'rules and checks off, guidelines as inspiration'}</p>}{ro.prose && <p className="text-xs">{ro.prose}</p>}{!ro.free && <OverrideList overrides={job.context.overrides.filter((o: any) => ro.rules.some((x: any) => x.id === o.id) || ro.suspend.includes(o.id))} />}</Block>}
    <RuleBreaks v={v} />
    {rep && <Block title="Agent self-report"><div className="mb-1.5 flex items-center gap-2"><Tag>Unverified</Tag></div><p className="mb-1.5 text-xs text-muted-foreground">What the agent says it did. The studio has not checked this.</p>
      {rep.viewed_references === false ? <p className="text-xs"><strong>Says it did not view the reference images.</strong></p> : rep.viewed_references === true ? <p className="text-xs">Says it viewed the reference images.</p> : null}
      {rep.ignored.length > 0 && <><p className="group-label mt-2 text-xs font-medium">Says it did not follow</p>{rep.ignored.map((l: string, i: number) => <p key={i} className="text-xs">{l}</p>)}</>}
      <details><summary className="cursor-pointer text-xs">Closing message</summary><pre className="whitespace-pre-wrap text-xs">{rep.text}</pre></details></Block>}
    <Block title="Lineage">
      {(v.mix_sources || []).length > 0 && <><p className="mb-2 text-xs text-muted-foreground">Mixed from:</p>{v.mix_sources.map((m: any, i: number) => <Prop key={i} k={b.screens[Number(m.screen)]}>{m.name} v{m.version}</Prop>)}</>}
      {parent ? <Button size="xs" variant="outline" data-parent={parent.id} onClick={() => { ui.set({ selectedVariant: parent.id }); if (r.mode === 'review') navigate(boardPath(r, b, 'review', parent.id), { keepView: true }); }}><Ic name="back" size={12} /> View parent v{parent.version}</Button> : <p className="text-xs text-muted-foreground">{v.kind === 'mix' ? 'Composed from existing versions.' : 'Original generation.'}</p>}
      {children.length > 0 && <div className="mt-2 text-xs text-muted-foreground">Revised in: {children.map((c, i) => <span key={c.id}>{i ? ', ' : ''}<Link className="underline" href={boardPath(r, b, 'review', c.id)}>v{c.version}</Link></span>)}</div>}
      {v.review_state === 'pending' && <div className="decision mt-3 rounded-lg border bg-muted/50 p-3"><p className="mb-2 text-xs">This revision awaits your decision. The parent is untouched either way.</p><div className="flex gap-2"><Button size="sm" className="primary" data-accept={v.id} onClick={() => acceptRevision(v.id).catch((e) => toast(e.message))}><Ic name="check" size={13} /> Accept revision</Button><Button size="sm" variant="outline" data-revert={v.id} onClick={() => revertRevision(v.id)}><Ic name="undo" size={13} /> Revert</Button></div></div>}
    </Block>
    {!(b.blind && !b.revealed) && <Block title="Explore from this version"><div className="flex flex-col gap-2">
      {twin && <Button size="sm" variant="outline" data-action="compare-twin" onClick={() => navigate(boardPath(r, b, 'compare') + `?left=${twin.left}&right=${twin.right}`)}><Ic name="columns" size={13} /> Compare rules vs free</Button>}
      <Button size="sm" variant="outline" data-action="pull-style" onClick={() => styleModal(v)}><Ic name="tokens" size={13} /> Pull style into guidelines</Button>
      <Button size="sm" variant="outline" data-action="add-states" onClick={() => statesModal(v)}><Ic name="layers" size={13} /> Add realistic states</Button>
      {!v.approved && <Button size="sm" variant="outline" data-action="set-aside" onClick={() => setAsideModal(v)}><Ic name="minus" size={13} /> Set aside…</Button>}</div></Block>}
    {v.changes.length > 0 && <Block title="Changes in this version">{v.changes.map((c: string, i: number) => <p key={i} className="text-[13px]">{c}</p>)}</Block>}
  </>;
  const group = (o: string) => { const c = checks.filter((x: any) => x.outcome === o); return c.length ? <div key={o}><p className="group-label mb-1 mt-3 text-xs font-medium">{OUTCOME[o]}</p>{c.map((x: any) => <div key={x.index} className="checkrow my-3 flex items-start gap-2.5 text-[13px]"><span className={cn('check-icon mt-0.5', o, o === 'pass' ? 'text-success-foreground' : o === 'fail' ? 'text-destructive-foreground' : 'text-warning-foreground')}><Ic name={o === 'pass' ? 'check' : o === 'fail' ? 'x' : 'eye'} size={13} /></span><span>{x.check}<small className="mt-0.5 block text-xs text-muted-foreground">{x.evidence}</small>{o === 'review' && <ReviewControls x={x} v={v} />}</span></div>)}</div> : null; };
  const checksTab = <Block><p className="mb-1.5 text-xs text-muted-foreground">Deterministic checks show evidence only. They do not certify accessibility, brand or visual quality.</p>{['pass', 'fail', 'not_assessable', 'review'].map(group)}</Block>;
  const commentsTab = (
    <Block>
      <div className="mb-2 flex items-center justify-between"><h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Comments</h3><Tag>{chosen.length}/{open.length} selected</Tag></div>
      {annotations.map((a, i) => (
        <div key={a.id} className={cn('pinrow mb-2 flex items-start justify-between gap-2 rounded-lg border p-2', s.activePin === a.id && 'focus border-foreground/40 bg-muted/60')}>
          <label className="m-0 flex flex-1 items-start gap-2 text-[13px] font-normal">{a.status === 'applied' ? <span className="chip rounded bg-muted px-1.5 text-xs">{i + 1}</span> : <input type="checkbox" className="mt-1 size-4" data-pin-select={a.id} checked={a.selected !== false} aria-label={`Include pin ${i + 1} in revision`} onChange={async (e) => { try { await api('annotation-update', { id: a.id, selected: e.target.checked }); await refresh(); } catch (er: any) { toast(er.message); } }} />}
            <span className="flex-1"><button type="button" className="linklike text-left hover:underline" data-pin-focus={a.id} data-pin-screen={a.screen} onClick={(e) => { e.preventDefault(); ui.set({ activePin: a.id, screen: a.screen }); if (r.mode !== 'review') navigate(boardPath(r, b, 'review', v.id), { keepView: true }); }}>{a.comment}</button><small className="block text-xs text-muted-foreground">{b.screens[Number(a.screen)]}{a.element_id ? ` · region “${a.element_id}”` : ' · whole screen (no element anchor)'}{a.status === 'applied' ? ' · applied in a revision' : ''}</small></span></label>
          {a.status !== 'applied' && <span className="flex gap-0.5"><Button variant="ghost" size="icon-xs" data-pin-edit={a.id} aria-label={`Edit pin ${i + 1}`} onClick={() => pinEdit(a.id)}><Ic name="edit" size={13} /></Button><Button variant="ghost" size="icon-xs" data-pin-delete={a.id} aria-label={`Delete pin ${i + 1}`} onClick={() => pinDelete(a.id)}><Ic name="trash" size={13} /></Button></span>}
        </div>
      ))}
      {!annotations.length && <p className="text-xs text-muted-foreground">No comments yet. Open Review, pick the comment tool and click a screen.</p>}
      <Button size="xs" variant="outline" data-action="review" onClick={() => runAction('review')}><Ic name="plus" size={12} /> Add comment</Button>
    </Block>
  );
  const anchored = chosen.filter((a) => a.element_id).length;
  return (
    <aside className={cn(shell, 'flex flex-col')}>
      <Tabs value={tab} onValueChange={(t) => ui.set({ inspTab: t as any })} className="gap-0">
        <TabsList variant="underline" className="itabs w-full justify-start px-2" aria-label="Inspector">
          <TabsTab value="design" className="itab">Design</TabsTab>
          <TabsTab value="checks" className="itab">Checks{failed ? <span className="tabcount fail ml-1.5 rounded-full bg-destructive/12 px-1.5 text-[11px] text-destructive-foreground">{failed}</span> : null}</TabsTab>
          <TabsTab value="audit" className="itab">Audit{v.audits?.length ? <span className={cn('tabcount ml-1.5 rounded-full px-1.5 text-[11px]', v.audits.at(-1).counts.fail ? 'fail bg-destructive/12 text-destructive-foreground' : 'bg-muted')}>{v.audits.at(-1).counts.fail || '✓'}</span> : null}</TabsTab>
          <TabsTab value="comments" className="itab">Comments{open.length ? <span className="tabcount ml-1.5 rounded-full bg-muted px-1.5 text-[11px]">{open.length}</span> : null}</TabsTab>
        </TabsList>
      </Tabs>
      <div className="ibody min-h-0 flex-1 overflow-auto" role="tabpanel">{tab === 'checks' ? checksTab : tab === 'comments' ? commentsTab : tab === 'audit' ? <AuditTab v={v} /> : design}</div>
      <div className="inspect-actions flex flex-col gap-2 border-t bg-background p-3">
        {b.blind && !b.revealed && <Button className="primary" data-blind-pick={v.id} onClick={() => blindPick(v.id)}><Ic name="check" size={13} /> I prefer this option</Button>}
        {anchored > 0 && <><label className="scopeopt flex items-center gap-2 text-xs font-normal"><input type="checkbox" data-region-only checked={s.regionOnly} onChange={(e) => ui.set({ regionOnly: e.target.checked })} /> Limit changes to pinned elements</label><span className="scopehelp text-xs text-muted-foreground">{anchored} of {chosen.length} selected pin{chosen.length === 1 ? ' is' : 's are'} element-anchored; {s.regionOnly ? 'the rest revise their whole screen. The studio checks that nothing else changed.' : 'whole screens may change.'}</span></>}
        <Button variant="outline" data-action="revise" disabled={!chosen.length} onClick={() => runAction('revise')}><Ic name="spark" size={13} /> Revise selection ({chosen.length} pin{chosen.length === 1 ? '' : 's'})</Button>
        {v.approved ? <><Button className="primary" data-action="preview" onClick={() => runAction('preview')}><Ic name="play" size={13} /> Open prototype</Button><span className="lockline flex items-center gap-1.5 text-xs text-muted-foreground"><Ic name="lock" size={12} /> Approved and locked. Further changes create new versions.</span></>
          : <><Button className="primary" data-action="approve" onClick={() => runAction('approve')}><Ic name="check" size={13} /> Approve &amp; build prototype</Button><span className="lockline text-xs text-muted-foreground">Approval pins this exact version.</span></>}
      </div>
    </aside>
  );
}
