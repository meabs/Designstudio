import React from 'react';
import { AbsoluteFill, Audio, Easing, interpolate, OffthreadVideo, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { TransitionSeries, linearTiming } from '@remotion/transitions';
import { fade } from '@remotion/transitions/fade';
import { slide } from '@remotion/transitions/slide';
import { C, FPS, fontFamily } from './theme';
import { scenes, type Scene } from './scenes';

type Layout = 'landscape' | 'portrait';
const T = 14; // transition frames
const HOOK = Math.round(6.2 * FPS);
const END = Math.round(8 * FPS);
const segFrames = (s: Scene) => s.segs.map((g) => Math.max(1, Math.round(((g.to - g.from) / (g.rate ?? 1)) * FPS)));
const sceneFrames = (s: Scene) => segFrames(s).reduce((a, b) => a + b, 0);
export const filmFrames = () => HOOK + END + scenes.reduce((a, s) => a + sceneFrames(s), 0) - T * (scenes.length + 1);

const ease = Easing.inOut(Easing.cubic);

/* ---------- background ---------- */
const Background: React.FC<{ layout: Layout }> = ({ layout }) => {
  const f = useCurrentFrame(); const w = layout === 'landscape' ? 1920 : 1080; const h = layout === 'landscape' ? 1080 : 1920;
  const a = f / 240;
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <div style={{ position: 'absolute', width: w * 0.9, height: w * 0.9, left: -w * 0.2 + Math.sin(a) * 60, top: -h * 0.25 + Math.cos(a * 0.8) * 50, borderRadius: '50%', background: 'radial-gradient(closest-side, rgba(139,155,255,.32), transparent)', filter: 'blur(30px)' }} />
      <div style={{ position: 'absolute', width: w * 0.8, height: w * 0.8, right: -w * 0.25 + Math.cos(a) * 60, bottom: -h * 0.3 + Math.sin(a * 0.7) * 50, borderRadius: '50%', background: 'radial-gradient(closest-side, rgba(94,234,212,.2), transparent)', filter: 'blur(30px)' }} />
      <AbsoluteFill style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px)', backgroundSize: '64px 64px', maskImage: 'radial-gradient(ellipse at center, black 30%, transparent 80%)' }} />
    </AbsoluteFill>
  );
};

/* ---------- the recorded clip with camera moves and speed ramps ---------- */
const Camera: React.FC<{ scene: Scene; bw: number; bh: number; portrait?: boolean }> = ({ scene, bw, bh, portrait }) => {
  const f = useCurrentFrame(); const t = f / FPS; const fk = scene.focus.length ? scene.focus : [{ t: 0, s: 1, x: 0.5, y: 0.5 }];
  const ts = fk.map((k) => k.t); const at = (key: 's' | 'x' | 'y') => (ts.length === 1 ? fk[0][key] : interpolate(t, ts, fk.map((k) => k[key]), { easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }));
  const s0 = at('s'), fx = at('x'), fy = at('y'); const s = portrait ? 1 + (s0 - 1) * 0.35 : s0; const base = Math.max(bw / 1920, bh / 1080); const k = base * s;
  const left = Math.min(0, Math.max(bw - 1920 * k, bw / 2 - fx * 1920 * k)); const top = Math.min(0, Math.max(bh - 1080 * k, bh / 2 - fy * 1080 * k));
  let acc = 0; const fr = segFrames(scene);
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', background: '#fff' }}>
      <div style={{ position: 'absolute', width: 1920, height: 1080, transform: `translate(${left}px, ${top}px) scale(${k})`, transformOrigin: '0 0' }}>
        {scene.segs.map((g, i) => { const from = acc; acc += fr[i]; return (
          <Sequence key={i} from={from} durationInFrames={fr[i]} layout="none">
            <OffthreadVideo src={staticFile(`clips/${g.clip ?? scene.clip}.mp4`)} startFrom={Math.round(g.from * FPS)} playbackRate={g.rate ?? 1} muted style={{ width: 1920, height: 1080 }} />
          </Sequence>); })}
      </div>
    </div>
  );
};

