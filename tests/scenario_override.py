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
OVERRIDES=[
 dict(id='CTA-001',description='Experiment: up to three equal-weight paths are allowed',scope='job',severity='info',verification='deterministic',check='primary_action_count',parameters={'max':3},enabled=True,justification='Experiment board: three equal doors are the point'),
 dict(id='TONE-001',description='Experiment: a playful folk-horror storytelling voice is allowed and encouraged',scope='job',severity='info',verification='human_review',enabled=True,justification='Experiment board'),
 dict(id='VISUAL-001',description='Experiment: bold illustration, ornament and an unusual palette are allowed; take colours from the supplied tokens',scope='job',severity='info',verification='human_review',enabled=True,justification='Experiment board')]

# Condition P: STRICT project guidance saved once, and the experiment lives only in the per-job override.
RUN=dict(rules=[dict(id=o['id'],description=o['description'],justification=o['justification'],verification=o['verification'],**{k:o[k] for k in ('check','parameters') if k in o}) for o in OVERRIDES],suspend=[],prose="EXPERIMENT BOARD (this run only): the calm-neutral conventions are suspended for this experiment. Be theatrical, folk-tale, illustrated and ornate; use the woodcut moodboard and the three-doors sketch. Three equal-weight paths at the first step are intended. Still true: explain why each sensitive detail is requested and keep every control reachable by keyboard.")
BRIEF="Design a mortgage application for a hut that walks on chicken legs (Baba Yaga style). Applicants are folk-tale characters. The hut relocates without notice, so address lines are tricky. At the first step offer three ways to continue: 'Fixed foundation', 'Roaming rate' and 'Ask the hut'."
screens=['Eligibility','The hut and you','Review']
board=api('board',dict(project_id=pid,title='Hut experiment (per-job override)',brief=BRIEF,screens=screens,reference_ids=rid))
warn=api('conflict-preview',dict(project_id=pid,brief=BRIEF,reference_ids=rid)); log('conflict preview before generating:',[(w['id'],w['overridden']) for w in warn])
warn2=api('conflict-preview',dict(project_id=pid,brief=BRIEF,reference_ids=rid,overrides=RUN)); log('after override:',[(w['id'],w['overridden']) for w in warn2])
api('generate',dict(project_id=pid,board_id=board['id'],brief=BRIEF,runner_ids=[runners['claude'],runners['codex']],reference_ids=rid,overrides=RUN,idempotency_key='scn-p'))
def done():
    js=[j for j in api('state')['job'] if j['board_id']==board['id'] and j['type']=='generate_board' and not j.get('retried_by')]
    return js if js and all(j['status'] in('succeeded','failed','timed_out') for j in js) else None
t=time.time(); time.sleep(5); js=wait(done,'condition P'); log(f'condition P done {time.time()-t:.0f}s')
st=api('state'); cx=[c for c in st['context'] if c['project_id']==pid]; log('project context versions:',len(cx),'(overrides must not add any)')
out=[]
for j in [x for x in st['job'] if x['board_id']==board['id'] and x['type']=='generate_board']:
    v=next((x for x in st['variant'] if x.get('job_id')==j['id']),None)
    out.append(dict(runner=j['runner_name'],status=j['status'],run_overrides=bool(j['context'].get('run_overrides')),agent_report=j.get('agent_report'),checks={c['check']:c['outcome'] for c in (v or {}).get('validation',[]) if c['outcome'] in('fail','review') } ,variant=(v or {}).get('id')))
json.dump(dict(project=pid,board=board['id'],jobs=out),open('/tmp/scenario-override-result.json','w'),indent=1); log('DONE',pid,board['id'])
