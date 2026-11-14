// Scene script. Clip times are seconds in the recorded mp4; `rate` speeds up waiting sections.
export type Seg = { from: number; to: number; rate?: number; clip?: string };
export type Focus = { t: number; s: number; x: number; y: number }; // t = seconds into the scene, s = zoom, x/y = focus point (0..1)
export type Scene = { id: string; kicker: string; title: string; sub?: string; chips?: string[]; clip: string; segs: Seg[]; focus: Focus[]; phone?: boolean };

export const scenes: Scene[] = [
  { id: 'board', kicker: 'Direct', title: 'Direct a team of agents', sub: 'One brief. Claude Code and Codex design it, independently.', chips: ['Real agents', 'Independent variants'], clip: 'board',
    segs: [{ from: 0.8, to: 17.5, rate: 2.3 }], focus: [{ t: 0, s: 1, x: 0.5, y: 0.5 }, { t: 3.4, s: 1.18, x: 0.44, y: 0.55 }] },
  { id: 'generate', kicker: 'Experiment', title: 'Try ideas without breaking the rules', sub: 'Spread directions, switch rules off, test different guideline profiles.', chips: ['Spread', 'Rules vs free', 'Profiles'], clip: 'generate',
    segs: [{ from: 2.5, to: 21, rate: 2.3 }], focus: [{ t: 0, s: 1, x: 0.5, y: 0.5 }, { t: 1.6, s: 1.5, x: 0.5, y: 0.52 }, { t: 5.2, s: 1.5, x: 0.5, y: 0.58 }] },
  { id: 'progress', kicker: 'Watch', title: 'Watch them work', sub: 'Live progress, time and usage while the agents run.', chips: ['Live output', 'Time and usage'], clip: 'progress',
    segs: [{ from: 1, to: 22, rate: 2.7 }], focus: [{ t: 0, s: 1, x: 0.5, y: 0.5 }, { t: 1.4, s: 1.32, x: 0.45, y: 0.5 }] },
  { id: 'compare', kicker: 'Learn', title: 'See what your rules cost', sub: 'The same idea with and without the rules, and a log of every break.', chips: ['Rule-break log', 'Side by side'], clip: 'compare',
    segs: [{ from: 0.8, to: 15.5, rate: 1.8 }], focus: [{ t: 0, s: 1.1, x: 0.8, y: 0.45 }, { t: 2.8, s: 1.6, x: 0.86, y: 0.55 }, { t: 5, s: 1.28, x: 0.5, y: 0.6 }] },
  { id: 'guidelines', kicker: 'Guidelines', title: 'Bring your own guidelines', sub: 'Import DESIGN.md, rules and tokens from your files. Branch a profile to test new rules.', chips: ['DESIGN.md', 'Rules', 'Tokens', 'Profiles'], clip: 'guidelines',
    segs: [{ from: 0.5, to: 12, rate: 3.5 }, { from: 12, to: 30.5, rate: 2.2 }], focus: [{ t: 0, s: 1, x: 0.5, y: 0.5 }, { t: 3.5, s: 1.35, x: 0.5, y: 0.5 }, { t: 7, s: 1.25, x: 0.5, y: 0.6 }] },
  { id: 'review', kicker: 'Review', title: 'Point, don’t prompt', sub: 'Pin feedback on the screen. Only that part is revised, and the studio checks nothing else changed.', chips: ['Pin comments', 'Region-limited revisions'], clip: 'review',
    segs: [{ from: 1, to: 19.5, rate: 2 }], focus: [{ t: 0, s: 1, x: 0.5, y: 0.5 }, { t: 2, s: 1.35, x: 0.45, y: 0.45 }, { t: 4.6, s: 1.5, x: 0.5, y: 0.5 }, { t: 7.5, s: 1.35, x: 0.86, y: 0.6 }] },
  { id: 'audit', kicker: 'Audit', title: 'Audit when you decide', sub: 'Accessibility checks and your own legal and design-review documents. An agent’s opinion is labelled unverified.', chips: ['Accessibility', 'Your documents', 'Never automatic'], clip: 'audit',
    segs: [{ from: 0.5, to: 19, rate: 3 }, { from: 19, to: 41.5, rate: 6 }, { from: 41.5, to: 48.5, rate: 2 }], focus: [{ t: 0, s: 1, x: 0.5, y: 0.5 }, { t: 1.4, s: 1.5, x: 0.88, y: 0.45 }, { t: 6, s: 1.5, x: 0.88, y: 0.62 }, { t: 10, s: 1.45, x: 0.88, y: 0.72 }] },
  { id: 'decisions', kicker: 'Decide', title: 'Decide with a paper trail', sub: 'Approve or set aside with a reason, then share the decision log.', chips: ['Reasons recorded', 'Shareable log'], clip: 'decisions',
    segs: [{ from: 0.5, to: 19.5, rate: 2.4 }, { from: 1, to: 6, rate: 1.6, clip: 'history' }], focus: [{ t: 0, s: 1, x: 0.5, y: 0.5 }, { t: 1.4, s: 1.5, x: 0.5, y: 0.5 }, { t: 6.2, s: 1.0, x: 0.5, y: 0.5 }, { t: 8, s: 1.35, x: 0.55, y: 0.3 }] },
  { id: 'prototype', kicker: 'Ship', title: 'Click through the result', sub: 'An approved design becomes a clickable prototype you can share.', chips: ['Clickable prototype', 'Share link'], clip: 'player',
    segs: [{ from: 1, to: 17.5, rate: 2.6 }], focus: [{ t: 0, s: 1, x: 0.5, y: 0.5 }, { t: 1.8, s: 1.18, x: 0.5, y: 0.55 }] },
  { id: 'phone', kicker: 'Anywhere', title: 'Review from your phone', sub: 'It runs on your computer and opens on your Wi-Fi.', chips: ['Same Wi-Fi', 'No sign-up'], clip: 'phone', phone: true,
    segs: [{ from: 1, to: 18.5, rate: 2.2 }], focus: [] },
];
