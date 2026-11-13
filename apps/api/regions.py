"""HTML region helpers: locate elements by data-design-id, diff revisions per element, stamp anchors."""

from html.parser import HTMLParser
import re, html

# ---- HTML regions: locate elements by data-design-id, diff revisions per element ----
VOID_TAGS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}


def element_spans(html_text):
    # {design_id: (start, end)} character offsets of each element's outerHTML.
    starts = [0] + [m.end() for m in re.finditer('\n', html_text)]
    off = lambda pos: starts[pos[0] - 1] + pos[1]

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.stack = []
            self.spans = {}

        def handle_starttag(self, tag, attrs):
            start = off(self.getpos())
            did = dict(attrs).get('data-design-id')
            if tag in VOID_TAGS:
                if did:
                    self.spans.setdefault(did, (start, start + len(self.get_starttag_text())))
                return
            self.stack.append((tag, did, start))

        def handle_endtag(self, tag):
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    _, did, start = self.stack[i]
                    end = html_text.find('>', off(self.getpos())) + 1
                    if did:
                        self.spans.setdefault(did, (start, end))
                    del self.stack[i:]
                    break

    p = P()
    p.feed(html_text)
    p.close()
    return p.spans


def _masked(text, spans, inside=None):
    # Replace nested identified elements by placeholders so a change is attributed to the innermost element that really differs.
    lo, hi = inside if inside else (0, len(text))
    items = sorted(((a, b, i) for i, (a, b) in spans.items() if lo <= a and b <= hi and (a, b) != (lo, hi)))
    out = []
    pos = lo
    for a, b, i in items:
        if a < pos:
            continue
        out.append(text[pos:a])
        out.append(f'\u27e6{i}\u27e7')
        pos = b
    out.append(text[pos:hi])
    return re.sub(r'\s+', ' ', ''.join(out)).strip()


def diff_regions(before, after):
    # {'elements': ids whose own content changed, 'outside': content changed outside any identified element}
    sb, sa = element_spans(before), element_spans(after)
    changed = []
    for i in sorted(set(sb) | set(sa)):
        if i not in sb or i not in sa or _masked(before, sb, sb[i]) != _masked(after, sa, sa[i]):
            changed.append(i)
    return {'elements': changed, 'outside': _masked(before, sb) != _masked(after, sa)}


def region_revise(html_text, notes):
    # Fixture behaviour: edit only the targeted elements (append a visible revision note inside each).
    for did, comment in notes.items():
        spans = element_spans(html_text)
        if did not in spans:
            return None
        a, b = spans[did]
        seg = html_text[a:b]
        close = seg.rfind('</')
        if close < 0:
            return None
        html_text = (
            html_text[:a]
            + seg[:close]
            + f' <small class="revision-note" data-revised="{html.escape(did)}">· {html.escape(comment)}</small>'
            + seg[close:]
            + html_text[b:]
        )
    return html_text


def stamp_anchors(html_text):
    # Adds data-design-id to common elements when an agent emitted none, so pins can target elements. Returns (html, count).
    if 'data-design-id' in html_text:
        return html_text, 0
    tags = {
        'h1',
        'h2',
        'h3',
        'h4',
        'h5',
        'h6',
        'p',
        'a',
        'button',
        'label',
        'input',
        'select',
        'textarea',
        'img',
        'form',
        'section',
        'article',
        'header',
        'footer',
        'main',
        'nav',
        'aside',
        'ul',
        'ol',
        'li',
        'table',
        'figure',
        'details',
        'summary',
    }
    starts = [0] + [m.end() for m in re.finditer('\n', html_text)]
    spots = []
    counts = {}

    class P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag not in tags:
                return
            text = self.get_starttag_text()
            line, col = self.getpos()
            a = starts[line - 1] + col
            end = a + len(text) - 1
            if text.endswith('/>'):
                end -= 1
            counts[tag] = counts.get(tag, 0) + 1
            spots.append((end, f' data-design-id="auto-{tag}-{counts[tag]}"'))

    P(convert_charrefs=False).feed(html_text)
    for pos, attr in sorted(spots, reverse=True):
        html_text = html_text[:pos] + attr + html_text[pos:]
    return html_text, len(spots)
