# Design Studio promo video

Remotion project that renders the promo (landscape 1920×1080 and portrait 1080×1920). The footage is the real app, recorded by script.

```
npm install
# 1. demo data: a throwaway Design Studio on :5196 with real Claude Code + Codex runs (see record/ and ../README)
# 2. record the clips (Chrome screencast -> ffmpeg), e.g.
# the demo server needs STUDIO_FOLDER_ROOTS=/tmp so it may read the sample brand and review folders
node record/scenes.mjs board generate progress compare guidelines review audit decisions phone
# 3. music (original, synthesised with ffmpeg)
python3 music.py
# 4. preview / render
npm run studio
npm run render        # out/design-studio-landscape.mp4 and out/design-studio-portrait.mp4
```

`src/scenes.ts` is the script: each scene names a clip, which sections to use (with speed-ups for waits) and camera moves.
`narration.md` is a voiceover script if you want to add one. Recorded clips, `out/` and `node_modules/` are git-ignored.
