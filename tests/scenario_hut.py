import json, urllib.request, time, base64, sys, re
O='http://localhost:5199/api/'
def api(p,d=None):
    r=urllib.request.Request(O+p,data=json.dumps(d).encode() if d else None,headers={'Content-Type':'application/json'})
    try: return json.load(urllib.request.urlopen(r))
    except urllib.error.HTTPError as e: raise SystemExit(p+': '+e.read().decode())
def log(*a): print(time.strftime('%H:%M:%S'),*a,flush=True)
def wait(pred,what,limit=900):
    end=time.time()+limit
    while time.time()<end:
        x=pred()
        if x: return x
        time.sleep(3)
    raise SystemExit('timeout waiting for '+what)
HUT=__import__('os').path.join(__import__('os').path.dirname(__file__),'..','fixtures','sample-project','references')+'/'
state=api('state'); p=api('project',{'name':'Baba Yaga Estates','description':'Mortgages for houses that walk on chicken legs.'}); pid=p['id']
log('project',pid)
STRICT_MD="""# Baba Yaga Estates: brand guidelines

Tone: calm, neutral, professional financial services. No humour, whimsy or folk-tale language.
Visual: neutral palette with one accent, generous whitespace, system fonts, no illustrations.
Use clear titles and short descriptive copy.
Explain why each sensitive detail is requested.
One obvious primary action per screen.
"""
STRICT_TOKENS={'accent':'#52614c','ink':'#202b24','background':'#f7f8f5','radius':'8px','spacing':'24px','font':'system-ui, sans-serif'}
base_rules=[
 dict(id='CTA-001',description='One primary action per screen',scope='project',severity='error',verification='deterministic',check='primary_action_count',parameters={'max':1},enabled=True),
 dict(id='COMPONENT-001',description='Use the supplied component tokens',scope='workspace',severity='warning',verification='human_review',enabled=True),
 dict(id='COPY-001',description='Explain why sensitive details are requested',scope='project',severity='warning',verification='human_review',enabled=True),
 dict(id='TONE-001',description='Calm, neutral, professional tone. No humour, whimsy or folk-tale language.',scope='project',severity='error',verification='human_review',enabled=True),
 dict(id='VISUAL-001',description='No illustrations or decorative imagery. Neutral palette only.',scope='project',severity='error',verification='human_review',enabled=True)]
OVERRIDES=[
 dict(id='CTA-001',description='Experiment: up to three equal-weight paths are allowed',scope='job',severity='info',verification='deterministic',check='primary_action_count',parameters={'max':3},enabled=True,justification='Experiment board: three equal doors are the point'),
 dict(id='TONE-001',description='Experiment: a playful folk-horror storytelling voice is allowed and encouraged',scope='job',severity='info',verification='human_review',enabled=True,justification='Experiment board'),
 dict(id='VISUAL-001',description='Experiment: bold illustration, ornament and an unusual palette are allowed; take colours from the supplied tokens',scope='job',severity='info',verification='human_review',enabled=True,justification='Experiment board')]
EXP_MD="""# Walking-hut mortgages: EXPERIMENT BOARD

This board is a deliberate experiment. The calm-neutral conventions are suspended: be theatrical, folk-tale, illustrated and ornate.
Still true: explain why each sensitive detail is requested, keep copy readable, and keep every control reachable by keyboard.
Three equal-weight paths at the first step are intended.
"""
EXP_TOKENS={'accent':'#7a1f16','accent2':'#2f5d50','ink':'#1d1110','background':'#f1e3c4','gold':'#c98a2b','radius':'2px','spacing':'24px','font':'Georgia, serif'}
def ctx(md,tokens,rules): return api('context',dict(project_id=pid,markdown=md,tokens=tokens,rules=rules))
c1=ctx(STRICT_MD,STRICT_TOKENS,base_rules); log('context v1 (strict)',c1['version'],c1['hash'][:8])
refs=[]
for f,n,note in [('hut-woodcut-moodboard.png','Woodcut moodboard','Brand mood: woodcut borders, ornate serif, candle-warm palette (red, green, gold). Use as inspiration only when the guidelines allow.'),('hut-three-doors-sketch.png','Three doors sketch','Eligibility offers three equal doors, no single primary button. The hut speaks in its own voice.')]:
    refs.append(api('reference-upload',dict(project_id=pid,name=n,note=note,data=base64.b64encode(open(HUT+f,'rb').read()).decode())))
