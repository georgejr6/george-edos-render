/**
 * George Edos tutorial kit: faceless Claude tutorials. Dark UI, a simulated Claude Code terminal that TYPES the exact
 * text from the script, STEP flashes, callout pills, one-word captions (Shorts, 1080x1920) or karaoke captions (long, 1920x1080).
 * Schema: episodes/SHORTS_SCHEMA.md (section "Tutorial cards"). Independent of the Novam kits.
 */
import React from "react";
import { AbsoluteFill, Audio, interpolate, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { MONO, SANS, rand } from "./core";
import { CLAUDE_PATH } from "./claude_logo_path";
import { Timing } from "./timeline";

export const TFPS = 30;
const LEAD = 8, GAP = 1, TAIL = 10; // frames (each narration file already carries its own breath)

const C = {
  bg: "#0b0c10", panel: "#12141a", bar: "#1a1d25", line: "#272b36", text: "#e9ebf1", dim: "#7b8394",
  accent: "#D97757", green: "#5ad19a", red: "#ff6464", blue: "#7aa7ff", yellow: "#f3c969",
};

/* ------------------------------------------------------------------ types */
type TLine = { k: "cmd" | "out" | "dim" | "ok" | "file" | "user" | "claude" | "tree" | "blank" | "paste"; t: string; beat?: number; cps?: number; c?: string; fast?: boolean };
type Pill = { text: string; beat: number; tone?: "red" | "green" };
export type TScene = {
  id: string; beats: string[]; chapter?: string; hold?: number; red?: string[];
  step?: { n: number; title: string }; pills?: Pill[];
  card: any;
};
export type TScript = { id: string; format: string; kind: "long" | "short"; title: string; music?: string; musicVol?: number; url?: string; scenes: TScene[] };

type Word = { w: string; t: number; e: number };
type Beat = { start: number; len: number; file: string; text: string; words: Word[] };
type BScene = { id: string; from: number; len: number; beats: Beat[] };

export const buildTutorial = (script: TScript, t: Timing) => {
  let cur = 0;
  const scenes: BScene[] = t.scenes.map((s, i) => {
    let local = LEAD;
    const beats = s.beats.map((b) => {
      const st = local, len = Math.round(b.dur * TFPS);
      local += len + GAP;
      return { start: st, len, file: b.file, text: b.text, words: b.words ?? [] };
    });
    const hold = Math.round((script.scenes[i]?.hold ?? 0) * TFPS);
    const len = local - GAP + TAIL + hold;
    const sc = { id: s.id, from: cur, len, beats };
    cur += len;
    return sc;
  });
  return { scenes, total: cur + 6 };
};

/* ------------------------------------------------------------------ layout */
type Lay = {
  long: boolean; W: number; H: number; fs: number; lh: number;
  term: { x: number; y: number; w: number; h: number };
  headY: number; pillY: number; capY: number; big: number; mid: number; small: number;
};
const layout = (w: number, h: number): Lay =>
  w > h
    ? { long: true, W: w, H: h, fs: 31, lh: 45, term: { x: 160, y: 150, w: 1600, h: 640 }, headY: 44, pillY: 812, capY: 892, big: 118, mid: 56, small: 30 }
    : { long: false, W: w, H: h, fs: 37, lh: 55, term: { x: 44, y: 230, w: 992, h: 1040 }, headY: 70, pillY: 1310, capY: 1480, big: 108, mid: 56, small: 34 };

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const pop = (f: number, at: number, fps = TFPS) => spring({ frame: f - at, fps, config: { damping: 14, stiffness: 190, mass: 0.6 } });
const ease = (f: number, at: number, dur = 14) => interpolate(f, [at, at + dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: (x) => 1 - Math.pow(1 - x, 3) });

/** spoken forms in the script text -> what the captions should show */
const showText = (s: string) =>
  s.replace(/SKILL dot M D/gi, "SKILL.md").replace(/M K dir/g, "mkdir").replace(/\bC D\b/g, "cd").replace(/dot claude/gi, ".claude");

/* ------------------------------------------------------------------ terminal plan */
type Plan = { line: TLine; rows: [number, number][]; colors: string[]; start: number; dur: number; printed: boolean; num: number };
const PREFIX: Record<string, string> = { cmd: "$ ", user: "> ", claude: "● ", ok: "✓ " };
const typedKinds = new Set(["cmd", "user", "file"]);

const lineColors = (l: TLine): string[] => {
  const t = l.t, out = new Array(t.length).fill(C.text);
  const paint = (a: number, b: number, c: string) => { for (let i = a; i < Math.min(b, t.length); i++) out[i] = c; };
  if (l.c === "accent") { paint(0, t.length, C.accent); return out; }
  if (l.c === "dim") { paint(0, t.length, C.dim); return out; }
  if (l.c === "red") { paint(0, t.length, C.red); return out; }
  if (l.k === "file") {
    if (/^---/.test(t)) paint(0, t.length, C.dim);
    else if (/^#{1,3} /.test(t)) paint(0, t.length, C.accent);
    else if (/^(name|description):/.test(t)) { const i = t.indexOf(":") + 1; paint(0, i, C.blue); }
    else if (/^\d+\. /.test(t)) paint(0, t.indexOf(" "), C.accent);
    else if (/^- /.test(t)) paint(0, 1, C.accent);
    for (const m of t.matchAll(/\[[^\]]+\]/g)) paint(m.index ?? 0, (m.index ?? 0) + m[0].length, C.dim);
  } else if (l.k === "cmd") paint(0, t.length, C.text);
  else if (l.k === "dim") paint(0, t.length, C.dim);
  else if (l.k === "ok") paint(0, t.length, C.green);
  else if (l.k === "tree") paint(0, t.length, C.blue);
  else if (l.k === "paste") paint(0, t.length, "#aab2c3");
  return out;
};

const wrap = (t: string, cols: number): [number, number][] => {
  if (t.length <= cols) return [[0, t.length]];
  const rows: [number, number][] = [];
  let a = 0;
  while (a < t.length) {
    let b = Math.min(t.length, a + cols);
    if (b < t.length) { const sp = t.lastIndexOf(" ", b); if (sp > a + 8) b = sp + 1; }
    rows.push([a, b]);
    a = b;
  }
  return rows;
};

const resolveLines = (id: string, byId: Record<string, TScene>, seen = new Set<string>()): TLine[] => {
  const sc = byId[id];
  if (!sc || seen.has(id)) return [];
  seen.add(id);
  const card = sc.card;
  return [...(card.carry ? resolveLines(card.carry, byId, seen) : []), ...(card.lines ?? [])];
};

const planTerminal = (carry: TLine[], lines: TLine[], b: number[], len: number, cols: number, numbers: boolean): Plan[] => {
  const all = [...carry.map((l) => ({ l, carried: true })), ...lines.map((l) => ({ l, carried: false }))];
  let num = 0;
  for (let m = 1; m <= 8; m *= 1.5) {
    let prevEnd = 0;
    const plans: Plan[] = all.map(({ l, carried }) => {
      const pre = (PREFIX[l.k] ?? "").length;
      const gut = numbers ? 4 : 0;
      const rows = wrap(l.t, Math.max(10, cols - pre - gut));
      const printed = !typedKinds.has(l.k);
      if (l.k === "file" || l.k === "blank") num = l.k === "file" || numbers ? num + 1 : num;
      let start = 0, dur = 0;
      if (carried) { start = -999; dur = 1; }
      else {
        const anchor = l.beat != null ? b[Math.min(l.beat, b.length - 1)] : prevEnd + 3;
        start = l.fast ? Math.max(anchor, prevEnd) : Math.max(anchor, prevEnd + (printed ? 0 : 2));
        const cps = (l.cps ?? (l.k === "claude" ? 130 : 36)) * m;
        dur = printed && l.k !== "claude" ? 3 : Math.max(4, Math.round((l.t.length / cps) * TFPS));
        if (l.fast) dur = 2;
        prevEnd = start + dur;
      }
      return { line: l, rows, colors: lineColors(l), start, dur, printed, num };
    });
    num = 0;
    if (prevEnd <= len - 14 || m >= 8) return plans;
  }
  return [];
};

/* ------------------------------------------------------------------ pieces */
export const ClaudeMark: React.FC<{ size: number; color?: string }> = ({ size, color = C.accent }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{ display: "block" }}><path d={CLAUDE_PATH} fill={color} /></svg>
);

