import React from "react";
import { AbsoluteFill, Audio, Easing, interpolate, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont as loadSerif } from "@remotion/google-fonts/InstrumentSerif";
import { loadFont as loadMono } from "@remotion/google-fonts/IBMPlexMono";
import { loadFont as loadCond } from "@remotion/google-fonts/Oswald";
import { loadFont as loadSans } from "@remotion/google-fonts/Inter";

export const SERIF = loadSerif("normal", { weights: ["400"], subsets: ["latin"] }).fontFamily;
export const SERIF_I = loadSerif("italic", { weights: ["400"], subsets: ["latin"] }).fontFamily;
export const MONO = loadMono("normal", { weights: ["400", "500", "600"], subsets: ["latin"] }).fontFamily;
export const COND = loadCond("normal", { weights: ["500", "600", "700"], subsets: ["latin"] }).fontFamily;
export const SANS = loadSans("normal", { weights: ["400", "500", "600", "700"], subsets: ["latin"] }).fontFamily;

/** 0→1 eased progress starting at frame `at` (scene-relative), settling over `dur` frames. */
export const useIn = (at: number, dur = 20) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: f - at, fps, config: { damping: 200 }, durationInFrames: dur });
};

/** Linear-ish eased progress for drawing lines / counters. */
export const useDraw = (at: number, dur = 24, ease = Easing.bezier(0.33, 0, 0.2, 1)) => {
  const f = useCurrentFrame();
  return interpolate(f, [at, at + dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
};

/** Standard "settle in" transform: fade + rise + tiny scale. */
export const enterStyle = (p: number, rise = 24): React.CSSProperties => ({
  opacity: p,
  transform: `translateY(${(1 - p) * rise}px) scale(${0.985 + 0.015 * p})`,
});

export const Sfx: React.FC<{ at: number; src: string; volume?: number }> = ({ at, src, volume = 0.5 }) => (
  <Sequence from={Math.max(0, Math.round(at))} durationInFrames={45} layout="none">
    <Audio src={staticFile(`sfx/${src}`)} volume={volume} />
  </Sequence>
);

/** Slow documentary camera drift applied to a whole scene. */
export const Drift: React.FC<{ len: number; children: React.ReactNode; amount?: number; seed?: number }> = ({ len, children, amount = 0.035, seed = 0 }) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [0, Math.max(1, len)], [0, 1], { extrapolateRight: "clamp" });
  const dir = seed % 2 === 0 ? 1 : -1;
  return (
    <AbsoluteFill style={{ transform: `scale(${1 + amount * t}) translate(${dir * 14 * t}px, ${-8 * t}px)` }}>
      {children}
    </AbsoluteFill>
  );
};

/** Deterministic pseudo-random. */
export const rand = (n: number) => {
  const x = Math.sin(n * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
};
