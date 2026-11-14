"""Discover binaries and non-secret local model metadata. Never read credentials."""
import re, json, os, shutil, subprocess
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def bwrap_ok():
 # True only if bubblewrap exists and can really create the namespaces we need (some systems disable them).
 exe=shutil.which('bwrap')
 if not exe: return False
 try: return subprocess.run([exe,'--ro-bind','/','/','--dev','/dev','--proc','/proc','--tmpfs','/tmp','true'],capture_output=True,timeout=10).returncode==0
 except (OSError,subprocess.TimeoutExpired): return False

CLAUDE_RUN_TOOLS=['Bash(python3 *)','Bash(python *)','Bash(node *)','Bash(mkdir *)','Bash(ls *)','Bash(cat *)']

def discover():
 result=[]
 for name in ['codex','claude','opencode','gemini','copilot','aider']:
  executable=shutil.which(name)
  if not executable: continue
  models=[]; source='Manual model ID; availability is checked by the agent when a job runs'
  if name=='codex':
   cache=Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))/'models_cache.json'
   try:
    data=json.loads(cache.read_text()); models=[m['slug'] for m in data.get('models',[]) if m.get('slug')]; source='Local Codex model cache (may be stale)'
   except (OSError,ValueError,KeyError): pass
  if name=='opencode':
   try:
    p=subprocess.run([executable,'models'],capture_output=True,text=True,timeout=8)
    if p.returncode==0: models=[s for s in p.stdout.splitlines() if '/' in s and len(s)<150]; source='opencode models'
   except (OSError,subprocess.TimeoutExpired): pass
  result.append(dict(id=name,name={'codex':'Codex','claude':'Claude Code','opencode':'OpenCode','gemini':'Gemini CLI','copilot':'GitHub Copilot','aider':'Aider'}[name],executable=executable,models=models,model_source=source,supported=name in ['codex','claude','opencode']))
 return result

def configuration(agent,model,sandbox=None):
 # sandbox: whether the studio's own filesystem sandbox (bubblewrap) wraps this agent. Default: on when usable.
 sandbox=bwrap_ok() if sandbox is None else bool(sandbox)
 model=str(model or '').strip()
 if model and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/@-]{0,99}',model): raise ValueError('Model IDs may only contain letters, numbers and . _ : / @ -')
 installed=next((a for a in discover() if a['id']==agent),None)
 if not installed or not installed['supported']: raise ValueError('No supported adapter for this installed agent')
 # Codex's own sandbox cannot start inside ours (nested user namespaces are denied), so exactly one layer confines it:
 # ours when active, otherwise Codex's workspace-write mode. Never both off.
 if agent=='codex': args=['exec','--skip-git-repo-check','--sandbox','danger-full-access' if sandbox else 'workspace-write']+(['--model',model] if model else [])+['{prompt}']
 elif agent=='claude':
  # acceptEdits lets Claude write files but silently blocks running anything, and a non-interactive run cannot ask for approval.
  # Agents often build screens with a small generator script, so inside our filesystem sandbox allow running interpreters
  # (they can only write the job folder). Without the sandbox keep it edit-only.
  args=['--print','--permission-mode','acceptEdits']+(['--allowedTools='+','.join(CLAUDE_RUN_TOOLS)] if sandbox else [])+(['--model',model] if model else [])+['{prompt}']
 else: args=['run']+(['--model',model] if model else [])+['{prompt}']
 env=['PATH','HOME','USER','LANG','LC_ALL','TERM','TMPDIR','SHELL','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME']+{'codex':['CODEX_HOME','OPENAI_API_KEY'],'claude':['CLAUDE_CONFIG_DIR','ANTHROPIC_API_KEY'],'opencode':['OPENCODE_CONFIG']}.get(agent,[])
 real=os.path.dirname(os.path.realpath(installed['executable']))
 rw={'codex':['~/.codex'],'claude':['~/.claude','~/.claude.json'],'opencode':['~/.config/opencode','~/.local/share/opencode']}.get(agent,[])
 return dict(name=installed['name']+' / '+(model or 'agent default'),type='cli',agent=agent,model=model,executable=installed['executable'],args=args,timeout=300,env_allowlist=env,auto_retries=0,sandbox='bwrap' if sandbox else None,sandbox_ro=[real],sandbox_rw=rw)
