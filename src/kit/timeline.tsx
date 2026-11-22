import React from "react";
import { AbsoluteFill, Audio, interpolate, Sequence, staticFile, useCurrentFrame as useFrame } from "remotion";
import { Drift } from "./core";

type Word = { w: string; t: number; e: number };
export type Timing = { id: string; scenes: { id: string; beats: { text: string; file: string; dur: number; words?: Word[] }[] }[] };
/**
 * b[i] = frame where beat i starts, e[i] = frame where it ends (scene-relative).
 * w(i, "word", nth) = frame where that word is spoken inside beat i (prefix match, punctuation ignored).
 */
export type SceneCtx = { b: number[]; e: number[]; len: number; w: (beat: number, word: string, nth?: number) => number };
export type SceneDef = { render: (c: SceneCtx) => React.ReactNode; drift?: number };

export const FPS = 30;
const LEAD = 0.45; // s before first beat of a scene
const GAP = 0.32; // s between beats
const TAIL = 0.85; // s after last beat
export const XF = 12; // crossfade frames between scenes

type BuiltBeat = { start: number; len: number; file: string; text: string; words: Word[] };
export type Built = { scenes: { id: string; from: number; len: number; beats: BuiltBeat[] }[]; total: number };

export const buildTimeline = (t: Timing, extraTail: Record<string, number> = {}): Built => {
  let cursor = 0;
  const scenes = t.scenes.map((s) => {
    let local = Math.round(LEAD * FPS);
    const beats = s.beats.map((b) => {
      const start = local;
      const len = Math.round(b.dur * FPS);
      local += len + Math.round(GAP * FPS);
      return { start, len, file: b.file, text: b.text, words: b.words ?? [] };
    });
    const len = local - Math.round(GAP * FPS) + Math.round((TAIL + (extraTail[s.id] ?? 0)) * FPS);
    const sc = { id: s.id, from: cursor, len, beats };
    cursor += len;
    return sc;
  });
  return { scenes, total: cursor + XF };
};

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

const makeWordLookup = (sceneId: string, beats: BuiltBeat[], pre: number) => (bi: number, word: string, nth = 1) => {
  const beat = beats[bi];
  if (!beat) throw new Error(`${sceneId}: no beat ${bi}`);
  const needle = norm(word);
  let seen = 0;
  for (const wd of beat.words) {
    if (norm(wd.w).startsWith(needle) && ++seen === nth) return beat.start + pre + Math.round(wd.t * FPS);
  }
  // fallback: estimate from character position in the beat text
  const idx = beat.text.toLowerCase().indexOf(word.toLowerCase());
  if (idx < 0) throw new Error(`${sceneId}: word "${word}" not in beat ${bi}`);
  return beat.start + pre + Math.round((idx / beat.text.length) * beat.len);
};

const FadeIn: React.FC<{ first: boolean; children: React.ReactNode }> = ({ first, children }) => {
  // incoming scene fades over the (still fully opaque) outgoing scene, a clean crossfade with no dip
  const f = useFrame();
  const op = first ? 1 : interpolate(f, [0, XF], [0, 1], { extrapolateRight: "clamp" });
  return <AbsoluteFill style={{ opacity: op }}>{children}</AbsoluteFill>;
};

/** A music cue: plays `src` from scene `from` to the end of scene `to` (inclusive), crossfading at both ends. */
export type Cue = { src: string; from: string; to: string; vol?: number; offset?: number };
/** A one-shot cinematic hit at a scene-relative frame (use the scene's word anchor). */
export type Hit = { scene: string; at: (c: { b: number[]; w: (beat: number, word: string, nth?: number) => number }) => number; src: string; vol?: number };

// owner 2026-11-02: score must sit VERY low, never drown the voice, but still be felt as a layer
const MUSIC_BASE = 0.11; // when nobody is talking
const MUSIC_DUCK = 0.38; // multiplier while the narrator speaks
const DUCK_RAMP = 9; // frames

