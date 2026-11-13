from html.parser import HTMLParser
import random, base64, os, json, sqlite3, uuid, hashlib, threading, time, re, html, zipfile, io, subprocess, shlex, shutil
from pathlib import Path
from contextlib import contextmanager
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from local_agents import discover, configuration
ROOT=Path(__file__).resolve().parents[2]
STORE=Path(os.environ.get('STUDIO_STORAGE', ROOT/'storage')); STORE.mkdir(parents=True,exist_ok=True)
LOCK=threading.RLock()
def uid(): return uuid.uuid4().hex[:16]
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'))
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()
@contextmanager
def db():
 c=sqlite3.connect(STORE/'studio.db')
 try:
  c.execute('CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, type TEXT, data TEXT)')
  yield c
  c.commit()
 finally: c.close()
def save(kind,x):
 with LOCK,db() as c: c.execute('INSERT OR REPLACE INTO entities VALUES (?,?,?)',(x['id'],kind,json.dumps(x)))
 return x
def allof(kind):
 with db() as c: return [json.loads(r[0]) for r in c.execute('SELECT data FROM entities WHERE type=?',(kind,))]
def get(id):
 with db() as c: r=c.execute('SELECT data FROM entities WHERE id=?',(id,)).fetchone()
 if not r: raise ValueError('Record not found')
 return json.loads(r[0])
RULES=[dict(id='CTA-001',description='One primary action per screen',scope='project',severity='error',verification='deterministic',check='primary_action_count',parameters={'max':1},enabled=True),dict(id='COMPONENT-001',description='Use the supplied component tokens',scope='workspace',severity='warning',verification='human_review',enabled=True),dict(id='COPY-001',description='Explain why sensitive details are requested',scope='project',severity='warning',verification='human_review',enabled=True)]
GUIDE='# Design guidelines\n\nUse a neutral financial-services style.\nUse clear titles and short descriptive copy.\nExplain why sensitive details are requested.\nOne obvious primary action per screen.\n'
TOKENS={'accent':'#52614c','ink':'#202b24','background':'#f7f8f5','radius':'8px','spacing':'24px','font':'system-ui, sans-serif'}
def context(project,data):
 tokens=data.get('tokens',TOKENS)
 if not isinstance(tokens,dict) or any(not isinstance(v,(str,int,float)) for v in tokens.values()): raise ValueError('Tokens must be a flat JSON object of scalar values')
 all_rules=data.get('rules',RULES)
 if not isinstance(all_rules,list) or any(not isinstance(r,dict) or not str(r.get('id','')).strip() or not str(r.get('description','')).strip() for r in all_rules): raise ValueError('Every rule needs an ID and a description')
 if r_ids:=[r['id'] for r in all_rules if r.get('scope','project')=='project']:
  if len(r_ids)!=len(set(r_ids)): raise ValueError('Duplicate rule IDs within the project scope')
 history=sorted([c for c in allof('context') if c['project_id']==project],key=lambda c:c['created_at'])
 previous=history[-1] if history else None
 prior={r['id']:r for r in (previous or {}).get('rules',[])}
 versioned=[]
 for r in all_rules:
  r=dict(r); old=prior.get(r['id'])
  core=lambda q:{k:v for k,v in q.items() if k!='version'}
  r['version']=1 if not old else (old.get('version',1) if core(old)==core(r) else old.get('version',1)+1)
  versioned.append(r)
 rules={}; overrides=[]
 for scope in ['workspace','project','job']:
  for r in versioned:
   if r.get('scope','project')==scope and r.get('enabled',True):
    if r['id'] in rules: overrides.append({'id':r['id'],'superseded':rules[r['id']],'winner':r,'justification':r.get('justification','More specific scope')})
    rules[r['id']]=r
 x=dict(id=uid(),project_id=project,version=len(history)+1,parent_id=previous['id'] if previous else None,markdown=data.get('markdown',GUIDE),tokens=tokens,rules=versioned,effective_rules=list(rules.values()),overrides=overrides,created_at=time.time())
 x['hash']=digest({k:x[k] for k in ['markdown','tokens','effective_rules']})
 x['content_key']=digest({'markdown':x['markdown'],'tokens':tokens,'rules':[{k:v for k,v in r.items() if k!='version'} for r in versioned]})
 if previous and previous.get('content_key')==x['content_key'] and get(project).get('context_id')==previous['id']: return previous
 save('context',x)
 p=get(project); p['context_id']=x['id']; save('project',p); return x
def project(data):
 p=save('project',dict(id=uid(),name=data.get('name','Untitled project'),description=data.get('description',''),created_at=time.time(),archived=False))
 context(p['id'],{}); return get(p['id'])
def seed():
 if not allof('runner'):
  for label,style in [('Studio A','a'),('Studio B','b')]: save('runner',dict(id=uid(),name=label,type='fixture',style=style))
 if not allof('project'):
  p=project({'name':'Credit Card Application','description':'A clearer path to your next everyday card.'})
  save('board',dict(id=uid(),project_id=p['id'],title='Application Journey',brief='Create a calm, transparent credit card application. Explain eligibility before asking for personal information.',screens=['Eligibility','Your details','Review']))
def safe_path(base,path):
 p=(base/path).resolve()
 if Path(path).is_absolute() or '..' in Path(path).parts or not p.is_relative_to(base.resolve()) or p.is_symlink(): raise ValueError('Unsafe asset path')
 return p

def fixture_tokens(ctx):
 # Deliberately small, explicit fixture vocabulary; not a general language model.
 tokens=dict(ctx['tokens'])
 colors={'pink':'#db2777','red':'#dc2626','blue':'#2563eb','green':'#15803d','purple':'#7c3aed','black':'#111111','white':'#ffffff','orange':'#c2410c'}
 instructions=[ctx.get('markdown','')]+[r.get('description','') for r in ctx.get('effective_rules',[]) if r.get('enabled',True)]
 for text in instructions:
  for match in re.finditer(r'(?:use\s+)?(#[0-9a-f]{6}\b|pink|red|blue|green|purple|black|white|orange)\s+(text|background|buttons?)\b|(?:text|background|buttons?)\s+(?:colou?r\s+)?(?:should\s+be|must\s+be|is|:|=)\s*(#[0-9a-f]{6}\b|pink|red|blue|green|purple|black|white|orange)\b',text,re.I):
   if re.search(r"(?:don't|do not|never|avoid|not)\s+(?:use\s+)?$",text[max(0,match.start()-35):match.start()],re.I): continue
   color,target=(match[1],match[2]) if match[1] else (match[3],match[0].split()[0])
   tokens[{'text':'ink','background':'background','button':'accent','buttons':'accent'}[target.lower()]]=colors.get(color.lower(),color.lower())
 return tokens

