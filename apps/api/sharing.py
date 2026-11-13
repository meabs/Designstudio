"""Read-only share links and the static share player."""

import secrets, hmac, time
from core import allof, get, save


# ---- read-only share links: served by a separate minimal listener that exposes nothing but approved prototype bundles ----
def share_find(token):
    for p in allof('prototype'):
        for sh in p.get('shares', []):
            if hmac.compare_digest(str(sh['token']), str(token)):
                if sh.get('revoked'):
                    return None, 'revoked'
                if sh.get('expires_at') and sh['expires_at'] < time.time():
                    return None, 'expired'
                return p, sh
    return None, 'unknown'


def share_create(pid, hours):
    p = get(pid)
    if 'variant_id' not in p:
        raise ValueError('Shares belong to a built prototype')
    if hours is not None and not (isinstance(hours, (int, float)) and 0 < hours <= 24 * 30):
        raise ValueError('Expiry must be between 1 hour and 30 days, or none')
    sh = dict(
        token=secrets.token_urlsafe(18),
        created_at=time.time(),
        expires_at=(time.time() + hours * 3600) if hours else None,
        revoked=False,
    )
    p.setdefault('shares', []).append(sh)
    return save('prototype', p)


def share_revoke(pid, token):
    p = get(pid)
    for sh in p.get('shares', []):
        if sh['token'] == token:
            sh['revoked'] = True
    return save('prototype', p)


SHARE_PLAYER = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Shared prototype</title>
<style>*{box-sizing:border-box}body{margin:0;font:13px system-ui,sans-serif;background:#ebecf0;color:#202124;height:100vh;display:flex;flex-direction:column}header{background:#242629;color:#e6e6ec;display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 12px}header .grow{flex:1}button{font:inherit;height:28px;padding:0 10px;border-radius:6px;border:1px solid #494a50;background:#34363c;color:#e6e6ec;cursor:pointer}button.on{background:#6366f1;border-color:#6366f1}button:focus-visible{outline:2px solid #a5a7f5;outline-offset:2px}.info{background:#fff;padding:8px 14px;font-size:12px;border-bottom:1px solid #e5e7eb;display:flex;gap:24px;flex-wrap:wrap}main{flex:1;overflow:auto;padding:20px;display:flex;justify-content:center;align-items:flex-start}.device{height:100%;min-height:520px;width:1440px;max-width:100%}.device.mobile{width:390px;border:10px solid #2b2d33;border-radius:34px;overflow:hidden;background:#2b2d33;max-height:844px}iframe{width:100%;height:100%;border:0;background:#fff;display:block}.badge{font-size:11px;background:#fff;color:#242629;border-radius:4px;padding:2px 7px}</style></head>
<body><header><strong>Prototype</strong><span class="badge">Read-only share</span><span class="grow"></span><button data-c="back">&#8592; Back</button><button data-c="forward">Forward &#8594;</button><button data-c="restart">Restart</button><button data-s="default">Default</button><button data-s="help">Help</button><button data-s="error">Error</button><button data-d="desktop" class="on">Desktop 1440</button><button data-d="mobile">Mobile 390</button></header>
<div class="info" id="info" role="status" aria-live="polite"></div><main><div class="device" id="device"><iframe id="f" title="Shared click-through prototype" sandbox="allow-scripts allow-forms"></iframe></div></main><script src="player.js"></script></body></html>'''
SHARE_JS = r'''(function(){var f=document.getElementById("f"),info=document.getElementById("info"),dev=document.getElementById("device"),meta;
function show(file){var i=0;meta.screens.forEach(function(s,k){if(s.file.split("/").pop()===file)i=k});var s=meta.screens[i];info.textContent="";[s.title+" \u00b7 screen "+(i+1)+" of "+meta.screens.length,meta.board_title+" \u00b7 v"+meta.version,dev.className.indexOf("mobile")>-1?"Mobile \u00b7 390px":"Desktop \u00b7 1440px"].forEach(function(t){var e=document.createElement("span");e.textContent=t;info.appendChild(e)})}
fetch("meta.json").then(function(r){return r.json()}).then(function(m){meta=m;var st=m.screens.filter(function(s){return s.id===m.start})[0]||m.screens[0];f.src="f/"+st.file;show(st.file.split("/").pop())});
window.addEventListener("message",function(e){if(e.source!==f.contentWindow||!e.data||e.data.type!=="screen"||!meta)return;show(String(e.data.file||"").replace(/[^\w.\-]/g,""))});
function send(m){f.contentWindow.postMessage(m,"*")}
document.querySelectorAll("[data-c]").forEach(function(b){b.onclick=function(){if(b.dataset.c==="restart"){var st=meta.screens.filter(function(s){return s.id===meta.start})[0]||meta.screens[0];f.src="f/"+st.file}else send({cmd:b.dataset.c})}});
document.querySelectorAll("[data-s]").forEach(function(b){b.onclick=function(){send({cmd:"state",name:b.dataset.s})}});
document.querySelectorAll("[data-d]").forEach(function(b){b.onclick=function(){dev.className="device "+(b.dataset.d==="mobile"?"mobile":"");document.querySelectorAll("[data-d]").forEach(function(x){x.classList.toggle("on",x===b)});if(meta)show((meta.screens[0]||{}).file.split("/").pop())}})})();'''