const Background: React.FC<{ lay: Lay }> = ({ lay }) => {
  const f = useCurrentFrame();
  const dx = Math.sin(f / 170) * 60, dy = Math.cos(f / 210) * 40;
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <AbsoluteFill style={{ background: `radial-gradient(60% 50% at ${30 + dx / 8}% ${28 + dy / 8}%, rgba(217,119,87,0.13), transparent 70%), radial-gradient(55% 45% at ${75 - dx / 9}% ${78 - dy / 8}%, rgba(122,167,255,0.09), transparent 70%)` }} />
      <AbsoluteFill style={{ backgroundImage: "radial-gradient(rgba(255,255,255,0.055) 1.5px, transparent 1.5px)", backgroundSize: lay.long ? "46px 46px" : "54px 54px", backgroundPosition: `${(f * 0.25) % 54}px ${(f * 0.12) % 54}px`, opacity: 0.8 }} />
      <AbsoluteFill style={{ background: "radial-gradient(120% 100% at 50% 50%, transparent 55%, rgba(0,0,0,0.55) 100%)" }} />
    </AbsoluteFill>
  );
};

const Header: React.FC<{ lay: Lay; step?: { n: number; title: string } }> = ({ lay, step }) => {
  const f = useCurrentFrame();
  const p = ease(f, 0, 16);
  return (
    <div style={{ position: "absolute", left: lay.long ? 160 : 50, right: lay.long ? 160 : 50, top: lay.headY, display: "flex", alignItems: "center", justifyContent: "space-between", opacity: p, transform: `translateY(${(1 - p) * -12}px)` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <ClaudeMark size={lay.long ? 44 : 56} />
        <div style={{ fontFamily: SANS, fontWeight: 700, letterSpacing: 5, color: C.text, fontSize: lay.long ? 26 : 32 }}>GEORGE EDOS</div>
      </div>
      {step && (
        <div style={{ display: "flex", alignItems: "center", gap: 14, justifyContent: "flex-end" }}>
          <div style={{ fontFamily: MONO, fontWeight: 600, color: C.accent, fontSize: lay.long ? 28 : 40, letterSpacing: 3 }}>STEP {step.n}</div>
          {lay.long && <div style={{ fontFamily: SANS, color: C.dim, fontSize: 26 }}>{step.title}</div>}
        </div>
      )}
    </div>
  );
};

const Pills: React.FC<{ lay: Lay; pills: Pill[]; b: number[] }> = ({ lay, pills, b }) => {
  const f = useCurrentFrame();
  const shown = pills.filter((p) => f >= b[Math.min(p.beat, b.length - 1)]).slice(-(lay.long ? 3 : 2));
  return (
    <div style={{ position: "absolute", left: lay.long ? 160 : 44, right: lay.long ? 160 : 44, top: lay.pillY, display: "flex", flexDirection: lay.long ? "row" : "column", gap: 14, alignItems: lay.long ? "center" : "center", justifyContent: "center", flexWrap: "wrap" }}>
      {shown.map((p) => {
        const at = b[Math.min(p.beat, b.length - 1)];
        const s = pop(f, at);
        const tone = p.tone === "red" ? C.red : p.tone === "green" ? C.green : C.accent;
        return (
          <React.Fragment key={p.text}>
            <div style={{ opacity: clamp01(s), transform: `scale(${0.7 + 0.3 * s}) translateY(${(1 - s) * 14}px)`, padding: lay.long ? "11px 26px" : "14px 34px", borderRadius: 999, border: `2px solid ${tone}`, background: "rgba(10,10,14,0.88)", color: C.text, fontFamily: SANS, fontWeight: 600, fontSize: lay.long ? 28 : 36, display: "flex", gap: 12, alignItems: "center" }}>
              <span style={{ width: 12, height: 12, borderRadius: 12, background: tone, display: "inline-block" }} />{p.text}
            </div>
            <Sequence from={at} durationInFrames={20} layout="none"><Audio src={staticFile("sfx/pop.wav")} volume={0.2} /></Sequence>
          </React.Fragment>
        );
      })}
    </div>
  );
};

/** display tokens with start/end seconds (relative to the beat file) */
const tokensOf = (bt: Beat) => {
  const toks = showText(bt.text).split(/\s+/).filter(Boolean);
  const W = bt.words;
  const total = bt.len / TFPS;
  if (!W.length) return toks.map((w, i) => ({ w, t: (i / toks.length) * total, e: ((i + 1) / toks.length) * total }));
  if (W.length === toks.length) return toks.map((w, i) => ({ w, t: W[i].t, e: W[i].e }));
  const a = W[0].t, z = W[W.length - 1].e, wt = toks.map((w) => w.length + 1), sum = wt.reduce((x, y) => x + y, 0);
  let acc = 0;
  return toks.map((w, i) => { const t = a + ((z - a) * acc) / sum; acc += wt[i]; return { w, t, e: a + ((z - a) * acc) / sum }; });
};
const nrm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

const Captions: React.FC<{ lay: Lay; sc: BScene; red: string[] }> = ({ lay, sc, red }) => {
  const f = useCurrentFrame();
  const bt = sc.beats.find((x) => f >= x.start - 2 && f <= x.start + x.len + 6);
  if (!bt) return null;
  const toks = tokensOf(bt);
  const tl = (f - bt.start) / TFPS;
  const isRed = (w: string) => red.some((r) => nrm(w).startsWith(nrm(r)) && nrm(r).length > 2);
  if (!lay.long) {
    let idx = toks.findIndex((k, i) => tl >= k.t - 0.02 && (i === toks.length - 1 || tl < toks[i + 1].t - 0.02));
    if (idx < 0) idx = tl < toks[0].t ? -1 : toks.length - 1;
    if (idx < 0) return null;
    const k = toks[idx];
    const fs = k.w.length > 9 ? 112 : 136;
    const s = pop(f, bt.start + Math.round(k.t * TFPS));
    return (
      <div style={{ position: "absolute", left: 0, right: 0, top: lay.capY, height: 240, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ transform: `scale(${0.82 + 0.18 * clamp01(s)})`, fontFamily: SANS, fontWeight: 700, fontSize: fs, textTransform: "uppercase", letterSpacing: 2, color: isRed(k.w) ? C.accent : "#fff",
          textShadow: "0 6px 0 rgba(0,0,0,0.9), 0 0 24px rgba(0,0,0,0.8), 4px 0 0 #000, -4px 0 0 #000, 0 -4px 0 #000" }}>{k.w.replace(/[.,;:]+$/, "")}</div>
      </div>
    );
  }
  // long: karaoke chunk of <= 9 words, broken at punctuation
  const chunks: typeof toks[] = [];
  let curc: typeof toks = [];
  toks.forEach((k) => { curc.push(k); if (curc.length >= 9 || /[.?!:]$/.test(k.w) || (curc.length >= 6 && /,$/.test(k.w))) { chunks.push(curc); curc = []; } });
  if (curc.length) chunks.push(curc);
  let ci = chunks.findIndex((ch) => tl <= ch[ch.length - 1].e + 0.05);
  if (ci < 0) ci = chunks.length - 1;
  const ch = chunks[ci];
  return (
    <div style={{ position: "absolute", left: 160, right: 160, top: lay.capY, height: 150, display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center" }}>
      <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 46, lineHeight: 1.25, textShadow: "0 3px 12px rgba(0,0,0,0.9)" }}>
        {ch.map((k, i) => {
          const spoken = tl >= k.t - 0.03;
          return <span key={i} style={{ color: spoken ? (isRed(k.w) ? C.accent : "#fff") : "rgba(255,255,255,0.42)", marginRight: 12 }}>{k.w}</span>;
        })}
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ cards */
const Terminal: React.FC<{ lay: Lay; sc: TScene; byId: Record<string, TScene>; b: number[]; len: number }> = ({ lay, sc, byId, b, len }) => {
  const f = useCurrentFrame();
  const { x, y, w, h } = lay.term;
  const card = sc.card;
  const charW = lay.fs * 0.6, padX = 28, padY = 22, barH = 52;
  const cols = Math.floor((w - padX * 2) / charW);
  const carry: TLine[] = card.carry ? resolveLines(card.carry, byId) : [];
  const plans = React.useMemo(() => planTerminal(carry, card.lines ?? [], b, len, cols, !!card.numbers), [sc.id, cols, len]);
  const viewH = h - barH - padY * 2;
  // scroll: ease to keep the newest started line visible
  let cum = 0, scroll = 0, prevT = 0;
  const heights: number[] = [];
  plans.forEach((p, i) => {
    if (f >= p.start) {
      cum += p.rows.length * lay.lh;
      const target = Math.max(0, cum - viewH);
      scroll = interpolate(f, [p.start, p.start + 8], [prevT, target], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
      prevT = target;
    }
    heights.push(p.rows.length * lay.lh);
  });
  const enter = ease(f, 0, 14);
  const blink = Math.floor(f / 15) % 2 === 0;
  const last = [...plans].reverse().find((p) => f >= p.start);
  const gut = card.numbers ? charW * 4 : 0;
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, height: h, borderRadius: 20, background: C.panel, border: `1.5px solid ${C.line}`, overflow: "hidden", opacity: enter, transform: `translateY(${(1 - enter) * 24}px)`, boxShadow: "0 30px 80px rgba(0,0,0,0.55)" }}>
      <div style={{ height: barH, background: C.bar, borderBottom: `1px solid ${C.line}`, display: "flex", alignItems: "center", padding: "0 22px", gap: 10, position: "relative" }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => <div key={c} style={{ width: 14, height: 14, borderRadius: 14, background: c }} />)}
        <div style={{ position: "absolute", left: 0, right: 0, textAlign: "center", fontFamily: MONO, color: C.dim, fontSize: 22 }}>{card.title ?? "terminal"}</div>
      </div>
      <div style={{ position: "absolute", left: padX, right: padX, top: barH + padY, height: viewH, overflow: "hidden" }}>
        <div style={{ transform: `translateY(${-scroll}px)`, fontFamily: MONO, fontSize: lay.fs, lineHeight: `${lay.lh}px`, color: C.text }}>
          {plans.map((p, i) => {
            if (f < p.start) return null;
            const prog = p.start < 0 ? 1 : clamp01((f - p.start) / Math.max(1, p.dur));
            const total = p.line.t.length;
            const shown = p.printed ? total : Math.floor(prog * total);
            const pre = PREFIX[p.line.k];
            const fade = p.printed && p.start >= 0 ? ease(f, p.start, 6) : 1;
            const prefixColor = p.line.k === "cmd" ? C.green : p.line.k === "claude" ? C.accent : p.line.k === "user" ? C.blue : C.green;
            return (
              <div key={i} style={{ position: "relative", opacity: fade, paddingLeft: gut }}>
                {card.numbers && (p.line.k === "file" || p.line.k === "blank") && (
                  <span style={{ position: "absolute", left: 0, width: gut - charW, textAlign: "right", color: "#4a5163" }}>{p.num}</span>
                )}
                {p.rows.map(([a, z], r) => {
                  const vis = Math.max(0, Math.min(z, shown) - a);
                  const txt = p.line.t.slice(a, a + vis);
                  return (
                    <div key={r} style={{ height: lay.lh, whiteSpace: "pre", paddingLeft: pre ? charW * 2 : 0, position: "relative" }}>
                      {pre && r === 0 && <span style={{ position: "absolute", left: 0, color: prefixColor }}>{pre}</span>}
                      {[...txt].map((ch, ci) => <span key={ci} style={{ color: p.colors[a + ci] }}>{ch}</span>)}
                      {last === p && r === p.rows.findIndex(([, zz]) => zz >= shown) && blink && <span style={{ background: C.text, display: "inline-block", width: charW * 0.7, height: lay.fs * 0.95, verticalAlign: "text-bottom", marginLeft: 2 }} />}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
      {/* typing sound under every typed line */}
      {plans.filter((p) => !p.printed && p.start >= 0 && p.dur > 6).map((p, i) => (
        <Sequence key={i} from={p.start} durationInFrames={p.dur} layout="none"><Audio loop src={staticFile("sfx/typing.wav")} volume={0.1} startFrom={(i * 23) % 120} /></Sequence>
      ))}
    </div>
  );
};

const TitleCard: React.FC<{ lay: Lay; card: any }> = ({ lay, card }) => {
  const f = useCurrentFrame();
  const s = pop(f, 2), a = ease(f, 8, 16), b = ease(f, 16, 16), c = ease(f, 26, 16);
  const big = lay.long ? 118 : 104;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center", paddingTop: lay.long ? 40 : 0 }}>
      <div style={{ transform: `scale(${0.6 + 0.4 * clamp01(s)}) rotate(${(1 - clamp01(s)) * -40}deg)`, opacity: clamp01(s), marginBottom: lay.long ? 30 : 50 }}>
        <ClaudeMark size={lay.long ? 120 : 190} />
      </div>
      <div style={{ opacity: a, fontFamily: MONO, color: C.accent, letterSpacing: 6, fontSize: lay.long ? 28 : 34, fontWeight: 600, transform: `translateY(${(1 - a) * 16}px)` }}>{card.kicker}</div>
      <div style={{ opacity: b, fontFamily: SANS, fontWeight: 700, color: "#fff", fontSize: big, lineHeight: 1.05, marginTop: 18, transform: `translateY(${(1 - b) * 24}px)` }}>{card.line1}</div>
      <div style={{ opacity: c, fontFamily: SANS, fontWeight: 700, color: C.accent, fontSize: big + 8, lineHeight: 1.05, transform: `translateY(${(1 - c) * 24}px)` }}>{card.line2}</div>
      {!!card.sub && <div style={{ opacity: c, fontFamily: SANS, color: C.dim, fontSize: lay.long ? 36 : 40, marginTop: 28 }}>{card.sub}</div>}
    </AbsoluteFill>
  );
};

const FlowCard: React.FC<{ lay: Lay; card: any; b: number[] }> = ({ lay, card, b }) => {
  const f = useCurrentFrame();
  const nodes: any[] = card.nodes;
  const horiz = lay.long;
  const bw = horiz ? 370 : 780, bh = horiz ? 200 : 190;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, top: horiz ? 320 : 420, display: "flex", flexDirection: horiz ? "row" : "column", justifyContent: "center", alignItems: "center", gap: horiz ? 0 : 0 }}>
      {nodes.map((n, i) => {
        const at = b[Math.min(n.beat, b.length - 1)] + (i && nodes[i - 1].beat === n.beat ? 8 : 0);
        const s = pop(f, at);
        const arrow = ease(f, at - 10, 12);
        return (
          <React.Fragment key={i}>
            {i > 0 && (
              <div style={{ width: horiz ? 90 : 6, height: horiz ? 6 : 70, background: C.accent, opacity: 0.7, transformOrigin: horiz ? "left" : "top", transform: horiz ? `scaleX(${arrow})` : `scaleY(${arrow})` }} />
            )}
            <div style={{ width: bw, height: bh, padding: "0 16px", boxSizing: "border-box", textAlign: "center", borderRadius: 22, border: `2px solid ${i === 0 ? C.blue : C.accent}`, background: C.panel, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8, opacity: clamp01(s), transform: `scale(${0.8 + 0.2 * clamp01(s)})` }}>
              <div style={{ fontFamily: MONO, fontWeight: 600, color: C.text, fontSize: horiz ? 30 : 40 }}>{n.t}</div>
              {!!n.s && <div style={{ fontFamily: SANS, color: C.dim, fontSize: horiz ? 26 : 32 }}>{n.s}</div>}
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
};

const ListCard: React.FC<{ lay: Lay; card: any; b: number[] }> = ({ lay, card, b }) => {
  const f = useCurrentFrame();
  const items: any[] = card.items;
  const fs = lay.long ? 50 : 52;
  const head = ease(f, 0, 14);
  return (
    <div style={{ position: "absolute", left: lay.long ? 300 : 70, right: lay.long ? 300 : 70, top: lay.long ? 190 : 450 }}>
      <div style={{ fontFamily: MONO, fontWeight: 600, color: C.accent, fontSize: lay.long ? 40 : 46, letterSpacing: 2, marginBottom: 28, opacity: head, transform: `translateY(${(1 - head) * 14}px)` }}>{card.title}</div>
      {items.map((it, i) => {
        const at = b[Math.min(it.beat, b.length - 1)] + (items.slice(0, i).filter((x) => x.beat === it.beat).length) * 7;
        const s = pop(f, at);
        const ic = it.x ? { c: C.red, g: "✗" } : it.ok ? { c: C.green, g: "✓" } : { c: C.accent, g: "●" };
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 24, marginBottom: lay.long ? 20 : 26, padding: "16px 28px", borderRadius: 16, background: C.panel, border: `1.5px solid ${it.x ? "rgba(255,100,100,0.5)" : C.line}`, opacity: clamp01(s), transform: `translateX(${(1 - clamp01(s)) * -50}px)` }}>
            <div style={{ color: ic.c, fontFamily: SANS, fontWeight: 700, fontSize: fs * 0.8, width: 44, textAlign: "center" }}>{ic.g}</div>
            <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: fs, color: it.x ? C.dim : C.text, textDecoration: it.x ? "line-through" : "none" }}>{it.t}</div>
          </div>
        );
      })}
    </div>
  );
};

const CompareCard: React.FC<{ lay: Lay; card: any; b: number[] }> = ({ lay, card, b }) => {
  const f = useCurrentFrame();
  const mk = (it: any, tone: string, mark: string) => {
    const at = b[Math.min(it.beat, b.length - 1)];
    const s = pop(f, at);
    return (
      <div style={{ flex: 1, borderRadius: 22, border: `3px solid ${tone}`, background: C.panel, padding: lay.long ? "28px 36px" : "30px 36px", opacity: clamp01(s), transform: `scale(${0.9 + 0.1 * clamp01(s)})` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 14 }}>
          <div style={{ color: tone, fontFamily: SANS, fontWeight: 700, fontSize: 52 }}>{mark}</div>
          <div style={{ color: tone, fontFamily: MONO, fontWeight: 600, fontSize: 32, letterSpacing: 4 }}>{it.label}</div>
        </div>
        <div style={{ fontFamily: MONO, fontSize: lay.long ? 38 : 40, color: C.text, lineHeight: 1.35 }}>{it.t}</div>
      </div>
    );
  };
  return (
    <div style={{ position: "absolute", left: lay.long ? 200 : 60, right: lay.long ? 200 : 60, top: lay.long ? 230 : 430, display: "flex", flexDirection: lay.long ? "row" : "column", gap: 34 }}>
      {mk(card.bad, C.red, "✗")}
      {mk(card.good, C.green, "✓")}
    </div>
  );
};

const CtaCard: React.FC<{ lay: Lay; card: any; b: number[] }> = ({ lay, card, b }) => {
  const f = useCurrentFrame();
  const s = pop(f, 2), u = pop(f, 14);
  const items: any[] = card.items ?? [];
  const pulse = 1 + 0.015 * Math.sin(f / 7);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center", paddingBottom: lay.long ? 0 : 200 }}>
      <div style={{ transform: `scale(${clamp01(s)})`, marginBottom: 24 }}><ClaudeMark size={lay.long ? 90 : 140} /></div>
      <div style={{ fontFamily: MONO, color: C.accent, letterSpacing: 6, fontWeight: 600, fontSize: lay.long ? 28 : 34, opacity: clamp01(s) }}>{card.tag}</div>
      <div style={{ fontFamily: SANS, fontWeight: 700, color: "#fff", fontSize: lay.long ? 92 : 92, margin: "16px 0 30px", lineHeight: 1.05, opacity: clamp01(s), padding: "0 40px" }}>{card.line1}</div>
      <div style={{ transform: `scale(${clamp01(u) * pulse})`, fontFamily: MONO, fontWeight: 600, color: C.bg, background: C.accent, borderRadius: 24, padding: lay.long ? "20px 48px" : "22px 34px", fontSize: lay.long ? 50 : 40 }}>{card.line2}</div>
      {!!items.length && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, justifyContent: "center", marginTop: 44, maxWidth: lay.long ? 1300 : 900 }}>
          {items.map((it, i) => {
            const at = b[Math.min(it.beat, b.length - 1)] + i * 14;
            const p = pop(f, at);
            return <div key={i} style={{ opacity: clamp01(p), transform: `scale(${0.8 + 0.2 * clamp01(p)})`, fontFamily: SANS, fontWeight: 600, fontSize: 30, color: C.text, border: `1.5px solid ${C.line}`, background: C.panel, borderRadius: 999, padding: "10px 26px" }}>{it.t}</div>;
          })}
        </div>
      )}
    </AbsoluteFill>
  );
};

/** big "STEP n" flash over the scene while the narrator announces the step */
const StepFlash: React.FC<{ lay: Lay; step: { n: number; title: string }; until: number }> = ({ lay, step, until }) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 5, until - 8, until + 4], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  if (f > until + 4) return null;
  const s = pop(f, 0);
  return (
    <AbsoluteFill style={{ background: "rgba(11,12,16,0.94)", opacity: o, alignItems: "center", justifyContent: "center", textAlign: "center" }}>
      <div style={{ transform: `scale(${0.7 + 0.3 * clamp01(s)})` }}>
        <div style={{ fontFamily: MONO, fontWeight: 600, color: C.accent, fontSize: lay.long ? 180 : 190, letterSpacing: 8, lineHeight: 1 }}>STEP {step.n}</div>
        <div style={{ height: 6, background: C.accent, margin: "26px auto", width: `${interpolate(f, [4, 22], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}%`, borderRadius: 6 }} />
        <div style={{ fontFamily: SANS, fontWeight: 700, color: "#fff", fontSize: lay.long ? 78 : 84, padding: "0 40px" }}>{step.title}</div>
      </div>
      <Sequence from={0} durationInFrames={40} layout="none"><Audio src={staticFile("sfx/hit_low.wav")} volume={0.3} /></Sequence>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ scene + composition */
const SceneView: React.FC<{ lay: Lay; sc: BScene; def: TScene; byId: Record<string, TScene>; first: boolean }> = ({ lay, sc, def, byId, first }) => {
  const f = useCurrentFrame();
  const b = sc.beats.map((x) => x.start);
  const o = first ? 1 : ease(f, 0, 7);
  const t = def.card.type;
  const flash = !!def.step && !!def.chapter?.startsWith("Step");
  return (
    <AbsoluteFill style={{ opacity: o, transform: `translateY(${first ? 0 : (1 - o) * 14}px)` }}>
      <Header lay={lay} step={def.step} />
      {t === "terminal" && <Terminal lay={lay} sc={def} byId={byId} b={b} len={sc.len} />}
      {t === "title" && <TitleCard lay={lay} card={def.card} />}
      {t === "flow" && <FlowCard lay={lay} card={def.card} b={b} />}
      {t === "list" && <ListCard lay={lay} card={def.card} b={b} />}
      {t === "compare" && <CompareCard lay={lay} card={def.card} b={b} />}
      {t === "cta" && <CtaCard lay={lay} card={def.card} b={b} />}
      {!!def.pills?.length && <Pills lay={lay} pills={def.pills} b={b} />}
      <Captions lay={lay} sc={sc} red={def.red ?? []} />
      {flash && <StepFlash lay={lay} step={def.step!} until={sc.beats[0].start + sc.beats[0].len} />}
    </AbsoluteFill>
  );
};

const DUCK = 0.4;
export const makeTutorial = (script: TScript, timing: Timing) => {
  const built = buildTutorial(script, timing);
  const byId = Object.fromEntries(script.scenes.map((s) => [s.id, s]));
  const speak = built.scenes.flatMap((s) => s.beats.map((b) => [s.from + b.start, s.from + b.start + b.len] as const));
  const duck = (f: number) => {
    let near = 1e9;
    for (const [a, z] of speak) { if (f >= a && f <= z) return DUCK; near = Math.min(near, f < a ? a - f : f - z); }
    return DUCK + (1 - DUCK) * Math.min(1, near / 10);
  };
  const Comp: React.FC = () => {
    const { width, height } = useVideoConfig();
    const lay = layout(width, height);
    const f = useCurrentFrame();
    return (
      <AbsoluteFill style={{ background: C.bg }}>
        <Background lay={lay} />
        {built.scenes.map((sc, i) => (
          <Sequence key={sc.id} from={sc.from} durationInFrames={sc.len + (i < built.scenes.length - 1 ? 0 : 6)} name={sc.id}>
            <SceneView lay={lay} sc={sc} def={byId[sc.id]} byId={byId} first={i === 0} />
            {i > 0 && <Sequence from={0} durationInFrames={14} layout="none"><Audio src={staticFile("sfx/whoosh.wav")} volume={0.1} /></Sequence>}
          </Sequence>
        ))}
        {built.scenes.flatMap((sc) => sc.beats.map((bt, j) => (
          <Sequence key={`${sc.id}v${j}`} from={sc.from + bt.start} durationInFrames={bt.len + 4} layout="none"><Audio src={staticFile(bt.file)} /></Sequence>
        )))}
        {script.music && (
          <Audio loop src={staticFile(script.music)} volume={(ff) => (script.musicVol ?? 0.1) * duck(ff) * interpolate(ff, [0, 30, built.total - 60, built.total], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />
        )}
        <div style={{ position: "absolute", left: 0, bottom: 0, height: lay.long ? 5 : 10, width: `${(f / built.total) * 100}%`, background: C.accent, opacity: 0.9 }} />
      </AbsoluteFill>
    );
  };
  return { Comp, built };
};