rid=[r['id'] for r in refs]
runners={}
for a in ('claude','codex'):
    r=api('local-runner',dict(agent=a,model='')); runners[a]=r['id']; log('runner',r['name'],'sandbox=',r.get('sandbox'))
SOURCES=[dict(title='Lore note (supplied by designer)',text='The hut stands on two chicken legs and relocates without notice; the address changes overnight. A fence of bones surrounds it. The occupant must feed the hut or it leaves.',verification='source_supplied_by_user'),
 dict(title='Underwriting note (supplied by designer)',text='Lenders treat unusual collateral (boats, mobile homes, listed buildings) with extra questions about location, upkeep and what happens if the asset moves or is damaged.',verification='source_supplied_by_user')]
rj=api('research',dict(project_id=pid,brief='What do applicants need explained when the asset being mortgaged is unusual or mobile, and how far can a playful voice go before it stops feeling trustworthy?',sources=SOURCES,reference_ids=rid,runner_ids=[runners['claude']],idempotency_key='scn-r'))[0]
log('research job',rj['id']); t=time.time()
job=wait(lambda:(lambda j:j if j['status'] in('succeeded','failed','timed_out') else None)(next(j for j in api('state')['job'] if j['id']==rj['id'])),'research')
log('research',job['status'],f'{time.time()-t:.0f}s')
if job['status']!='succeeded': raise SystemExit(json.dumps(job['events'][-1]))
research=next(r for r in api('state')['research'] if r['job_id']==rj['id']); log('findings',len(research['findings']),[f['verification'] for f in research['findings']])
BRIEF="Design a mortgage application for a hut that walks on chicken legs (Baba Yaga style). Applicants are folk-tale characters. The hut relocates without notice, so address lines are tricky. At the first step offer three ways to continue: 'Fixed foundation', 'Roaming rate' and 'Ask the hut'."
screens=['Eligibility','The hut and you','Review']
made=api('research-board',dict(project_id=pid,research_id=research['id'],finding_ids=[f['id'] for f in research['findings']],title='Hut mortgage journey',brief=BRIEF,screens=screens,runner_ids=[runners['claude'],runners['codex']],reference_ids=rid,idempotency_key='scn-b'))
board=made['board']; log('board',board['id'],'condition S launched (strict context v%s)'%c1['version'])
def variants(n): 
    v=[x for x in api('state')['variant'] if x['board_id']==board['id']]
    return v if len(v)>=n else None
def jobs_done(): 
    js=[j for j in api('state')['job'] if j['board_id']==board['id'] and j['type']=='generate_board' and not j.get('retried_by')]
    return js if js and all(j['status'] in('succeeded','failed','timed_out') for j in js) else None
t=time.time(); wait(jobs_done,'condition S'); log(f'condition S done {time.time()-t:.0f}s')
c2=ctx(STRICT_MD,STRICT_TOKENS,base_rules+OVERRIDES); log('context v2 (rule overrides only)',c2['version'],'overrides:',len(c2['overrides']))
api('generate',dict(project_id=pid,board_id=board['id'],brief=BRIEF,runner_ids=[runners['claude'],runners['codex']],reference_ids=rid,idempotency_key='scn-o'))
t=time.time(); time.sleep(5); wait(jobs_done,'condition O'); log(f'condition O done {time.time()-t:.0f}s')
c3=ctx(EXP_MD,EXP_TOKENS,base_rules+OVERRIDES); log('context v3 (overrides + experiment prose + tokens)',c3['version'])
api('generate',dict(project_id=pid,board_id=board['id'],brief=BRIEF,runner_ids=[runners['claude'],runners['codex']],reference_ids=rid,idempotency_key='scn-e'))
t=time.time(); time.sleep(5); wait(jobs_done,'condition E'); log(f'condition E done {time.time()-t:.0f}s')
st=api('state'); out=[]
for v in sorted([x for x in st['variant'] if x['board_id']==board['id']],key=lambda x:x['created_at']):
    ctxv=next(c for c in st['context'] if c['id']==v['context_id'])
    out.append(dict(variant=v['id'],runner=v['runner_name'],context_version=ctxv['version'],validation={c['check']:c['outcome'] for c in v['validation'] if c['outcome'] in('fail','pass') and ('Primary' in c['check'])},fails=[(c['check'],c['evidence']) for c in v['validation'] if c['outcome']=='fail'],anchors=v.get('anchors_added')))
json.dump(dict(project=pid,board=board['id'],variants=out),open('/tmp/scenario-result.json','w'),indent=1)
log('DONE',pid,board['id'])
