import { Composition } from 'remotion';
import { Film, filmFrames } from './Film';
import { FPS } from './theme';

export const Root = () => (
  <>
    <Composition id="Landscape" component={Film} width={1920} height={1080} fps={FPS} durationInFrames={filmFrames()} defaultProps={{ layout: 'landscape' as const }} />
    <Composition id="Portrait" component={Film} width={1080} height={1920} fps={FPS} durationInFrames={filmFrames()} defaultProps={{ layout: 'portrait' as const }} />
  </>
);
