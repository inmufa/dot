/* Dot buddy rig: eye shapes, colours and the pose engine. Every eye is 4 cubic segments (13 points) so any eye morphs into any other. */

export type Pt = [number, number];
export type EyePair = [Pt[], Pt[]];
export type Emote = "thinking" | "working" | "waiting" | "wonder" | "squint" | "done" | "error" | "wink" | "jump" | "nod";
export type Mood = "idle" | "thinking" | "working" | "waiting";

export const CENTRES: Pt[] = [[21.5, 37], [42.5, 37]];
export const EYE_SIZE = [1.06, 0.9]; // a touch lopsided: left bigger, right smaller

const ell = (rx: number, ry: number, dy = 0): Pt[] => {
  const a = rx * 0.5523, b = ry * 0.5523;
  return [[0, -ry + dy], [a, -ry + dy], [rx, -b + dy], [rx, dy], [rx, b + dy], [a, ry + dy], [0, ry + dy], [-a, ry + dy], [-rx, b + dy], [-rx, dy], [-rx, -b + dy], [-a, -ry + dy], [0, -ry + dy]];
};
const ARCH: Pt[] = [[0, -2.6], [2.0, -2.6], [3.7, -0.8], [3.7, 1.0], [2.6, 0.9], [1.6, -0.2], [0, -0.2], [-1.6, -0.2], [-2.6, 0.9], [-3.7, 1.0], [-3.7, -0.8], [-2.0, -2.6], [0, -2.6]];
// flat lid; positive slant lowers it toward the face centre on the left eye
const lid = (top: number, slant: number, w = 2.6, bottom = 2.8): Pt[] => {
  const k = 0.5523, T = (x: number) => top + slant * x;
  const mid = (x: number) => (T(x) + bottom) / 2;
  return [[0, T(0)], [w * 0.6, T(w * 0.6)], [w, T(w) + 0.1], [w, mid(w)], [w, mid(w) + ((bottom - T(w)) * k) / 2], [w * k, bottom], [0, bottom], [-w * k, bottom], [-w, mid(-w) + ((bottom - T(-w)) * k) / 2], [-w, mid(-w)], [-w, T(-w) + 0.1], [-w * 0.6, T(-w * 0.6)], [0, T(0)]];
};
const mirror = (p: Pt[]): Pt[] => p.map(([x, y]) => [-x, y]);
const pair = (l: Pt[], r: Pt[] = mirror(l)): EyePair => [l, r];

export const EYES = {
  open: pair(ell(2.4, 3.1)),
  closed: pair(ell(2.9, 0.15, 1)),
  big: pair(ell(3.3, 4.1, -0.6)),
  narrow: pair(ell(2.6, 1.5, 0.5)),
  focus: pair(lid(-1.0, 0.32)),
  worried: pair(lid(-0.6, -0.34, 2.4, 2.6)),
  squeeze: pair(ell(3.3, 1.1, -0.2)),
  happy: pair(ARCH, ARCH),
  winkR: [ell(2.4, 3.1), ARCH] as EyePair,
  down: pair(ell(2.4, 2.4, 0.9)),
};
export type EyeName = keyof typeof EYES;

/** SVG path for one eye at its place in the face. */
export function eyePath(pts: Pt[], i: number, lx = 0, ly = 0): string {
  const [cx, cy] = CENTRES[i] ?? [0, 0];
  const k = EYE_SIZE[i] ?? 1;
  const f = (p: Pt) => `${(p[0] * k + cx + lx).toFixed(2)} ${(p[1] * k + cy + ly).toFixed(2)}`;
  let d = `M${f(pts[0] ?? [0, 0])}`;
  for (let j = 1; j < 13; j += 3) d += `C${f(pts[j] ?? [0, 0])} ${f(pts[j + 1] ?? [0, 0])} ${f(pts[j + 2] ?? [0, 0])}`;
  return `${d}Z`;
}

// ---- colour: base in, shade / gloss / blush out ----
function hexToHsl(hex: string): [number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16) / 255, g = parseInt(hex.slice(3, 5), 16) / 255, b = parseInt(hex.slice(5, 7), 16) / 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
  if (mx === mn) return [0, 0, l * 100];
  const d = mx - mn, s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
  const h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [h * 60, s * 100, l * 100];
}
const hsl = (h: number, s: number, l: number) => `hsl(${h.toFixed(0)} ${Math.max(0, Math.min(100, s)).toFixed(0)}% ${Math.max(0, Math.min(100, l)).toFixed(0)}%)`;
export function buddyPalette(hex: string): Record<"--bd-body" | "--bd-shade" | "--bd-gloss" | "--bd-blush", string> {
  const [h, s, l] = hexToHsl(hex);
  const warm = s > 30 && (h < 50 || h > 320);
  return { "--bd-body": hex, "--bd-shade": hsl(h, s * 0.9, l - 11), "--bd-gloss": hsl(h, s * 0.6, Math.min(94, l + 16)), "--bd-blush": warm ? "#E0607A" : "#F59AA6" };
}

