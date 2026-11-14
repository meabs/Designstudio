import { describe, expect, it } from 'vitest';
import { ago, contextDiff, diffIsEmpty, esc, fmtDur, renderMarkdown, uuid } from './format';

describe('uuid', () => {
  const re = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
  it('works without crypto.randomUUID (plain-http pages, e.g. a phone on the LAN)', () => {
    const withValues = { getRandomValues: (a: Uint8Array) => { for (let i = 0; i < a.length; i++) a[i] = (i * 37 + 11) & 255; return a; } };
    expect(uuid(withValues)).toMatch(re); expect(uuid({})).toMatch(re); expect(uuid(undefined)).toMatch(re);
    expect(uuid({})).not.toEqual(uuid({}));
  });
});
describe('formatting', () => {
  it('ago reads naturally', () => { expect(ago(1000, 1010)).toBe('just now'); expect(ago(0, 600)).toBe('10 min ago'); expect(ago(0, 7200)).toBe('2 h ago'); expect(ago(0, 86400 * 3)).toBe('3 days ago'); });
  it('fmtDur', () => { expect(fmtDur(0.2)).toBe('<1s'); expect(fmtDur(45)).toBe('45s'); expect(fmtDur(125)).toBe('2m 05s'); expect(fmtDur(null)).toBe(''); });
});
describe('renderMarkdown', () => {
  it('renders headings, lists and emphasis', () => { expect(renderMarkdown('# Rules\n\n- Use **calm** copy')).toMatch(/<h2>Rules<\/h2>.*<strong>calm<\/strong>/s); });
  it('escapes HTML before rendering', () => { const html = renderMarkdown('<img src=x onerror=alert(1)> **b**'); expect(html).not.toContain('<img'); expect(html).toContain('&lt;img'); });
  it('esc escapes the five characters', () => { expect(esc(`<a href="x">'&'</a>`)).toBe('&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;'); });
});
describe('contextDiff', () => {
  it('reports added, removed and changed content; identical versions are empty', () => {
    const a = { markdown: 'one\ntwo', tokens: { accent: '#111', ink: '#000' }, rules: [{ id: 'R1', description: 'x', version: 1 }] };
    const b = { markdown: 'one\nthree', tokens: { accent: '#222', radius: '8px' }, rules: [{ id: 'R1', description: 'y', version: 2 }, { id: 'R2', description: 'z' }] };
    const d = contextDiff(a, b);
    expect(d.markdown).toEqual({ added: ['three'], removed: ['two'] }); expect(d.tokens).toEqual({ added: ['radius'], removed: ['ink'], changed: ['accent'] }); expect(d.rules.added).toEqual(['R2']); expect(d.rules.changed).toEqual(['R1']);
    expect(diffIsEmpty(contextDiff(a, { ...a, rules: [{ id: 'R1', description: 'x', version: 9 }] }))).toBe(true);
    expect(contextDiff(null, b).initial).toBe(true);
  });
});
