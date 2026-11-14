// What a board's screens are designed for. Mirrors boards.TARGETS on the server; legacy boards (no target) keep 720x960.
export type View = 'd' | 'm';
export const TARGETS: Record<string, { label: string; frames: Record<string, [number, number]> }> = {
  website: { label: 'Website', frames: { d: [1440, 900] } },
  mobile: { label: 'Mobile app', frames: { d: [390, 844] } },
  both: { label: 'Website and mobile app', frames: { d: [1440, 900], m: [390, 844] } },
};
export const MAX_SCREENS = 12;
export const frameOf = (b: any, view: View = 'd'): { w: number; h: number } => { const t = TARGETS[b?.target]; if (!t) return { w: 720, h: 960 }; const [w, h] = t.frames[view] || t.frames.d; return { w, h }; };
export const hasPhoneView = (b: any) => b?.target === 'both';
export const cardWidth = (b: any) => (b?.target === 'mobile' ? 170 : TARGETS[b?.target] ? 340 : 260);
export const reviewBase = (b: any, view: View = 'd') => { const { w } = frameOf(b, view); return w >= 1000 ? 900 : w <= 400 ? 340 : 560; };
export const targetLabel = (b: any) => TARGETS[b?.target]?.label || '';