// ---- engine ----
type Pose = { tx: number; ty: number; rot: number; sx: number; sy: number; lx: number; ly: number; ckL: number; ckR: number; dots: number };
type PoseKey = keyof Pose;
const NEUTRAL: Pose = { tx: 0, ty: 0, rot: 0, sx: 1, sy: 1, lx: 0, ly: 0, ckL: 0, ckR: 0, dots: 0 };
const BODY_PACE = 1.6, EYE_PACE = 1.15, TILT = 0.5;
type Ease = (t: number) => number;
const E: Record<"out" | "in" | "inOut", Ease> = {
  out: (t) => 1 - Math.pow(1 - t, 3),
  in: (t) => t * t * t,
  inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
};
interface Tween { from: Partial<Pose>; target: Partial<Pose>; ms: number; ease: Ease; t0: number; done: () => void }
interface EyeTween { from: EyePair; to: EyePair; ms: number; ease: Ease; t0: number; done: () => void }

export interface Els { body: SVGGElement; eyes: [SVGPathElement, SVGPathElement]; cheeks: [SVGEllipseElement, SVGEllipseElement]; dots: SVGCircleElement[] }

/** One buddy's animation state; render() writes the current frame into the SVG. */
export class BuddyEngine {
  private P: Pose = { ...NEUTRAL };
  private eyes: EyePair = clone(EYES.open);
  private tweens = new Set<Tween>();
  private eyeTw: EyeTween | null = null;
  private busy = false;
  private token = 0;
  private mood: Mood = "idle";
  private raf = 0;
  private life = 0;
  private cursor: Pt | null = null;
  private glance: Pt = [0, 0];
  private glanceUntil = 0;
  private visible = true;
  follow = false;

  constructor(private els: Els, private reduced: boolean, private host: SVGSVGElement) {}

  start(): void {
    if (this.raf) return;
    const tick = (now: number) => { this.frame(now); this.raf = requestAnimationFrame(tick); };
    this.raf = requestAnimationFrame(tick);
    this.life = window.setInterval(() => this.idleLife(), 2400);
    window.addEventListener("pointermove", this.onPointer, { passive: true });
  }
  stop(): void {
    cancelAnimationFrame(this.raf); this.raf = 0;
    window.clearInterval(this.life);
    window.removeEventListener("pointermove", this.onPointer);
  }
  setVisible(v: boolean): void { this.visible = v; if (v) this.start(); else this.stop(); }

  setMood(m: Mood): void {
    if (m === this.mood) return;
    this.mood = m;
    if (m !== "idle") void this.play(m);
  }

  /** Plays one emote; a looping mood replays its emote while it lasts. */
  play(name: Emote): Promise<void> {
    const my = ++this.token;
    this.busy = true;
    this.tweens.clear();
    const live = () => my === this.token;
    return this.script(name, live).then(async () => {
      if (!live()) return;
      if (this.mood !== "idle" && (name === this.mood || name === "wonder" || name === "nod")) { void this.play(this.mood); return; }
      await Promise.all([this.to(NEUTRAL, 320, E.out), this.eye("open", 220)]);
      if (live()) this.busy = false;
    });
  }