const Sweep: React.FC<{ w: number; h: number; radius: number }> = ({ w, h, radius }) => {
  const f = useCurrentFrame(); const x = interpolate(f, [4, 34], [-w * 0.6, w * 1.2], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  return <div style={{ position: 'absolute', inset: 0, borderRadius: radius, overflow: 'hidden', pointerEvents: 'none' }}><div style={{ position: 'absolute', top: -h * 0.2, height: h * 1.4, width: w * 0.35, left: x, transform: 'rotate(18deg)', background: 'linear-gradient(90deg, transparent, rgba(255,255,255,.34), transparent)' }} /></div>;
};

/* ---------- headings ---------- */
const Heading: React.FC<{ scene: Scene; index: number; layout: Layout }> = ({ scene, index, layout }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const p = (d: number) => spring({ frame: f - d, fps, config: { damping: 200 } });
  const land = layout === 'landscape';
  const row = (d: number): React.CSSProperties => ({ opacity: p(d), transform: `translateY(${(1 - p(d)) * 22}px)` });
  return (
    <div style={{ fontFamily, color: C.text, position: 'absolute', left: land ? 232 : 70, top: land ? 38 : 130, width: land ? 1456 : 940 }}>
      <div style={{ ...row(0), display: 'flex', alignItems: 'center', gap: 14, color: C.accent, fontWeight: 700, letterSpacing: 4, fontSize: land ? 19 : 28, textTransform: 'uppercase' }}><span style={{ color: C.muted }}>{String(index + 1).padStart(2, '0')}</span>{scene.kicker}</div>
      <div style={{ ...row(5), fontSize: land ? 56 : 84, lineHeight: 1.04, fontWeight: 800, letterSpacing: -2, marginTop: land ? 6 : 16 }}>{scene.title}</div>
      {scene.sub && !land && <div style={{ ...row(10), fontSize: 36, color: C.muted, fontWeight: 500, marginTop: 20, lineHeight: 1.3 }}>{scene.sub}</div>}
    </div>
  );
};
const Caption: React.FC<{ scene: Scene; layout: Layout }> = ({ scene, layout }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const p = spring({ frame: f - 22, fps, config: { damping: 200 } }); const land = layout === 'landscape';
  if (!scene.sub && !scene.chips?.length) return null;
  const chips = (scene.chips || []).map((c, i) => <span key={i} style={{ background: 'rgba(139,155,255,.16)', border: '1px solid rgba(139,155,255,.4)', color: '#dfe3ff', padding: land ? '7px 15px' : '12px 22px', borderRadius: 999, fontSize: land ? 19 : 30, fontWeight: 600, whiteSpace: 'nowrap', opacity: spring({ frame: f - 28 - i * 5, fps, config: { damping: 200 } }) }}>{c}</span>);
  if (land) return (
    <div style={{ position: 'absolute', left: 232, top: 976, width: 1456, opacity: p, transform: `translateY(${(1 - p) * 14}px)`, fontFamily, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 28 }}>
      <div style={{ color: C.text, fontSize: 24, fontWeight: 600, lineHeight: 1.3, maxWidth: 980 }}>{scene.sub}</div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'flex-end' }}>{chips}</div>
    </div>
  );
  return <div style={{ position: 'absolute', left: 70, right: 70, bottom: 150, opacity: p, transform: `translateY(${(1 - p) * 16}px)`, fontFamily, display: 'flex', gap: 10, flexWrap: 'wrap' }}>{chips}</div>;
};