def render_screen(title,index,screens,ctx,style,revised=False,comment=''):
 t=fixture_tokens(ctx); esc=html.escape
 css=';'.join('--'+k+':'+str(v).replace('<','').replace('>','') for k,v in t.items())
 nextfile=f'{min(index+1,len(screens)-1)}.html'; previous=f'{max(index-1,0)}.html'
 heading=['A little check.\nA lot of possibility.','Let’s get to know you.','Looking good.\nLet’s make it yours.'][min(index,2)]
 body='<p>Check your eligibility in a few simple steps. It won’t affect your credit score.</p><div class="benefits"><div>✓ &nbsp; A decision in minutes</div><div>✓ &nbsp; No impact on your credit score</div><div>✓ &nbsp; No commitment to apply</div></div>'
 if index==1: body='<p>We ask for these details to confirm your identity. This demo uses fictional information only.</p><label>Full name<input value="Alex Morgan" readonly></label><label>Email address<input value="alex@example.test" readonly></label><label>Annual income<input value="£38,000" readonly></label><button class="text" onclick="document.querySelector(\'#error\').hidden=false">Try a validation state</button><p id="error" hidden role="alert">Enter an annual income to continue. (Demo state)</p>'
 if index>=2: body='<p>Take a moment to check your application before continuing.</p><div class="summary">Full name <b>Alex Morgan</b><hr>Annual income <b>£38,000</b><hr>Card <b>Everyday credit</b></div><a href="1.html">Edit details ↗</a>'
 if revised: body=f'<p class="revision" data-design-id="explanation">{esc(comment)} — Updated explanation: your information is used only for this eligibility check.</p>'+body
 extra='<button data-role="primary-action">Apply now</button>' if style=='b' and index==0 and not revised else ''
 return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>:root{{{css}}}*{{box-sizing:border-box}}body{{margin:0;color:var(--ink,#202b24);background:var(--background,#f7f8f5);font:15px var(--font,system-ui)}}header{{padding:28px 38px;border-bottom:1px solid #dce1d8;display:flex;justify-content:space-between;font-size:12px}}.brand{{font-size:21px;font-weight:700;letter-spacing:-1px}}main{{max-width:600px;padding:40px;margin:auto}}.eyebrow{{color:var(--accent);font-size:11px;letter-spacing:2px;text-transform:uppercase}}h1{{font-size:43px;line-height:1.12;white-space:pre-line;letter-spacing:-1.8px;font-weight:500}}p{{line-height:1.7;color:var(--ink,#677065);opacity:.75}}.benefits{{padding:20px 0;line-height:2.9;font-size:13px}}button,.primary{{display:block;border:0;border-radius:var(--radius,8px);background:var(--accent,#52614c);padding:17px 24px;color:white;text-decoration:none;text-align:center;font:inherit;cursor:pointer;margin-top:16px}}.primary{{width:100%}}a{{color:var(--accent)}}label{{display:block;font-size:12px;margin:20px 0}}input{{width:100%;padding:14px;border:1px solid #d5dbd1;border-radius:6px;background:white;margin-top:8px;font:inherit}}details{{font-size:12px;margin:22px 0;color:var(--ink,#677065)}}.text{{background:none;color:var(--accent);padding:0;font-size:12px}}.summary{{background:white;padding:24px;line-height:2.5;font-size:13px}}.summary b{{float:right}}hr{{border:0;border-top:1px solid #e7e9e4}}footer{{text-align:center;font-size:10px;color:#859080;padding:24px}}.revision{{border-left:2px solid var(--accent);padding-left:12px}}{ 'main{max-width:620px;background:white;margin:28px auto;border:1px solid #e1e5df;border-radius:12px}h1{font-size:36px}.benefits{background:#f2f5ef;padding:16px;border-radius:8px}' if style=='b' else ''}</style><header><span class="brand">north<span style="color:var(--accent)">.</span></span><span>EVERYDAY CREDIT &nbsp; / &nbsp; {index+1:02d}</span></header><main><div class="eyebrow">{esc(title)} · Step {index+1} of {len(screens)}</div><h1 data-design-id="heading">{esc(heading)}</h1>{body}<details><summary>Why do we ask for this?</summary>We use this information to show suitable options. No real application is submitted.</details><a class="primary" data-role="primary-action" data-design-id="continue" href="{nextfile}">{'Continue' if index<len(screens)-1 else 'Finish demo'} &nbsp; →</a>{extra}{f'<p><a href="{previous}">← Back</a></p>' if index else ''}</main><footer>Illustrative prototype only · No application will be submitted</footer></html>'''

ALLOWED_OUTPUT={'.html','.css','.js','.json','.png','.jpg','.jpeg','.svg','.woff','.woff2','.txt','.md'}
# ---- HTML regions: locate elements by data-design-id, diff revisions per element ----
VOID_TAGS={'area','base','br','col','embed','hr','img','input','link','meta','source','track','wbr'}
def element_spans(html_text):
 # {design_id: (start, end)} character offsets of each element's outerHTML.
 starts=[0]+[m.end() for m in re.finditer('\n',html_text)]
 off=lambda pos: starts[pos[0]-1]+pos[1]
 class P(HTMLParser):
  def __init__(self): super().__init__(convert_charrefs=False); self.stack=[]; self.spans={}
  def handle_starttag(self,tag,attrs):
   start=off(self.getpos()); did=dict(attrs).get('data-design-id')
   if tag in VOID_TAGS:
    if did: self.spans.setdefault(did,(start,start+len(self.get_starttag_text())))
    return
   self.stack.append((tag,did,start))
  def handle_endtag(self,tag):
   for i in range(len(self.stack)-1,-1,-1):
    if self.stack[i][0]==tag:
     _,did,start=self.stack[i]; end=html_text.find('>',off(self.getpos()))+1
     if did: self.spans.setdefault(did,(start,end))
     del self.stack[i:]; break
 p=P(); p.feed(html_text); p.close(); return p.spans
def _masked(text,spans,inside=None):
 # Replace nested identified elements by placeholders so a change is attributed to the innermost element that really differs.
 lo,hi=(inside if inside else (0,len(text))); items=sorted(((a,b,i) for i,(a,b) in spans.items() if lo<=a and b<=hi and (a,b)!=(lo,hi)))
 out=[]; pos=lo
 for a,b,i in items:
  if a<pos: continue
  out.append(text[pos:a]); out.append(f'\u27e6{i}\u27e7'); pos=b
 out.append(text[pos:hi]); return re.sub(r'\s+',' ',''.join(out)).strip()
def diff_regions(before,after):
 # {'elements': ids whose own content changed, 'outside': content changed outside any identified element}
 sb,sa=element_spans(before),element_spans(after); changed=[]
 for i in sorted(set(sb)|set(sa)):
  if i not in sb or i not in sa or _masked(before,sb,sb[i])!=_masked(after,sa,sa[i]): changed.append(i)
 return {'elements':changed,'outside':_masked(before,sb)!=_masked(after,sa)}
def region_revise(html_text,notes):
 # Fixture behaviour: edit only the targeted elements (append a visible revision note inside each).
 for did,comment in notes.items():
  spans=element_spans(html_text)
  if did not in spans: return None
  a,b=spans[did]; seg=html_text[a:b]; close=seg.rfind('</')
  if close<0: return None
  html_text=html_text[:a]+seg[:close]+f' <small class="revision-note" data-revised="{html.escape(did)}">· {html.escape(comment)}</small>'+seg[close:]+html_text[b:]
 return html_text
def hidden_job_file(path):
 # While a board is blind, files that reveal the runner (envelope, runner log, raw agent output) are withheld; the task text and references are identical for every runner.
 m=re.match(r'/assets/jobs/([0-9a-f]+)/(.*)$',path)
 if not m: return False
 try: j=get(m.group(1)); b=get(j['board_id']) if j.get('board_id') else None
 except ValueError: return False
 return bool(b and b.get('blind') and not b.get('revealed') and not (m.group(2)=='TASK.md' or m.group(2).startswith('references/')))
def stamp_anchors(html_text):
 # Adds data-design-id to common elements when an agent emitted none, so pins can target elements. Returns (html, count).
 if 'data-design-id' in html_text: return html_text,0
 tags={'h1','h2','h3','h4','h5','h6','p','a','button','label','input','select','textarea','img','form','section','article','header','footer','main','nav','aside','ul','ol','li','table','figure','details','summary'}
 starts=[0]+[m.end() for m in re.finditer('\n',html_text)]; spots=[]; counts={}
 class P(HTMLParser):
  def handle_starttag(self,tag,attrs):
   if tag not in tags: return
   text=self.get_starttag_text(); line,col=self.getpos(); a=starts[line-1]+col; end=a+len(text)-1
   if text.endswith('/>'): end-=1
   counts[tag]=counts.get(tag,0)+1; spots.append((end,f' data-design-id="auto-{tag}-{counts[tag]}"'))
 P(convert_charrefs=False).feed(html_text)
 for pos,attr in sorted(spots,reverse=True): html_text=html_text[:pos]+attr+html_text[pos:]
 return html_text,len(spots)
MAX_PACKAGE_FILES=200; MAX_PACKAGE_BYTES=20_000_000
EXTERNAL_PATTERNS=[(r'(?:src|href|action|poster|data)\s*=\s*["\']?\s*(?:https?:)?//','external URL in an attribute'),(r'url\(\s*["\']?\s*(?:https?:)?//','external URL in CSS url()'),(r'@import\b','CSS @import'),
 (r'\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(',"network call"),(r'sendBeacon\s*\(','network call (sendBeacon)'),(r'\bimport\s*\(|\bimport\s+[^;]*\bfrom\s+["\']',"dynamic or module import"),
 (r'<\s*(?:iframe|object|embed)\b','embedded frame/object'),(r'http-equiv\s*=\s*["\']?refresh[^>]*url\s*=\s*\s*https?:','meta refresh to an external URL'),(r'(?:location\s*(?:\.href)?\s*=|window\.open\s*\()\s*["\']https?:','navigation to an external URL')]
def check_manifest(m):
 # Minimal structural check of variant-package/1.0 (stdlib only; mirrors contracts/schemas/variant-package.schema.json).
 if not isinstance(m,dict): raise ValueError('Manifest must be a JSON object')
 if m.get('schema_version')!='1.0' or m.get('kind')!='clickthrough-static': raise ValueError('Invalid manifest contract: need schema_version "1.0" and kind "clickthrough-static"')
 screens=m.get('screens')
 if not isinstance(screens,list) or not screens: raise ValueError('Manifest needs a non-empty screens list')
 ids=[]
 for sc in screens:
  if not isinstance(sc,dict) or not all(isinstance(sc.get(k),str) and sc.get(k) for k in ('id','title','file')): raise ValueError('Every screen needs string id, title and file')
  if not isinstance(sc.get('states',[]),list): raise ValueError('Screen states must be a list')
  ids.append(sc['id'])
 if len(ids)!=len(set(ids)): raise ValueError('Duplicate screen IDs in manifest')
 if m.get('start_screen_id') not in ids: raise ValueError('start_screen_id must name a screen')
 if not isinstance(m.get('edges',[]),list) or any(not isinstance(e,dict) or e.get('from') not in ids or e.get('to') not in ids for e in m.get('edges',[])): raise ValueError('Invalid navigation edge')
def scan_package(folder):
 files=[f for f in folder.rglob('*') if f.is_file() or f.is_symlink()]
 if len(files)>MAX_PACKAGE_FILES: raise ValueError(f'Package has too many files (limit {MAX_PACKAGE_FILES})')
 if sum(f.stat().st_size for f in files if f.is_file() and not f.is_symlink())>MAX_PACKAGE_BYTES: raise ValueError('Package is too large')
 for f in files:
  if f.is_symlink(): raise ValueError('Symlinks are not allowed in packages')
  if f.suffix.lower() in ('.html','.css','.js'):
   text=f.read_text(errors='replace')
   for pattern,label in EXTERNAL_PATTERNS:
    if re.search(pattern,text,re.I): raise ValueError(f'Not allowed in {f.relative_to(folder)}: {label}')
def token_refs(folder,tokens):
 # var(--x) with no fallback must be declared in the package or provided by the token set.
 declared=set('--'+k for k in (tokens or {})); used={}
 for f in folder.rglob('*'):
  if f.is_file() and f.suffix.lower() in ('.html','.css'):
   text=f.read_text(errors='replace'); declared|=set(re.findall(r'(--[\w-]+)\s*:',text))
   for name in re.findall(r'var\(\s*(--[\w-]+)\s*\)',text): used.setdefault(name,f.name)
 return sorted(n for n in used if n not in declared)
def validate(folder,manifest,rules,tokens=None):
 results=[]; check_manifest(manifest); ids={s['id'] for s in manifest['screens']}; scan_package(folder)
 for s in manifest['screens']:
  f=safe_path(folder,s['file']); content=f.read_text(); count=len(re.findall('data-role="primary-action"',content))
  results.append(dict(check='Primary action · '+s['title'],outcome='not_assessable' if not count else ('pass' if count<=next((r.get('parameters',{}).get('max',1) for r in rules if r.get('check')=='primary_action_count'),1) else 'fail'),evidence=f'{count} instrumented primary actions',screen=s['id']))
  root=folder.resolve()
  for link in re.findall(r'(?:href|src)\s*=\s*["\']([^"\']+)["\']',content):
   if link.startswith(('#','data:','mailto:','tel:')): continue
   target=(f.parent/link.split('#')[0].split('?')[0]).resolve()
   if Path(link).is_absolute() or link.startswith('/') or not target.is_relative_to(root): raise ValueError(f'{s["file"]} links outside the package: {link}')
   if not target.is_file(): raise ValueError(f'{s["file"]} links to a missing file: {link}')
  stable=re.findall('data-design-id="([^"]+)"',content)
  results.append(dict(check='Stable targets · '+s['title'],outcome='pass' if stable and len(set(stable))==len(stable) else 'not_assessable',evidence=f'{len(stable)} targets'))
 results.append(dict(check='Package & local navigation',outcome='pass',evidence='Manifest valid; all screen files and declared destinations exist; local links resolved; no external assets, network calls or embedded frames'))
 unresolved=token_refs(folder,tokens)
 results.append(dict(check='Token references',outcome='fail' if unresolved else 'pass',evidence=('Unresolved CSS variables without fallback: '+', '.join(unresolved)) if unresolved else 'All CSS variables resolve to a declared token or custom property'))
 for r in rules:
  if r.get('verification')!='deterministic': results.append(dict(check=r['description'],outcome='review',evidence='Needs designer review; no automated conformance claim'))
 return results

def event(j,status,message):
 j['status']=status; j['events'].append(dict(time=time.time(),message=message)); save('job',j)
CANCEL=set(); MAX_JOBS=max(1,int(os.environ.get('STUDIO_MAX_JOBS','3')))
class Cancelled(Exception): pass
def check_cancel(j):
 if j['id'] in CANCEL: raise Cancelled()
DEFAULT_ENV_ALLOWLIST=['PATH','HOME','USER','LANG','LC_ALL','TERM','TMPDIR','SHELL']
def runner_env(runner):
 return {k:os.environ[k] for k in runner.get('env_allowlist',DEFAULT_ENV_ALLOWLIST) if k in os.environ}
def run_cli(command,out,timeout,j,runner=None):
 # Streams to runner.log so a partial log survives a timeout or cancellation.
 with open(out/'runner.log','w') as log:
  proc=subprocess.Popen(command,cwd=out,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,text=True,env=runner_env(runner or {})); start=time.time()
  while proc.poll() is None:
   if j['id'] in CANCEL: proc.terminate(); proc.wait(); raise Cancelled()
   if time.time()-start>timeout: proc.kill(); proc.wait(); raise subprocess.TimeoutExpired(command,timeout)
   time.sleep(.2)
 return proc.returncode
def execute(j):
 try: check_cancel(j); _execute(j)
 except Cancelled: event(j,'cancelled','Cancelled by designer; no variation was saved')
# ---- durable queue: job state lives in SQLite; this in-memory queue only holds IDs and is rebuilt from the database on start ----
import queue
JOBQ=queue.Queue(); WORKERS=[]
def enqueue(j): JOBQ.put(j['id'])
def claim(jid):
 # Atomically move queued -> running so a cancel and a worker can never both win.
 with LOCK:
  j=get(jid)
  if j['status']!='queued': return None
  if jid in CANCEL: event(j,'cancelled','Cancelled before it started'); return None
  j['status']='running'; save('job',j); return j
def worker():
 while True:
  jid=JOBQ.get()
  if jid is None: JOBQ.task_done(); return
  try:
   j=claim(jid)
   if j: execute(j)
  except Exception: pass
  finally: JOBQ.task_done()
def start_workers(n=None):
 while len(WORKERS)<(n or MAX_JOBS):
  t=threading.Thread(target=worker,daemon=True); t.start(); WORKERS.append(t)
def stop_workers():
 for _ in WORKERS: JOBQ.put(None)
 for t in WORKERS: t.join(10)
 WORKERS.clear()
def recover_jobs():
 # Queued jobs resume in their original order; jobs that were mid-run cannot be trusted, so they fail visibly and can be retried with the same inputs.
 resumed=0
 for j in sorted(allof('job'),key=lambda x:x['created_at']):
  if j['status']=='running': event(j,'failed','Interrupted by a server restart; use Retry to run it again with the same inputs')
  elif j['status']=='queued': j['events'].append(dict(time=time.time(),message='Resumed after server restart')); save('job',j); enqueue(j); resumed+=1
 return resumed
def cancel_job(jid):
 with LOCK:
  j=get(jid)
  if j['status'] not in ['queued','running']: raise ValueError('Only queued or running jobs can be cancelled')
  CANCEL.add(jid)
  if j['status']=='queued': event(j,'cancelled','Cancelled before it started')
def _execute(j):
 folder=None
 try:
  event(j,'running','Runner started with immutable context snapshot'); ctx=j['context']; runner=get(j['runner_id']); out=STORE/'jobs'/j['id']; out.mkdir(parents=True,exist_ok=True)
  (out/'envelope.json').write_text(json.dumps(j,indent=2)); (out/'TASK.md').write_text(j['instruction'])
  if runner['type']=='cli':
   command=[runner['executable']]+[s.replace('{input}',str(out/'envelope.json')).replace('{output}',str(out/'output')).replace('{instruction}',str(out/'TASK.md')).replace('{prompt}',j['instruction']+'\nRead envelope.json for full inputs. Write all deliverables to output/.') for s in runner.get('args',[])]
   (out/'output').mkdir(exist_ok=True)
   if j.get('parent_id'):
    # Revisions start from a copy of the parent version, so the agent edits in place and untouched files stay identical.
    shutil.copytree(STORE/'variants'/j['parent_id'],out/'output',dirs_exist_ok=True,ignore=shutil.ignore_patterns('thumbnails','changes.json'))
   if run_cli(command,out,min(int(runner.get('timeout',120)),600),j,runner): raise ValueError('CLI runner failed; see runner.log in the job history')
  time.sleep(.4); check_cancel(j)
  if j['type']=='research':
   result={'findings':[dict(id=uid(),title=t,detail=d,selected=False,verification='unverified_claim',source_ids=[]) for t,d in [('Explain before you ask','Synthetic fixture: explain the purpose of eligibility questions before requesting information.'),('Make progress visible','Synthetic fixture: a short, predictable journey can help users understand the next step.')]],'sources':j.get('sources',[])}
   if runner['type']=='cli': result=json.loads((out/'output'/'research.json').read_text())
   for finding in result['findings']:
    finding.setdefault('id',uid()); finding.setdefault('selected',False)
    if not finding.get('source_ids'): finding['verification']='unverified_claim'
   # Own ID: entities share one primary key, so reusing the job's ID let the final job save overwrite this record.
   j['research_id']=uid(); save('research',dict(id=j['research_id'],job_id=j['id'],project_id=j['project_id'],brief=j['brief'],created_at=time.time(),**result))
  else:
   board=get(j['board_id']); parent=get(j['parent_id']) if j.get('parent_id') else None
   variant=dict(id=uid(),project_id=j['project_id'],board_id=board['id'],job_id=j['id'],runner_id=runner['id'],runner_name=runner['name'],style=runner.get('style','a'),parent_id=j.get('parent_id'),context_id=ctx['id'],version=parent['version']+1 if parent else 1,approved=False,created_at=time.time(),changes=[])
   folder=STORE/'variants'/variant['id']; (folder/'screens').mkdir(parents=True)
   variant['blind_label']=j.get('blind_label') or (parent or {}).get('blind_label'); variant['review_state']='pending' if parent else None; variant['references']=j.get('references',[])
   manifest=dict(schema_version='1.0',kind='clickthrough-static',board_id=board['id'],start_screen_id='0',screens=[],edges=[])
   annotations=j.get('annotations',[])
   for i,title in enumerate(board['screens']):
    matching=[a for a in annotations if a['screen']==str(i)]
    sc=(j.get('scope') or {}).get(str(i),{}); parent_html=(STORE/'variants'/parent['id']/'screens'/f'{i}.html').read_text() if parent else ''
    content=render_screen(title,i,board['screens'],ctx,variant['style'],bool(matching),' '.join(a['comment'] for a in matching))
    if parent and not matching: content=parent_html
    elif parent and sc.get('mode')=='region':
     notes={}
     for a in matching: notes.setdefault(a['element_id'],a['comment'])
     content=region_revise(parent_html,notes) or content
    if runner['type']=='fixture': (folder/'screens'/f'{i}.html').write_text(content)
    manifest['screens'].append(dict(id=str(i),title=title,file=f'screens/{i}.html',states=['default','help','error'] if i==1 else ['default','help']))
    if i<len(board['screens'])-1: manifest['edges'].append({'from':str(i),'to':str(i+1),'trigger':'continue'})
    if matching: variant['changes'].append(f'{title}: '+ '; '.join(a['comment'] for a in matching))
   if runner['type']=='cli':
    source=out/'output'
    for f in source.rglob('*'):
     if f.is_symlink() or not f.resolve().is_relative_to(source.resolve()): raise ValueError('Unsafe output symlink')
     if f.is_file() and f.suffix.lower() not in ALLOWED_OUTPUT: raise ValueError(f'Unsupported output file output/{f.relative_to(source)}. Allowed types: '+', '.join(sorted(ALLOWED_OUTPUT)))
    written=sorted(str(f.relative_to(source)) for f in source.rglob('*') if f.is_file())
    if not (source/'manifest.json').is_file(): raise ValueError('The agent finished without writing output/manifest.json ('+(f'it wrote {len(written)} other file(s): '+', '.join(written[:6]) if written else 'it wrote no files')+'). Open runner.log in the job history to see what it said.')
    try: manifest_check=json.loads((source/'manifest.json').read_text())
    except ValueError as e: raise ValueError('output/manifest.json is not valid JSON: '+str(e))
    shutil.copytree(source,folder,dirs_exist_ok=True); manifest=manifest_check; variant['anchors_added']={}
    for sd in manifest.get('screens',[]):
     pf=folder/sd.get('file','')
     if pf.is_file() and not pf.is_symlink() and pf.suffix=='.html':
      new,n=stamp_anchors(pf.read_text(errors='replace'))
      if n: pf.write_text(new); variant['anchors_added'][sd['id']]=n
   (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)); variant['manifest']=manifest
   check_manifest(manifest)
   if {s['id'] for s in manifest['screens']}!={str(i) for i in range(len(board['screens']))}: raise ValueError('Screen IDs must be zero-based strings')
   if len(manifest['screens'])!=len(board['screens']): raise ValueError('Missing requested screens')
   variant['validation']=validate(folder,manifest,ctx['effective_rules'],ctx['tokens'])
   if variant.get('anchors_added'): variant['validation'].append(dict(check='Annotation anchors added by the studio',outcome='review',evidence='The agent emitted no data-design-id on '+str(len(variant['anchors_added']))+' screen(s), so the studio added '+str(sum(variant['anchors_added'].values()))+' anchors (auto-<tag>-<n>) to make pins and region revisions possible. Markup is otherwise unchanged.'))
   if variant['references']: variant['validation'].append(dict(check=f"Reference images ({len(variant['references'])})",outcome='review',evidence=('Recorded with the job, but the fixture runner cannot interpret images. Use a local coding agent to apply them.' if runner['type']=='fixture' else 'Passed to the agent as files. Whether they were applied needs your judgement; this is not verified.')))
   if runner['type']=='fixture':
    variant['validation'].append(dict(check='Fixture guidance support',outcome='review',evidence='Template demo: supports tokens and explicit text/background/button color directives. Other prose rules need a local coding agent; no general rule conformance is claimed.'))
    variant['applied_tokens']=fixture_tokens(ctx)
   if parent:
    scope=j.get('scope') or {}; variant['changed_regions']={}; variant['revision_scope']=scope
    for screen_def in manifest['screens']:
     before=safe_path(STORE/'variants'/parent['id'],screen_def['file']).read_text(errors='replace'); after=safe_path(folder,screen_def['file']).read_text(errors='replace'); sc=scope.get(screen_def['id']); title=screen_def['title']
     if before==after:
      if sc: variant['validation'].append(dict(check='Revision scope · '+title,outcome='review',evidence='The agent made no change to this targeted screen.'))
      continue
     d=diff_regions(before,after); variant['changed_regions'][screen_def['id']]=d
     if not sc: variant['validation'].append(dict(check='Revision scope · '+title,outcome='fail',evidence='Changed although no feedback targeted this screen.'))
     elif sc['mode']=='region':
      extra=[x for x in d['elements'] if x not in sc['elements']]
      variant['validation'].append(dict(check='Revision scope · '+title,outcome='fail' if (extra or d['outside']) else 'pass',evidence=(('Changed outside the pinned element(s): '+', '.join(extra+(['page content'] if d['outside'] else []))) if (extra or d['outside']) else 'Only the pinned element(s) changed: '+', '.join(d['elements']))))
    (folder/'changes.json').write_text(json.dumps(variant['changes']))
   variant['changed_screens']=[sd['id'] for sd in manifest['screens'] if parent and (folder/sd['file']).read_bytes()!=safe_path(STORE/'variants'/parent['id'],sd['file']).read_bytes()]
   # Capture actual rendered screens using the locally installed browser.
   (folder/'thumbnails').mkdir(exist_ok=True)
   for s in manifest['screens']:
    check_cancel(j)
    try:
     subprocess.run(['google-chrome','--headless','--no-sandbox','--disable-gpu','--hide-scrollbars','--no-pdf-header-footer','--window-size=720,960',f'--user-data-dir=/tmp/studio-chrome-{j["id"]}',f'--screenshot={folder}/thumbnails/{s["id"]}.png',safe_path(folder,s['file']).as_uri()],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
    except (FileNotFoundError,subprocess.TimeoutExpired): pass
    if not (folder/'thumbnails'/f'{s["id"]}.png').is_file(): variant['validation'].append(dict(check='Screenshot capture · '+s['title'],outcome='not_assessable',evidence='Local Chrome capture unavailable'))
   check_cancel(j)
   save('variant',variant); j['variant_id']=variant['id']; folder=None
  event(j,'succeeded','Artifacts saved and deterministic validation completed')
 except Cancelled:
  if folder: shutil.rmtree(folder,ignore_errors=True)
  raise
 except subprocess.TimeoutExpired: event(j,'timed_out','Runner exceeded the configured timeout; partial log kept in job history')
 except Exception as e: event(j,'failed',str(e))
PLAYER_JS='''(function(){var P=window.parent;function send(){P.postMessage({type:"screen",file:location.pathname.split("/").pop(),title:document.title,help:document.querySelectorAll("details").length>0,error:document.querySelectorAll("[role=alert]").length>0},"*")}
window.addEventListener("message",function(e){if(e.source!==P)return;var m=e.data||{};if(m.cmd==="back")history.back();else if(m.cmd==="forward")history.forward();else if(m.cmd==="state"){document.querySelectorAll("details").forEach(function(x){x.open=m.name==="help"});document.querySelectorAll("[role=alert]").forEach(function(x){x.hidden=m.name!=="error"})}});
window.addEventListener("pageshow",send);send()})();
'''
def build_prototype(v):
 existing=next((p for p in allof('prototype') if p['variant_id']==v['id'] and (STORE/'prototypes'/p['id']).is_dir()),None)
 if existing: return existing
 pid=uid(); src=STORE/'variants'/v['id']; dst=STORE/'prototypes'/pid
 shutil.copytree(src,dst); (dst/'_player').mkdir(); (dst/'_player'/'nav.js').write_text(PLAYER_JS)
 tag='<script src="../_player/nav.js"></script>'
 for sc in v['manifest']['screens']:
  f=safe_path(dst,sc['file']); t=f.read_text(); f.write_text(t.replace('</body>',tag+'</body>',1) if '</body>' in t else t+tag)
 (dst/'index.html').write_text(f'<meta http-equiv="refresh" content="0;url=screens/{v["manifest"]["start_screen_id"]}.html">')
 board=get(v['board_id']); ctx=get(v['context_id'])
 return save('prototype',dict(id=pid,variant_id=v['id'],board_id=v['board_id'],project_id=v['project_id'],version=v['version'],runner_name=v['runner_name'],board_title=board['title'],context_hash=ctx['hash'],bundle_path=f'prototypes/{pid}',screens=v['manifest']['screens'],start_screen_id=v['manifest']['start_screen_id'],edges=v['manifest']['edges'],created_at=time.time()))
def approve(variant_id):
 v=get(variant_id)
 if v.get('review_state')=='reverted': raise ValueError('A reverted version cannot be approved; approve its parent or another version')
 with LOCK:
  if v.get('review_state')=='pending': v['review_state']='accepted'; v['decided_at']=time.time()
  for other in allof('variant'):
   if other['board_id']==v['board_id'] and other['id']!=v['id'] and other.get('approved'): other['approved']=False; other['superseded_approval_at']=time.time(); save('variant',other)
  if not v.get('approved'): v['approved']=True; v['approved_at']=time.time()
  save('variant',v)
  b=get(v['board_id'])
  if b.get('blind') and not b.get('revealed'): blind_choice(b['id'],v['id'],'Approved')
  proto=build_prototype(v)
 return dict(variant=v,prototype=proto)
# ---- mixing: compose one new immutable version from screens of different versions ----
LINK_RE=re.compile(r'(href|src|poster|action)\s*=\s*(["\'])([^"\']*)\2',re.I)
def style_fingerprint(folder,page):
 text=page.read_text(errors='replace')
 for link in re.findall(r'<link[^>]+href\s*=\s*["\']([^"\']+\.css)[^"\']*["\']',text,re.I):
  f=(page.parent/link).resolve()
  if f.is_file() and f.is_relative_to(folder.resolve()): text+=f.read_text(errors='replace')
 fonts=re.findall(r'font-family\s*:\s*([^;}{]+)',text,re.I); first=lambda x: re.split(r',',x)[0].strip().strip('"\'').lower()
 hexes={}
 for h in re.findall(r'#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b',text): hexes[h.lower()]=hexes.get(h.lower(),0)+1
 return dict(font=first(fonts[0]) if fonts else None,colors=[h for h,_ in sorted(hexes.items(),key=lambda x:-x[1])[:3]])
def mix_consistency(folder,entries,provenance):
 prints={e['id']:style_fingerprint(folder,folder/e['file']) for e in entries}
 fonts={p['font'] for p in prints.values() if p['font']}; palettes=[set(p['colors']) for p in prints.values()]
 problems=[]
 if len(fonts)>1: problems.append('different primary fonts: '+', '.join(sorted(fonts)))
 if palettes and len(set.intersection(*palettes))==0 and all(palettes): problems.append('no dominant colour is shared by every screen')
 detail='; '.join(f"screen {e['id']} ({next(p['name'] for p in provenance if p['screen']==e['id'])}): {prints[e['id']]['font'] or 'no font set'}, {', '.join(prints[e['id']]['colors']) or 'no colours'}" for e in entries)
 return dict(check='Cross-screen consistency (heuristic)',outcome='review',evidence=(('Possible inconsistencies: '+'; '.join(problems)+'. ') if problems else 'No differences in primary font or dominant colours were detected. ')+'This compares CSS text only and is not a visual review. '+detail)
def mix_variants(board_id,picks):
 board=get(board_id); ids=[str(i) for i in range(len(board['screens']))]
 if not isinstance(picks,dict) or set(map(str,picks))!=set(ids): raise ValueError('Choose a source version for every screen')
 sources={}
 for sid in ids:
  v=sources.get(picks[sid]) or get(picks[sid])
  if v.get('board_id')!=board_id or 'manifest' not in v: raise ValueError('Sources must be versions of this board')
  sources[v['id']]=v
 if len(sources)<2: raise ValueError('Pick screens from at least two different versions; to keep one version, just use it')
 vid=uid(); folder=STORE/'variants'/vid; (folder/'screens').mkdir(parents=True); (folder/'thumbnails').mkdir()
 try:
  for v in sources.values():
   src=STORE/'variants'/v['id']
   for item in src.iterdir():
    if item.name in ('manifest.json','changes.json','screens','thumbnails') or item.is_symlink(): continue
    dst=folder/'shared'/v['id']/item.name; dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(item,dst,symlinks=False) if item.is_dir() else shutil.copyfile(item,dst)
  def rewrite(text,src_id):
   root=(STORE/'variants'/src_id).resolve()
   def sub(m):
    attr,q,link=m.groups()
    if link.startswith(('#','data:','mailto:','tel:','http:','https:','//')) or not link: return m.group(0)
    base=re.split(r'[?#]',link)[0]; tail=link[len(base):]; target=(root/'screens'/base).resolve()
    if not target.is_relative_to(root): return m.group(0)
    rel=target.relative_to(root)
    if len(rel.parts)==2 and rel.parts[0]=='screens' and rel.suffix=='.html': return m.group(0)
    return f'{attr}={q}../shared/{src_id}/{rel.as_posix()}{tail}{q}'
   return LINK_RE.sub(sub,text)
  entries=[]; edges=[]; changes=[]; provenance=[]
  ctxs=[get(v['context_id']) for v in sources.values()]; ctx=max(ctxs,key=lambda c:c['created_at'])
  blind=board.get('blind') and not board.get('revealed'); name_of=lambda v: ('Option '+str(v.get('blind_label') or '?')) if blind else v['runner_name']
  for sid in ids:
   v=sources[picks[sid]]; src=STORE/'variants'/v['id']; entry=next((e for e in v['manifest']['screens'] if e['id']==sid),None)
   if not entry: raise ValueError(f'{name_of(v)} v{v["version"]} has no screen {sid}')
   text=safe_path(src,entry['file']).read_text(errors='replace'); (folder/'screens'/f'{sid}.html').write_text(rewrite(text,v['id']))
   entries.append(dict(id=sid,title=entry['title'],file=f'screens/{sid}.html',states=entry.get('states',['default'])))
   for e in v['manifest'].get('edges',[]):
    if e['from']==sid and e not in edges: edges.append(e)
   thumb=src/'thumbnails'/f'{sid}.png'
   if thumb.is_file(): shutil.copyfile(thumb,folder/'thumbnails'/f'{sid}.png')
   changes.append(f"{entry['title']}: from {name_of(v)} v{v['version']}"); provenance.append(dict(screen=sid,variant_id=v['id'],name=name_of(v),version=v['version']))
  first=sources[picks[ids[0]]]['manifest']
  manifest=dict(schema_version='1.0',kind='clickthrough-static',board_id=board_id,start_screen_id=first.get('start_screen_id',ids[0]) if first.get('start_screen_id') in ids else ids[0],screens=entries,edges=[e for e in edges if e['from'] in ids and e['to'] in ids])
  (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
  validation=validate(folder,manifest,ctx['effective_rules'],ctx['tokens'])
  validation.append(mix_consistency(folder,entries,provenance)); names=sorted({p['name']+' v'+str(p['version']) for p in provenance})
  validation.append(dict(check='Mixed provenance',outcome='review',evidence='Screens come from '+', '.join(names)+'. Visual and copy consistency across screens is not checked automatically.'))
  if len({c['id'] for c in ctxs})>1: validation.append(dict(check='Mixed context versions',outcome='review',evidence='Sources were generated under different guideline versions (v'+', v'.join(str(c.get('version','?')) for c in sorted(ctxs,key=lambda c:c['created_at']))+'); the newest is recorded.'))
  for sid in ids:
   if not (folder/'thumbnails'/f'{sid}.png').is_file(): validation.append(dict(check='Screenshot capture · '+next(e['title'] for e in entries if e['id']==sid),outcome='not_assessable',evidence='Source had no screenshot'))
 except Exception:
  shutil.rmtree(folder,ignore_errors=True); raise
 jid=uid(); count=len([v for v in allof('variant') if v['board_id']==board_id and v.get('kind')=='mix'])+1; label='Mix of '+' + '.join(dict.fromkeys(p['name'] for p in provenance))
 variant=dict(id=vid,project_id=board['project_id'],board_id=board_id,job_id=jid,runner_id=None,runner_name=label,kind='mix',style=None,parent_id=None,context_id=ctx['id'],version=count,approved=False,review_state=None,created_at=time.time(),changes=changes,changed_screens=[],references=[],mix_sources=provenance,manifest=manifest,validation=validation)
 save('variant',variant)
 save('job',dict(id=jid,project_id=board['project_id'],type='mix_board',runner_id=None,runner_name='Mix',status='succeeded',events=[dict(time=time.time(),message='Mixed '+str(len(ids))+' screens from '+str(len(sources))+' versions')],created_at=time.time(),board_id=board_id,variant_id=vid,context=ctx,input_hash=digest(picks),references=[],parent_id=None,annotations=[],brief=board['brief']))
 return variant
def set_review_state(variant_id,state):
 v=get(variant_id)
 if not v.get('parent_id'): raise ValueError('Only revisions can be accepted or reverted')
 if v.get('approved') and state=='reverted': raise ValueError('An approved version is locked; approve another version first')
 v['review_state']=state; v['decided_at']=time.time(); return save('variant',v)
# ---- reference images: designer-supplied visual context passed to agents as files ----
MAX_REF_BYTES=5_000_000; MAX_REFS_PER_PROJECT=40
def sniff_image(raw):
 if raw.startswith(b'\x89PNG\r\n\x1a\n'): return 'png','image/png'
 if raw.startswith(b'\xff\xd8\xff'): return 'jpg','image/jpeg'
 if raw[:4]==b'RIFF' and raw[8:12]==b'WEBP': return 'webp','image/webp'
 if raw[:4]==b'GIF8': return 'gif','image/gif'
 raise ValueError('Unsupported image type. Use PNG, JPEG, WebP or GIF.')
def add_reference(d):
 pid=d['project_id']; get(pid)
 try: raw=base64.b64decode(d.get('data',''),validate=True)
 except Exception: raise ValueError('Image data is not valid')
 if not raw: raise ValueError('Empty image')
 if len(raw)>MAX_REF_BYTES: raise ValueError('Image is larger than 5 MB')
 if len([r for r in allof('reference') if r['project_id']==pid])>=MAX_REFS_PER_PROJECT: raise ValueError('Reference limit reached for this project')
 ext,mime=sniff_image(raw); rid=uid(); folder=STORE/'projects'/pid/'references'; folder.mkdir(parents=True,exist_ok=True)
 (folder/f'{rid}.{ext}').write_bytes(raw)
 name=re.sub(r'[^\w .,()\-]','',str(d.get('name') or 'Reference'))[:80].strip() or 'Reference'
 return save('reference',dict(id=rid,project_id=pid,name=name,note=str(d.get('note',''))[:500],file=f'{rid}.{ext}',mime=mime,size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),created_at=time.time()))
def delete_reference(rid):
 r=get(rid); f=STORE/'projects'/r['project_id']/'references'/r['file']
 if f.is_file(): f.unlink()
 with LOCK,db() as c: c.execute('DELETE FROM entities WHERE id=?',(rid,))
 return {'deleted':rid}
def resolve_references(project_id,ids):
 out=[]
 for i in dict.fromkeys(ids or []):
  r=get(i)
  if r.get('project_id')!=project_id or 'sha256' not in r: raise ValueError('Reference images must belong to this project')
  out.append(dict(id=r['id'],name=r['name'],note=r.get('note',''),file=r['file'],mime=r['mime'],sha256=r['sha256']))
 return out
def snapshot_references(j,source_dir):
 # Copy into the job's own folder so retries and history keep working even if the library image is later deleted.
 if not j.get('references'): return
 dst=STORE/'jobs'/j['id']/'references'; dst.mkdir(parents=True,exist_ok=True)
 for r in j['references']:
  src=source_dir/r['file']
  if not src.is_file(): raise ValueError('Reference image is no longer available: '+r['name'])
  shutil.copyfile(src,dst/r['file'])
# ---- blind A/B comparison: identities are withheld by the server until the designer chooses or reveals ----
LETTERS='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
def assign_labels(board_id,count):
 used={v.get('blind_label') for v in allof('variant') if v['board_id']==board_id}|{j.get('blind_label') for j in allof('job') if j.get('board_id')==board_id}
 pool=[c for c in LETTERS if c not in used]; random.SystemRandom().shuffle(pool); return pool[:count]
def label_lineage(board_id):
 vs=[v for v in allof('variant') if v['board_id']==board_id]; byid={v['id']:v for v in vs}
 for v in sorted([v for v in vs if not v.get('parent_id') and not v.get('blind_label') and v.get('kind')!='mix'],key=lambda x:x['id']):
  v['blind_label']=assign_labels(board_id,1)[0]; save('variant',v)
 for v in sorted(vs,key=lambda x:x['created_at']):
  if v.get('parent_id') and not v.get('blind_label'):
   root=v
   while root.get('parent_id') and root['parent_id'] in byid: root=byid[root['parent_id']]
   if root.get('blind_label'): v['blind_label']=root['blind_label']; save('variant',v)
def set_blind(board_id,on):
 b=get(board_id)
 if on and b.get('revealed'): raise ValueError('Identities were already revealed for this board')
 b['blind']=bool(on); save('board',b)
 if on: label_lineage(board_id)
 return get(board_id)
def blind_choice(board_id,variant_id=None,reason=''):
 b=get(board_id)
 if not b.get('blind') or b.get('revealed'): raise ValueError('This board is not in blind mode')
 choice=None
 if variant_id:
  v=get(variant_id)
  if v['board_id']!=board_id: raise ValueError('Choose a variation from this board')
  choice=dict(variant_id=v['id'],label=v.get('blind_label'),runner_name=v['runner_name'],reason=str(reason)[:500],at=time.time())
 b['revealed']=True; b['blind_choice']=choice; return save('board',b)
def mask_state(state):
 hidden={b['id'] for b in state['board'] if b.get('blind') and not b.get('revealed')}
 if not hidden: return state
 for v in state['variant']:
  if v['board_id'] in hidden:
   v['runner_name']='Option '+(v.get('blind_label') or '?') if v.get('kind')!='mix' else v['runner_name']; v['runner_id']=None; v.pop('style',None); v.pop('applied_tokens',None)
   for c in v.get('validation',[]):
    if c['check']=='Fixture guidance support': c.update(check='Guidance support',evidence='Some prose guidance may not be applied automatically; needs designer review.')
 for j in state['job']:
  if j.get('board_id') in hidden: j['runner_name']='Hidden (blind)'; j['runner_id']=None
 for p in state['prototype']:
  if p.get('board_id') in hidden: p['runner_name']='Hidden (blind)'
 return state
def create_board(data):
 project_id=data['project_id']; get(project_id)
 screens=data.get('screens',[])
 if not isinstance(screens,list) or not 2<=len(screens)<=5 or any(not isinstance(n,str) or not n.strip() for n in screens): raise ValueError('Choose 2–5 named screens')
 board=dict(id=uid(),project_id=project_id,title=data.get('title','Untitled board'),brief=data.get('brief',''),screens=screens)
 if 'research_id' in data:
  research=get(data['research_id'])
  if research.get('project_id')!=project_id or 'findings' not in research: raise ValueError('Research must belong to this project')
  ids=data.get('finding_ids',[])
  findings=[f for f in research['findings'] if f['id'] in ids]
  if not findings or set(ids)!={f['id'] for f in findings}: raise ValueError('Choose valid research findings')
  board.update(research_id=research['id'],research_brief=research['brief'],research_findings=findings,research_sources=research.get('sources',[]))
 return save('board',board)

def launch(data,kind,project_id):
 if kind=='research' and not str(data.get('brief','')).strip(): raise ValueError('Enter a research question first')
 p=get(project_id); ctx=get(p['context_id']); key=data.get('idempotency_key')
 if key:
  existing=[j for j in allof('job') if j.get('key')==key and j['project_id']==project_id]
  if existing: return existing

 if kind=='revise_board' and data.get('parent_id') and not data.get('runner_ids') and not get(data['parent_id']).get('runner_id'): raise ValueError('Choose a runner to revise a mixed version')
 runners=data.get('runner_ids') or ([get(data['parent_id'])['runner_id']] if kind=='revise_board' and data.get('parent_id') else [next(r['id'] for r in allof('runner') if r.get('enabled',True))]); jobs=[]
 enabled={r['id'] for r in allof('runner') if r.get('enabled',True)}
 if any(r not in enabled for r in runners): raise ValueError('Runner is disabled or no longer exists')
 annotations=data.get('annotations',[])
 if kind=='revise_board':
  ids=data.get('annotation_ids',[]); annotations=[get(i) for i in ids]
  if not annotations or any(a['variant_id']!=data.get('parent_id') or a.get('status','open')!='open' for a in annotations): raise ValueError('Select open feedback pins on the version being revised')
 board_for_refs=get(data['board_id']) if data.get('board_id') else None
 ref_ids=data['reference_ids'] if 'reference_ids' in data else (board_for_refs or {}).get('reference_ids',[])
 references=resolve_references(project_id,[i for i in ref_ids if any(r['id']==i for r in allof('reference'))])
 scope={}
 if kind=='revise_board':
  by_screen={}
  for a in annotations:
   e=by_screen.setdefault(str(a['screen']),{'elements':[],'anchored':True})
   if a.get('element_id'): e['elements'].append(a['element_id'])
   else: e['anchored']=False
  region=data.get('scope_mode','region')=='region'
  scope={sid:({'mode':'region','elements':sorted(set(e['elements']))} if region and e['anchored'] and e['elements'] else {'mode':'screen'}) for sid,e in by_screen.items()}
 common=dict(scope=scope,references=references,brief=data.get('brief',''),board_id=data.get('board_id'),parent_id=data.get('parent_id'),annotations=annotations,sources=data.get('sources',[]),findings=[f for r in allof('research') if r['project_id']==project_id for f in r['findings'] if f.get('selected')],context=ctx)
 if common['board_id']:
  common['board']=get(common['board_id'])
  if common['board']['project_id']!=project_id: raise ValueError('Board must belong to this project')
  if 'research_findings' in common['board']:
   common['findings']=common['board']['research_findings']
   common['sources']=common['board'].get('research_sources',[])
 if common['parent_id']:
  common['parent_package']=str(STORE/'variants'/common['parent_id'])
 shared=digest(common)
 for runner_id in runners:
  blind_labels=assign_labels(common['board_id'],1) if kind=='generate_board' and board_for_refs and board_for_refs.get('blind') else []
  j=dict(id=uid(),project_id=project_id,type=kind,runner_id=runner_id,runner_name=get(runner_id).get('name',''),status='queued',events=[],created_at=time.time(),input_hash=shared,key=key,**common)
  scope_text=('\nRevision scope (strict): '+'; '.join((f'screen {sid}: change ONLY the element(s) with data-design-id in {sc["elements"]} and their descendants, keep every other byte of that file identical' if sc['mode']=='region' else f'screen {sid}: you may change the whole screen') for sid,sc in scope.items())+'; all other screens must be copied unchanged.') if scope else ''
  refs_text=('\nReference images (designer-supplied visual context; files in references/). Treat them as inspiration or constraints, not verified brand rules; the guidelines above take precedence unless a note says otherwise:\n'+'\n'.join(f'- references/{r["file"]} · {r["name"]}'+(f' · note: {r["note"]}' if r['note'] else '') for r in references)) if references else ''
  if blind_labels: j['blind_label']=blind_labels[0]
  j['instruction']=f'Task: {kind}. Output contract: static variant-package/1.0 or research.json.\nBrief: {common["brief"]}\nScreens: {common.get("board",{}).get("screens",[])}\nDESIGN.md:\n{ctx["markdown"]}\nTokens: {canonical(ctx["tokens"])}\nRules: {canonical(ctx["effective_rules"])}\nSnapshot SHA256: {ctx["hash"]}\nFindings (unverified unless explicitly sourced): {canonical(common["findings"])}\nSupplied sources (preserve provenance): {canonical(common["sources"])}\nAnnotations: {canonical(common["annotations"])}{refs_text}{scope_text}\nYou are running non-interactively: do not ask questions, do not reply with only a plan or summary, and do not wait for confirmation. The task is only complete when the files exist. Only create these file types: .html .css .js .json .png .jpg .svg .woff .woff2 (plus optional .md/.txt notes). Write files to output/. Research output: research.json with findings (id,title,detail,verification,source_ids,selected) and sources arrays. Variant output: manifest.json with schema_version=1.0, kind=clickthrough-static, board_id, start_screen_id=0 (string), screens array with id as zero-based string, title, file=screens/<id>.html, states array; edges with from,to,trigger. All requested screens must exist. Use data-role=primary-action on primary controls and data-design-id on annotation targets. For a revision, output/ ALREADY CONTAINS a full copy of the parent version: edit those files in place and leave everything not covered by the revision scope untouched. No external dependencies. Enumerate files and any guidelines you could not honor; self-report is not validation.'
  save('job',j); jobs.append(j); snapshot_references(j,STORE/'projects'/project_id/'references'); enqueue(j)
 if kind=='generate_board' and board_for_refs is not None and 'reference_ids' in data: board_for_refs['reference_ids']=[r['id'] for r in references]; save('board',board_for_refs)
 for a in annotations:
  if kind=='revise_board': a=get(a['id']); a.update(status='applied',job_ids=[j['id'] for j in jobs]); save('annotation',a)
 return jobs
def retry_job(job_id):
 old=get(job_id)
 if old['status'] not in ['failed','timed_out','cancelled']: raise ValueError('Only failed, timed-out or cancelled jobs can be retried')
 if old.get('retried_by'): raise ValueError('This job was already retried')
 fresh={k:v for k,v in old.items() if k not in ['id','status','events','variant_id','key','retried_by']}
 j=dict(fresh,id=uid(),status='queued',events=[],created_at=time.time(),key=None,retry_of=old['id']); snapshot_references(j,STORE/'jobs'/old['id']/'references'); old['retried_by']=j['id']; save('job',old); save('job',j)
 enqueue(j); return j
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args): pass
 def send_json(self,x,status=200):
  data=json.dumps(x).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
 def do_GET(self):
  path=urlparse(self.path).path
  try:
   if path=='/api/local-agents': return self.send_json(discover())
   if path=='/api/state': return self.send_json(mask_state({k:allof(k) for k in ['project','context','board','variant','job','research','annotation','runner','prototype','reference']}))
   if path.startswith('/api/export/'):
    rec=get(path.split('/')[-1]); proto='variant_id' in rec; v=get(rec['variant_id']) if proto else rec; folder=STORE/('prototypes' if proto else 'variants')/rec['id']; buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
     for f in folder.rglob('*'):
      if f.is_file() and not f.is_symlink(): z.write(f,f.relative_to(folder))
     if not proto: z.writestr('index.html',f'<meta http-equiv="refresh" content="0;url=screens/{v["manifest"]["start_screen_id"]}.html">')
    self.send_response(200); self.send_header('Content-Type','application/zip'); self.send_header('Content-Disposition','attachment; filename="prototype.zip"'); self.end_headers(); return self.wfile.write(buf.getvalue())
   if path.startswith('/assets/'):
    if hidden_job_file(path): return self.send_json({'message':'Hidden while this comparison is blind'},403)
    f=safe_path(STORE,path[len('/assets/'):])
   else: f=safe_path(ROOT/'apps/web',path.lstrip('/')) if '.' in path.split('/')[-1] else ROOT/'apps/web/index.html'
   if not f.is_file(): return self.send_error(404)
   import mimetypes
   self.send_response(200); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; form-action 'none'" if path.startswith('/assets/') else "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; script-src 'self'"); self.send_header('Content-Type',mimetypes.guess_type(f)[0] or 'application/octet-stream'); self.end_headers(); self.wfile.write(f.read_bytes())
  except Exception as e: self.send_json({'message':str(e)},400)
 def do_POST(self):
  try:
   origin=self.headers.get('Origin')
   if origin and urlparse(origin).netloc!=self.headers.get('Host'): raise ValueError('Cross-origin request rejected')
   n=int(self.headers.get('Content-Length',0))
   if n>(8_000_000 if self.path.endswith('/reference-upload') else 1_000_000): raise ValueError('Request too large')
   d=json.loads(self.rfile.read(n) or '{}'); action=self.path.split('/')[-1]
   if action=='local-runner': result=save('runner',dict(id=uid(),**configuration(d['agent'],d.get('model',''))))
   elif action=='project': result=project(d)
   elif action=='update-project':
    p=get(d['id']); p.update({k:v for k,v in d.items() if k in ['name','archived','description']}); result=save('project',p)
   elif action=='context': result=context(d['project_id'],d)
   elif action=='board': result=create_board(d)
   elif action=='research-board':
    runner_ids=d.get('runner_ids',[])
    if len(set(runner_ids))<2: raise ValueError('Choose at least two runner configurations')
    if any(r not in {r['id'] for r in allof('runner')} for r in runner_ids): raise ValueError('Runner unavailable')
    key=d.get('idempotency_key')
    with LOCK:
     previous=next((b for b in allof('board') if key and b.get('handoff_key')==key and b['project_id']==d['project_id']),None)
     board=previous or create_board(d)
     board['handoff_key']=key; save('board',board)
     jobs=launch(dict(d,board_id=board['id']), 'generate_board',d['project_id'])
    result={'board':board,'jobs':jobs}
   elif action in ['research','generate','revise']: result=launch(d,{'research':'research','generate':'generate_board','revise':'revise_board'}[action],d['project_id'])
   elif action=='finding':
    r=get(d['research_id'])
    for f in r['findings']:
     if f['id']==d['id']: f['selected']=d['selected']
    result=save('research',r)
   elif action=='annotation':
    if not 0<=d['x']<=1 or not 0<=d['y']<=1 or not d['comment'].strip(): raise ValueError('Invalid annotation')
    get(d['variant_id']); result=save('annotation',dict(d,id=uid(),created_at=time.time(),status='open',selected=True,element_id=d.get('element_id') or None))
   elif action=='reference-upload': result=add_reference(d)
   elif action=='reference-update':
    r=get(d['id']); r.update({k:str(d[k])[:500 if k=='note' else 80] for k in ['name','note'] if k in d}); result=save('reference',r)
   elif action=='reference-delete': result=delete_reference(d['id'])
   elif action=='board-blind': result=set_blind(d['board_id'],d.get('blind',True))
   elif action=='blind-choice': result=blind_choice(d['board_id'],d.get('variant_id'),d.get('reason',''))
   elif action=='mix': result=mix_variants(d['board_id'],d.get('picks'))
   elif action=='approve': result=approve(d['id'])
   elif action=='accept-revision': result=set_review_state(d['id'],'accepted')
   elif action=='revert-revision': result=set_review_state(d['id'],'reverted')
   elif action=='review-check':
    v=get(d['variant_id']); 
    if d['decision'] not in ['accepted','needs_change','open']: raise ValueError('Unknown decision')
    v.setdefault('reviews',{})[str(d['index'])]=dict(decision=d['decision'],note=d.get('note',''),time=time.time()); result=save('variant',v)
   elif action=='annotation-update':
    a=get(d['id'])
    if a.get('status','open')!='open': raise ValueError('Applied feedback is part of history and cannot be edited')
    a.update({k:d[k] for k in ['comment','selected'] if k in d})
    if not str(a['comment']).strip(): raise ValueError('Comment cannot be empty')
    result=save('annotation',a)
   elif action=='annotation-delete':
    a=get(d['id'])
    if a.get('status','open')!='open': raise ValueError('Applied feedback is part of history and cannot be deleted')
    with LOCK,db() as c: c.execute('DELETE FROM entities WHERE id=?',(a['id'],))
    result={'deleted':a['id']}
   elif action=='cancel-job':
    cancel_job(d['id']); result={'cancelling':d['id']}
   elif action=='retry-job': result=retry_job(d['id'])
   elif action=='update-runner':
    r=get(d['id']); r.update({k:d[k] for k in ['name','enabled','timeout'] if k in d})
    if 'env_allowlist' in d:
     names=[str(x).strip() for x in d['env_allowlist'] if str(x).strip()]
     if any(not re.fullmatch(r'[A-Z_][A-Z0-9_]*',n) for n in names): raise ValueError('Environment variable names must be UPPER_SNAKE_CASE')
     r['env_allowlist']=names
    if 'model' in d and r['type']=='cli':
     r['args']=configuration(r['agent'],d['model'].strip())['args']; r['model']=d['model'].strip()
    if not str(r['name']).strip(): raise ValueError('Runner needs a name')
    result=save('runner',r)
   elif action=='delete-runner':
    if len([r for r in allof('runner') if r['id']!=d['id'] and r.get('enabled',True)])<1: raise ValueError('Keep at least one enabled runner')
    with LOCK,db() as c: c.execute('DELETE FROM entities WHERE id=?',(d['id'],))
    result={'deleted':d['id']}
   elif action=='board-research':
    b=get(d['board_id']); r=get(d['research_id']); ids=d.get('finding_ids',[]); f=[x for x in r['findings'] if x['id'] in ids]
    if b['project_id']!=r.get('project_id') or not f or len(f)!=len(set(ids)): raise ValueError('Choose valid findings from this project')
    b.update(research_id=r['id'],research_brief=r['brief'],research_findings=f,research_sources=r.get('sources',[]),research_updated_at=time.time()); result=save('board',b)
   elif action=='runner':
    if d['type'] not in ['fixture','cli']: raise ValueError('Unsupported runner')
    result=save('runner',dict(id=uid(),**d))
   elif action=='test-runner':
    r=get(d['id']); result={'message':'Fixture ready' if r['type']=='fixture' else ('Executable found' if shutil.which(r.get('executable','')) else 'Executable unavailable')}
   else: raise ValueError('Unknown action')
   self.send_json(result)
  except Exception as e: self.send_json({'code':'INVALID_REQUEST','message':str(e),'request_id':uid()},400)
def main():
 import errno
 import sys
 try:
  port=int(os.environ.get('PORT','5173'))
  if not 0 < port < 65536: raise ValueError()
 except ValueError:
  print('Design Studio: PORT must be an integer from 1 to 65535.',file=sys.stderr)
  return 1
 try:
  server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
 except OSError as error:
  if error.errno==errno.EADDRINUSE:
   print(f'Design Studio: port {port} is already in use. Stop the existing server or choose another port:\n  PORT={port+1 if port<65535 else 5173} python3 apps/api/server.py',file=sys.stderr)
  elif error.errno in (errno.EACCES,errno.EPERM):
   print(f'Design Studio: permission denied opening 127.0.0.1:{port}. Run in a terminal that permits local server sockets, or choose an unprivileged port with PORT=5174.',file=sys.stderr)
  else:
   print(f'Design Studio: cannot listen on 127.0.0.1:{port}: {error}',file=sys.stderr)
  return 1
 with server:
  seed()
  resumed=recover_jobs(); start_workers()
  if resumed: print(f'Resumed {resumed} queued job(s) after restart',flush=True)
  print(f'Design Studio → http://localhost:{port}',flush=True)
  try: server.serve_forever()
  except KeyboardInterrupt: pass
 return 0

if __name__=='__main__':
 raise SystemExit(main())