  private onPointer = (e: PointerEvent) => {
    if (!this.follow) return;
    const r = this.host.getBoundingClientRect();
    const dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height * 0.58);
    const d = Math.hypot(dx, dy) || 1, k = Math.min(1, d / 280);
    this.cursor = [(dx / d) * 3 * k, (dy / d) * 2 * k];
  };

  private idleLife(): void {
    if (this.busy || this.mood !== "idle" || !this.visible) return;
    const r = Math.random();
    if (r < 0.45) void this.blink(Math.random() < 0.2);
    else if (r < 0.6) { this.glance = [Math.random() < 0.5 ? -2.6 : 2.6, -0.4]; this.glanceUntil = performance.now() + 900; }
    else if (r < 0.65) void this.play("wink");
  }

  private to(target: Partial<Pose>, ms: number, ease: Ease = E.inOut, paced = true): Promise<void> {
    return new Promise((done) => {
      // the newest tween owns its keys
      for (const tw of this.tweens) tw.target = Object.fromEntries(Object.entries(tw.target).filter(([k]) => !(k in target)));
      const from: Partial<Pose> = {};
      for (const k of Object.keys(target) as PoseKey[]) from[k] = this.P[k];
      this.tweens.add({ from, target, ms: this.reduced ? 0 : ms * (paced ? BODY_PACE : 1), ease, t0: performance.now(), done });
    });
  }
  private eye(name: EyeName, ms = 160, ease: Ease = E.out): Promise<void> {
    this.eyeTw?.done();
    return new Promise((done) => { this.eyeTw = { from: clone(this.eyes), to: EYES[name], ms: ms * EYE_PACE, ease, t0: performance.now(), done }; });
  }
  private async blink(double = false): Promise<void> {
    await this.eye("closed", 70, E.in); await this.eye("open", 120);
    if (double) { await wait(90); await this.eye("closed", 60, E.in); await this.eye("open", 120); }
  }

  private frame(now: number): void {
    for (const tw of [...this.tweens]) {
      const t = tw.ms <= 0 ? 1 : Math.min(1, (now - tw.t0) / tw.ms), e = tw.ease(t);
      for (const k of Object.keys(tw.target) as PoseKey[]) { const a = tw.from[k] ?? this.P[k], b = tw.target[k] ?? a; this.P[k] = a + (b - a) * e; }
      if (t >= 1) { this.tweens.delete(tw); tw.done(); }
    }
    if (this.eyeTw) {
      const tw = this.eyeTw, t = Math.min(1, (now - tw.t0) / tw.ms), e = tw.ease(t);
      this.eyes = tw.from.map((s, i) => s.map((p, j) => { const q = tw.to[i]?.[j] ?? p; return [p[0] + (q[0] - p[0]) * e, p[1] + (q[1] - p[1]) * e]; })) as EyePair;
      if (t >= 1) { this.eyeTw = null; tw.done(); }
    }
    let bx = 0, by = 0, lean = 0;
    const P = this.P;
    if (!this.busy) {
      if (!this.reduced) { const br = Math.sin((now / 3600) * Math.PI * 2); bx = 0.018 * br; by = -0.028 * br; }
      const tl: Pt = now < this.glanceUntil ? this.glance : this.follow && this.cursor ? this.cursor : [0, 0];
      P.lx += (tl[0] - P.lx) * 0.1; P.ly += (tl[1] - P.ly) * 0.1;
      lean = P.lx * 1.1;
    }
    const { body, eyes, cheeks, dots } = this.els;
    body.setAttribute("transform", `translate(${(32 + P.tx).toFixed(2)} ${(57 + P.ty).toFixed(2)}) rotate(${((P.rot + lean) * TILT).toFixed(2)}) scale(${(P.sx + bx).toFixed(3)} ${(P.sy + by).toFixed(3)}) translate(-32 -57)`);
    eyes.forEach((el, i) => el.setAttribute("d", eyePath(this.eyes[i] ?? [], i, P.lx, P.ly)));
    cheeks[0].setAttribute("transform", `translate(0 ${(-1.8 * P.ckL).toFixed(2)})`);
    cheeks[1].setAttribute("transform", `translate(0 ${(-1.8 * P.ckR).toFixed(2)})`);
    dots.forEach((c, i) => c.setAttribute("opacity", Math.max(0, Math.min(1, P.dots * 3 - i)).toFixed(2)));
  }

  // ---- emotes: each plays once ----
  private async script(name: Emote, live: () => boolean): Promise<void> {
    const { to } = { to: this.to.bind(this) }, eye = this.eye.bind(this);
    switch (name) {
      case "thinking": // eyes up and aside, head follows, thought dots rise
        await Promise.all([eye("narrow", 200), to({ lx: -2.4, ly: -1.6, rot: -3, dots: 0.4 }, 380)]);
        if (!live()) return; await to({ dots: 1 }, 450); await wait(250);
        if (!live()) return; await to({ lx: 2.4, ly: -1.8, rot: 3 }, 520); await wait(380);
        if (!live()) return; await to({ lx: 0.6, ly: -1.2, rot: 0, dots: 0 }, 420);
        await this.blink();
        return;
      case "working": // focused lids, settles low, slow kneading squish in place
        await Promise.all([eye("focus", 180), to({ ly: 0.5, sy: 0.96, sx: 1.03 }, 260)]);
        for (let i = 0; i < 3 && live(); i++) {
          await to({ sy: 0.93, sx: 1.05, ty: 0.8, rot: i % 2 ? 1.5 : -1.5 }, 260);
          await to({ sy: 0.98, sx: 1.01, ty: 0, rot: 0 }, 260);
        }
        return;
      case "waiting": // looks at you, leans in, two "hey" bobs, small wiggle
        await Promise.all([eye("big", 180), to({ ly: 0.8, rot: -5, sy: 1.04, sx: 0.97 }, 260, E.out)]);
        for (let i = 0; i < 2 && live(); i++) { await to({ ty: -3, rot: -7 }, 180, E.out); await to({ ty: 0, rot: -3 }, 200, E.in); }
        if (!live()) return; await to({ rot: 4 }, 220); await to({ rot: -2 }, 220);
        await wait(150); await this.blink();
        return;
      case "wonder": // crouch, stretch tall, big eyes up
        await to({ sy: 0.92, sx: 1.05 }, 120, E.out); if (!live()) return;
        await Promise.all([eye("big", 220), to({ sy: 1.08, sx: 0.95, ty: -3, ly: -1.4 }, 300, E.out)]);
        await wait(650);
        return;
      case "squint": // press flat, fold into arches, cheeks up, body scrunches, opens with a pop
        await Promise.all([eye("squeeze", 120, E.in), to({ ckL: 0.6, ckR: 0.6, sx: 1.05, sy: 0.94 }, 120)]);
        await Promise.all([eye("happy", 170), to({ ckL: 1, ckR: 1, sx: 1.08, sy: 0.9 }, 170, E.out)]);
        await wait(650); if (!live()) return;
        await Promise.all([eye("big", 160), to({ ckL: 0, ckR: 0, sx: 0.98, sy: 1.03 }, 160)]);
        await wait(80);
        return;
      case "done": // happy arches, three small hops
        await Promise.all([eye("happy", 150), to({ ckL: 1, ckR: 1, sx: 1.06, sy: 0.92 }, 120)]);
        for (const h of [6, 4, 2]) {
          if (!live()) return;
          await to({ ty: -h, sx: 0.96, sy: 1.05 }, 150, E.out);
          await to({ ty: 0, sx: 1.07, sy: 0.91 }, 130, E.in);
        }
        if (live()) { await to({ sx: 1, sy: 1 }, 180, E.out); await wait(250); }
        return;
      case "error": // flinch, sag, worried lids, slow head shake
        await to({ sy: 0.9, sx: 1.02, ty: 1 }, 90, E.out); if (!live()) return;
        await Promise.all([eye("worried", 260), to({ sy: 0.94, sx: 1.06, ly: 1.2, ty: 0 }, 420)]);
        for (const r of [-4, 4, -2.5, 0]) { if (!live()) return; await to({ rot: r }, 230); }
        await wait(350);
        return;
      case "wink": // tilts toward the wink, that side squashes, cheek lifts, eye snaps shut and pops open
        await Promise.all([eye("winkR", 90, E.in), to({ rot: 6, tx: 1, ty: 1, sx: 1.04, sy: 0.95, ckR: 1, lx: 0.4 }, 120, E.out)]);
        await wait(200); if (!live()) return;
        await Promise.all([eye("open", 150), to({ rot: -1.5, ty: -1.5, sx: 0.98, sy: 1.03, ckR: 0 }, 200, E.out)]);
        await to({ rot: 0, ty: 0, tx: 0, sx: 1, sy: 1 }, 180, E.out);
        return;
      case "jump": { // light and springy: small crouch, quick launch, a float at the top, soft landing
        const q = (t: Partial<Pose>, ms: number, ease: Ease) => this.to(t, ms, ease, false);
        await q({ sy: 0.94, sx: 1.04 }, 90, E.out); if (!live()) return;
        await Promise.all([q({ ty: -15, sy: 1.06, sx: 0.96, ly: -0.8 }, 210, E.out), eye("big", 180)]);
        await q({ ty: -16, sy: 1, sx: 1 }, 110, E.inOut);
        await Promise.all([q({ ty: 0, sy: 1.02, sx: 0.99, ly: 0 }, 190, E.in), eye("open", 180)]);
        await q({ sy: 0.95, sx: 1.04 }, 70, E.out);
        if (live()) await q({ sy: 1, sx: 1 }, 170, E.out);
        return;
      }
      case "nod": // "got it": eyes dip, two gentle forward nods
        for (let i = 0; i < 2 && live(); i++) {
          await Promise.all([eye("down", 140), to({ ty: 1.6, sy: 0.95, sx: 1.03, ly: 1.2 }, 200)]);
          await Promise.all([eye("open", 160), to({ ty: 0, sy: 1, sx: 1, ly: 0 }, 220, E.out)]);
        }
        return;
    }
  }
}

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
const clone = (e: EyePair): EyePair => [e[0].map((p) => [...p] as Pt), e[1].map((p) => [...p] as Pt)];
