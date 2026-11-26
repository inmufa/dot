"use client";
import { forwardRef, useEffect, useImperativeHandle, useRef, type CSSProperties } from "react";
import { useBuddyColor } from "@/lib/buddy/prefs";
import { BuddyEngine, buddyPalette, EYES, eyePath, type Emote, type Mood } from "./rig";
import "./Buddy.css";

const BASE = "M4 37C4 21 16.5 11 32.5 11C48.5 11 60 21.5 60 37C60 49.5 49 57 32 57C15 57 4 49.5 4 37Z";
const TOP = "M4 37C4 21 16.5 11 32.5 11C48.5 11 60 21.5 60 37C60 46 49 52.5 32 52.5C15 52.5 4 46 4 37Z";

export interface BuddyHandle { play: (e: Emote) => void }
interface Props {
  size?: number;
  mood?: Mood;
  follow?: boolean;
  className?: string;
  label?: string;
  onClick?: () => void;
}

/** Shared body markup; eyes are filled in by the engine (live) or statically (logo). */
function Body({ eyes }: { eyes?: [string, string] }) {
  return (
    <>
      <path d={BASE} fill="var(--bd-shade)" />
      <path d={TOP} fill="var(--bd-body)" />
      <path d="M12.5 28C13.5 22 18 17.5 23.5 16" fill="none" stroke="var(--bd-gloss)" strokeWidth="3.4" strokeLinecap="round" />
      <circle cx="28" cy="14.8" r="1.6" fill="var(--bd-gloss)" />
      <ellipse className="bd-ck" cx="13.5" cy="44" rx="4.3" ry="2.4" fill="var(--bd-blush)" opacity=".7" />
      <ellipse className="bd-ck" cx="51" cy="44" rx="4.3" ry="2.4" fill="var(--bd-blush)" opacity=".7" />
      <path className="bd-eye" d={eyes?.[0]} />
      <path className="bd-eye" d={eyes?.[1]} />
    </>
  );
}

/** Static buddy in the logo pose (winking). */
export function BuddyMark({ size = 24, label }: { size?: number; label?: string }) {
  const color = useBuddyColor();
  const eyes: [string, string] = [eyePath(EYES.winkR[0], 0), eyePath(EYES.winkR[1], 1)];
  return (
    <svg className="dot-mark bd" width={size} height={size} viewBox="0 0 64 64" style={buddyPalette(color) as CSSProperties} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true} focusable="false">
      <Body eyes={eyes} />
    </svg>
  );
}

/** Live buddy: breathes, blinks, follows the cursor and plays emotes for `mood` and `pulse`. */
export const Buddy = forwardRef<BuddyHandle, Props>(function Buddy({ size = 48, mood = "idle", follow = false, className, label = "Dot", onClick }, ref) {
  const color = useBuddyColor();
  const svg = useRef<SVGSVGElement>(null);
  const engine = useRef<BuddyEngine | null>(null);

  useEffect(() => {
    const el = svg.current;
    if (!el) return;
    const q = <T extends Element>(s: string) => [...el.querySelectorAll<T>(s)];
    const [e0, e1] = q<SVGPathElement>(".bd-eye");
    const [c0, c1] = q<SVGEllipseElement>(".bd-ck");
    const body = el.querySelector<SVGGElement>(".bd-body");
    if (!e0 || !e1 || !c0 || !c1 || !body) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const eng = new BuddyEngine({ body, eyes: [e0, e1], cheeks: [c0, c1], dots: q<SVGCircleElement>(".bd-dot") }, reduced, el);
    engine.current = eng;
    eng.start();
    const io = new IntersectionObserver(([entry]) => eng.setVisible(!!entry?.isIntersecting));
    io.observe(el);
    return () => { io.disconnect(); eng.stop(); engine.current = null; };
  }, []);

  useEffect(() => { if (engine.current) engine.current.follow = follow; }, [follow]);
  useEffect(() => { engine.current?.setMood(mood); }, [mood]);
  useImperativeHandle(ref, () => ({ play: (e) => void engine.current?.play(e) }), []);

  return (
    <svg
      ref={svg}
      className={`bd bd-live${className ? ` ${className}` : ""}`}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      style={buddyPalette(color) as CSSProperties}
      role="img"
      aria-label={label}
      onClick={onClick}
    >
      <g className="bd-body"><Body eyes={[eyePath(EYES.open[0], 0), eyePath(EYES.open[1], 1)]} /></g>
      <g fill="var(--bd-body)" aria-hidden>
        <circle className="bd-dot" cx="50" cy="8" r="1.5" opacity="0" />
        <circle className="bd-dot" cx="55" cy="3.5" r="2" opacity="0" />
        <circle className="bd-dot" cx="61" cy="-1.5" r="2.6" opacity="0" />
      </g>
    </svg>
  );
});