/** 1 when the narrator is silent, MUSIC_DUCK while speaking, with smooth ramps. */
const duckAt = (built: Built, f: number) => {
  let near = Infinity;
  for (const sc of built.scenes)
    for (const bt of sc.beats) {
      const s = sc.from + bt.start, e = s + bt.len;
      if (f >= s && f <= e) return MUSIC_DUCK;
      near = Math.min(near, f < s ? s - f : f - e);
    }
  return MUSIC_DUCK + (1 - MUSIC_DUCK) * Math.min(1, near / DUCK_RAMP);
};

const sceneSpan = (built: Built, from: string, to: string) => {
  const a = built.scenes.find((s) => s.id === from), b = built.scenes.find((s) => s.id === to);
  if (!a || !b) throw new Error(`cue scenes ${from}..${to} not found`);
  return { start: a.from, end: b.from + b.len };
};

export const EpisodePlayer: React.FC<{ built: Built; defs: Record<string, SceneDef>; drone?: number; score?: Cue[]; hits?: Hit[] }> = ({ built, defs, drone = 0.16, score, hits }) => (
  <AbsoluteFill style={{ background: "#050505" }}>
    {built.scenes.map((sc, i) => {
      const def = defs[sc.id];
      if (!def) throw new Error(`no scene renderer for ${sc.id}`);
      const pre = i === 0 ? 0 : XF; // visuals start XF early so they crossfade over the previous scene
      const ctx: SceneCtx = {
        b: sc.beats.map((bt) => bt.start + pre),
        e: sc.beats.map((bt) => bt.start + bt.len + pre),
        len: sc.len + pre,
        w: makeWordLookup(sc.id, sc.beats, pre),
      };
      return (
        <Sequence key={sc.id} from={sc.from - pre} durationInFrames={sc.len + pre + XF} name={sc.id}>
          <FadeIn first={i === 0}>
            <Drift len={sc.len + pre + XF} amount={def.drift ?? 0.03} seed={i}>
              {def.render(ctx)}
            </Drift>
          </FadeIn>
        </Sequence>
      );
    })}
    {/* narration track, independent of visuals */}
    {built.scenes.flatMap((sc) =>
      sc.beats.map((bt, j) => (
        <Sequence key={`${sc.id}-vo${j}`} from={sc.from + bt.start} durationInFrames={bt.len + 6} layout="none">
          <Audio src={staticFile(bt.file)} />
        </Sequence>
      )),
    )}
    {/* score: mood cues, ducked under the narration; falls back to the ambient drone when no cues are given */}
    {score && score.length > 0
      ? score.map((c, i) => {
          const { start, end } = sceneSpan(built, c.from, c.to);
          const len = end - start + 45;
          const v = c.vol ?? 1;
          return (
            <Sequence key={`cue${i}`} from={Math.max(0, start - 15)} durationInFrames={len} layout="none">
              <Audio loop src={staticFile(c.src)} startFrom={c.offset ?? 0}
                volume={(f) => MUSIC_BASE * v * duckAt(built, f + start - 15) *
                  interpolate(f, [0, 45, len - 60, len], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />
            </Sequence>
          );
        })
      : <Audio loop src={staticFile("sfx/drone.mp3")} volume={(f) => interpolate(f, [0, 60, built.total - 90, built.total], [0, drone, drone, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />}
    {/* cinematic hits on big reveals */}
    {(hits ?? []).map((h, i) => {
      const sc = built.scenes.find((s) => s.id === h.scene);
      if (!sc) throw new Error(`hit scene ${h.scene} not found`);
      const idx = built.scenes.indexOf(sc);
      const pre = idx === 0 ? 0 : XF;
      const at = h.at({ b: sc.beats.map((bt) => bt.start + pre), w: makeWordLookup(sc.id, sc.beats, pre) }) + sc.from - pre;
      return (
        <Sequence key={`hit${i}`} from={Math.max(0, at)} durationInFrames={150} layout="none">
          <Audio src={staticFile(`sfx/${h.src}`)} volume={h.vol ?? 0.5} />
        </Sequence>
      );
    })}
  </AbsoluteFill>
);
