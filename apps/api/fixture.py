"""Deterministic fixture runner: renders sample screens from tokens and a small instruction vocabulary."""

import re, html


def fixture_tokens(ctx):
    # Deliberately small, explicit fixture vocabulary; not a general language model.
    tokens = dict(ctx['tokens'])
    colors = {
        'pink': '#db2777',
        'red': '#dc2626',
        'blue': '#2563eb',
        'green': '#15803d',
        'purple': '#7c3aed',
        'black': '#111111',
        'white': '#ffffff',
        'orange': '#c2410c',
    }
    instructions = [ctx.get('markdown', ''), ctx.get('run_overrides', {}).get('prose', '')] + [
        r.get('description', '') for r in ctx.get('effective_rules', []) if r.get('enabled', True)
    ]
    for text in instructions:
        for match in re.finditer(
            r'(?:use\s+)?(#[0-9a-f]{6}\b|pink|red|blue|green|purple|black|white|orange)\s+(text|background|buttons?)\b|(?:text|background|buttons?)\s+(?:colou?r\s+)?(?:should\s+be|must\s+be|is|:|=)\s*(#[0-9a-f]{6}\b|pink|red|blue|green|purple|black|white|orange)\b',
            text,
            re.I,
        ):
            if re.search(
                r"(?:don't|do not|never|avoid|not)\s+(?:use\s+)?$",
                text[max(0, match.start() - 35) : match.start()],
                re.I,
            ):
                continue
            color, target = (match[1], match[2]) if match[1] else (match[3], match[0].split()[0])
            tokens[
                {'text': 'ink', 'background': 'background', 'button': 'accent', 'buttons': 'accent'}[target.lower()]
            ] = colors.get(color.lower(), color.lower())
    return tokens


def render_screen(title, index, screens, ctx, style, revised=False, comment=''):
    t = fixture_tokens(ctx)
    esc = html.escape
    css = ';'.join('--' + k + ':' + str(v).replace('<', '').replace('>', '') for k, v in t.items())
    nextfile = f'{min(index+1,len(screens)-1)}.html'
    previous = f'{max(index-1,0)}.html'
    heading = [
        'A little check.\nA lot of possibility.',
        'Let’s get to know you.',
        'Looking good.\nLet’s make it yours.',
    ][min(index, 2)]
    body = '<p>Check your eligibility in a few simple steps. It won’t affect your credit score.</p><div class="benefits"><div>✓ &nbsp; A decision in minutes</div><div>✓ &nbsp; No impact on your credit score</div><div>✓ &nbsp; No commitment to apply</div></div>'
    if index == 1:
        body = '<p>We ask for these details to confirm your identity. This demo uses fictional information only.</p><label>Full name<input value="Alex Morgan" readonly></label><label>Email address<input value="alex@example.test" readonly></label><label>Annual income<input value="£38,000" readonly></label><button class="text" onclick="document.querySelector(\'#error\').hidden=false">Try a validation state</button><p id="error" hidden role="alert">Enter an annual income to continue. (Demo state)</p>'
    if index >= 2:
        body = '<p>Take a moment to check your application before continuing.</p><div class="summary">Full name <b>Alex Morgan</b><hr>Annual income <b>£38,000</b><hr>Card <b>Everyday credit</b></div><a href="1.html">Edit details ↗</a>'
    if revised:
        body = (
            f'<p class="revision" data-design-id="explanation">{esc(comment)} — Updated explanation: your information is used only for this eligibility check.</p>'
            + body
        )
    extra = (
        '<button data-role="primary-action">Apply now</button>' if style == 'b' and index == 0 and not revised else ''
    )
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>:root{{{css}}}*{{box-sizing:border-box}}body{{margin:0;color:var(--ink,#202b24);background:var(--background,#f7f8f5);font:15px var(--font,system-ui)}}header{{padding:28px 38px;border-bottom:1px solid #dce1d8;display:flex;justify-content:space-between;font-size:12px}}.brand{{font-size:21px;font-weight:700;letter-spacing:-1px}}main{{max-width:600px;padding:40px;margin:auto}}.eyebrow{{color:var(--accent);font-size:11px;letter-spacing:2px;text-transform:uppercase}}h1{{font-size:43px;line-height:1.12;white-space:pre-line;letter-spacing:-1.8px;font-weight:500}}p{{line-height:1.7;color:var(--ink,#677065);opacity:.75}}.benefits{{padding:20px 0;line-height:2.9;font-size:13px}}button,.primary{{display:block;border:0;border-radius:var(--radius,8px);background:var(--accent,#52614c);padding:17px 24px;color:white;text-decoration:none;text-align:center;font:inherit;cursor:pointer;margin-top:16px}}.primary{{width:100%}}a{{color:var(--accent)}}label{{display:block;font-size:12px;margin:20px 0}}input{{width:100%;padding:14px;border:1px solid #d5dbd1;border-radius:6px;background:white;margin-top:8px;font:inherit}}details{{font-size:12px;margin:22px 0;color:var(--ink,#677065)}}.text{{background:none;color:var(--accent);padding:0;font-size:12px}}.summary{{background:white;padding:24px;line-height:2.5;font-size:13px}}.summary b{{float:right}}hr{{border:0;border-top:1px solid #e7e9e4}}footer{{text-align:center;font-size:10px;color:#859080;padding:24px}}.revision{{border-left:2px solid var(--accent);padding-left:12px}}{ 'main{max-width:620px;background:white;margin:28px auto;border:1px solid #e1e5df;border-radius:12px}h1{font-size:36px}.benefits{background:#f2f5ef;padding:16px;border-radius:8px}' if style=='b' else ''}</style><header><span class="brand">north<span style="color:var(--accent)">.</span></span><span>EVERYDAY CREDIT &nbsp; / &nbsp; {index+1:02d}</span></header><main><div class="eyebrow">{esc(title)} · Step {index+1} of {len(screens)}</div><h1 data-design-id="heading">{esc(heading)}</h1>{body}<details><summary>Why do we ask for this?</summary>We use this information to show suitable options. No real application is submitted.</details><a class="primary" data-role="primary-action" data-design-id="continue" href="{nextfile}">{'Continue' if index<len(screens)-1 else 'Finish demo'} &nbsp; →</a>{extra}{f'<p><a href="{previous}">← Back</a></p>' if index else ''}</main><footer>Illustrative prototype only · No application will be submitted</footer></html>'''


ALLOWED_OUTPUT = {'.html', '.css', '.js', '.json', '.png', '.jpg', '.jpeg', '.svg', '.woff', '.woff2', '.txt', '.md'}