/* ---------- scenes ---------- */
const WindowScene: React.FC<{ scene: Scene; index: number; layout: Layout }> = ({ scene, index, layout }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const land = layout === 'landscape';
  const bw = land ? 1456 : 1000, bh = land ? 819 : 900; const pop = spring({ frame: f - 3, fps, config: { damping: 22, stiffness: 120 } });
  return (
    <AbsoluteFill>
      <Heading scene={scene} index={index} layout={layout} />
      <div style={{ position: 'absolute', left: land ? 232 : 40, top: land ? 146 : 600, width: bw, height: bh, borderRadius: 22, overflow: 'hidden', transform: `scale(${0.94 + 0.06 * pop})`, opacity: pop, boxShadow: '0 40px 120px rgba(0,0,0,.65), 0 0 0 1px rgba(255,255,255,.14)' }}>
        <Camera scene={scene} bw={bw} bh={bh} portrait={!land} />
        <Sweep w={bw} h={bh} radius={22} />
      </div>
      <Caption scene={scene} layout={layout} />
    </AbsoluteFill>
  );
};
const PhoneScene: React.FC<{ scene: Scene; index: number; layout: Layout }> = ({ scene, index, layout }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const land = layout === 'landscape'; const pop = spring({ frame: f - 3, fps, config: { damping: 20, stiffness: 100 } });
  const H = land ? 960 : 1060; const W = Math.round(H * (860 / 1864)); const x = land ? 1920 - W - 250 : (1080 - W) / 2; const y = land ? 60 : 600;
  let acc = 0; const fr = segFrames(scene);
  return (
    <AbsoluteFill>
      {land ? <div style={{ fontFamily, color: C.text, position: 'absolute', left: 176, top: 330, width: 800 }}>
        <div style={{ color: C.accent, fontWeight: 700, letterSpacing: 4, fontSize: 19, textTransform: 'uppercase', marginBottom: 12 }}><span style={{ color: C.muted }}>{String(index + 1).padStart(2, '0')}</span>&nbsp;&nbsp;{scene.kicker}</div>
        <div style={{ fontSize: 74, lineHeight: 1.02, fontWeight: 800, letterSpacing: -2.5 }}>{scene.title}</div>
        {scene.sub && <div style={{ fontSize: 30, color: C.muted, marginTop: 24, lineHeight: 1.35, fontWeight: 500 }}>{scene.sub}</div>}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 30 }}>{(scene.chips || []).map((c, i) => <span key={i} style={{ background: 'rgba(139,155,255,.16)', border: '1px solid rgba(139,155,255,.4)', color: '#dfe3ff', padding: '9px 18px', borderRadius: 999, fontSize: 21, fontWeight: 600 }}>{c}</span>)}</div>
      </div> : <Heading scene={scene} index={index} layout={layout} />}
      <div style={{ position: 'absolute', left: x, top: y, width: W + 28, height: H + 28, padding: 14, borderRadius: 74, background: 'linear-gradient(145deg,#2a2d38,#0c0d12)', boxShadow: '0 50px 120px rgba(0,0,0,.7), inset 0 0 0 2px rgba(255,255,255,.12)', transform: `translateY(${(1 - pop) * 60}px) scale(${0.95 + 0.05 * pop})`, opacity: pop }}>
        <div style={{ width: W, height: H, borderRadius: 60, overflow: 'hidden', position: 'relative', background: '#fff' }}>
          {scene.segs.map((g, i) => { const from = acc; acc += fr[i]; return (<Sequence key={i} from={from} durationInFrames={fr[i]} layout="none"><OffthreadVideo src={staticFile(`clips/${g.clip ?? scene.clip}.mp4`)} startFrom={Math.round(g.from * FPS)} playbackRate={g.rate ?? 1} muted style={{ width: W, height: H, objectFit: 'cover' }} /></Sequence>); })}
        </div>
        <div style={{ position: 'absolute', top: 24, left: '50%', width: 110, height: 30, marginLeft: -55, borderRadius: 20, background: '#06070a' }} />
      </div>
    </AbsoluteFill>
  );
};

const Hook: React.FC<{ layout: Layout }> = ({ layout }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const land = layout === 'landscape';
  const lines = [{ t: 'AI agents can design.', at: 6, c: C.text }, { t: 'But who is in charge?', at: 62, c: C.muted }, { t: 'You are.', at: 118, c: 'grad' }];
  return (
    <AbsoluteFill style={{ fontFamily, alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
      {lines.map((l, i) => { const show = spring({ frame: f - l.at, fps, config: { damping: 18, stiffness: 110 } }); const hideAt = i < 2 ? lines[i + 1].at : 9999; const gone = interpolate(f, [hideAt - 2, hideAt + 10], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        return <div key={i} style={{ position: 'absolute', fontSize: land ? 112 : 112, fontWeight: 800, letterSpacing: -4, lineHeight: 1.05, width: land ? 1600 : 900, opacity: show * (i < 2 ? gone : 1), transform: `translateY(${(1 - show) * 40}px) scale(${0.96 + 0.04 * show})`, color: l.c === 'grad' ? 'transparent' : l.c, ...(l.c === 'grad' ? { backgroundImage: `linear-gradient(90deg, ${C.accent}, ${C.teal})`, WebkitBackgroundClip: 'text' } : {}) }}>{l.t}</div>; })}
    </AbsoluteFill>
  );
};

const Mark: React.FC<{ size: number }> = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 64 64"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor={C.accent} /><stop offset="1" stopColor={C.teal} /></linearGradient></defs><rect x="2" y="2" width="60" height="60" rx="16" fill="url(#g)" /><rect x="14" y="16" width="36" height="32" rx="5" fill="none" stroke="#0a0b10" strokeWidth="4" /><path d="M14 27h36M27 27v21" stroke="#0a0b10" strokeWidth="4" /></svg>
);
const End: React.FC<{ layout: Layout }> = ({ layout }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const land = layout === 'landscape'; const p = (d: number) => spring({ frame: f - d, fps, config: { damping: 200 } });
  const chips = ['Claude Code + Codex', 'Your rules, your files', 'Runs on your machine', 'No Docker · No sign-up'];
  return (
    <AbsoluteFill style={{ fontFamily, alignItems: 'center', justifyContent: 'center', textAlign: 'center', color: C.text }}>
      <div style={{ opacity: p(0), transform: `scale(${0.8 + 0.2 * p(0)})` }}><Mark size={land ? 130 : 160} /></div>
      <div style={{ fontSize: land ? 108 : 120, fontWeight: 800, letterSpacing: -4, marginTop: 28, opacity: p(8), transform: `translateY(${(1 - p(8)) * 24}px)` }}>Design Studio</div>
      <div style={{ fontSize: land ? 40 : 44, color: C.muted, fontWeight: 500, marginTop: 14, opacity: p(18), width: land ? 1400 : 900, lineHeight: 1.25 }}>Direct AI agents. Keep the judgment.</div>
      <div style={{ display: 'flex', gap: 12, marginTop: 56, flexWrap: 'wrap', justifyContent: 'center', width: land ? 1500 : 920 }}>{chips.map((c, i) => <span key={i} style={{ opacity: p(32 + i * 6), transform: `translateY(${(1 - p(32 + i * 6)) * 14}px)`, background: 'rgba(255,255,255,.07)', border: `1px solid ${C.line}`, padding: land ? '12px 24px' : '14px 26px', borderRadius: 999, fontSize: land ? 26 : 30, fontWeight: 600 }}>{c}</span>)}</div>
    </AbsoluteFill>
  );
};

/* ---------- film ---------- */
export const Film: React.FC<{ layout: Layout }> = ({ layout }) => {
  const total = filmFrames(); const len = (frames: number) => frames;
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <Background layout={layout} />
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={len(HOOK)}><Hook layout={layout} /></TransitionSeries.Sequence>
        {scenes.flatMap((s, i) => [
          <TransitionSeries.Transition key={'t' + i} presentation={i % 3 === 2 ? slide({ direction: 'from-right' }) : fade()} timing={linearTiming({ durationInFrames: T })} />,
          <TransitionSeries.Sequence key={'s' + i} durationInFrames={sceneFrames(s)}>{s.phone ? <PhoneScene scene={s} index={i} layout={layout} /> : <WindowScene scene={s} index={i} layout={layout} />}</TransitionSeries.Sequence>,
        ])}
        <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: T })} />
        <TransitionSeries.Sequence durationInFrames={END}><End layout={layout} /></TransitionSeries.Sequence>
      </TransitionSeries>
      <Audio src={staticFile('music.mp3')} volume={(f) => Math.min(0.55, interpolate(f, [0, 45], [0, 0.55], { extrapolateRight: 'clamp' })) * interpolate(f, [total - 75, total - 5], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })} />
    </AbsoluteFill>
  );
};
