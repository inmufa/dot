"use client";
import { useEffect, useRef } from "react";
import { Buddy, BuddyMark, type BuddyHandle } from "@/components/buddy/Buddy";
import type { Emote } from "@/components/buddy/rig";
import { Switch } from "@/components/ui";
import { BUDDY_COLORS, setBuddyAnim, setBuddyColor, useBuddyAnim, useBuddyColor } from "@/lib/buddy/prefs";
import { SettingGroup, SettingRow } from "./SettingRow";

const SHOW: Emote[] = ["nod", "wink", "wonder", "squint", "jump", "done", "thinking"];

/** Buddy colour: named swatches on the left, a live buddy on the right that reacts to the pick. */
export function BuddySettings() {
  const color = useBuddyColor();
  const animate = useBuddyAnim();
  const buddy = useRef<BuddyHandle>(null);
  // the preview plays random emotes one after another, with a pause between
  useEffect(() => {
    if (!animate) return;
    let prev: Emote | null = null;
    const t = window.setInterval(() => {
      const pool = SHOW.filter((e) => e !== prev);
      prev = pool[Math.floor(Math.random() * pool.length)] ?? "nod";
      buddy.current?.play(prev);
    }, 3400);
    return () => window.clearInterval(t);
  }, [animate]);
  const pick = (hex: string) => { setBuddyColor(hex); buddy.current?.play("done"); };
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const d = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const next = BUDDY_COLORS[(i + d + BUDDY_COLORS.length) % BUDDY_COLORS.length];
    if (!next) return;
    pick(next.hex);
    const row = e.currentTarget.parentElement;
    window.requestAnimationFrame(() => row?.querySelector<HTMLElement>('[aria-checked="true"]')?.focus());
  };
  return (
    <SettingGroup title="Buddy" intro="Dot's little companion. It reacts to what Dot is doing: thinking, working, waiting for you, done.">
      <div className="bd-set">
        <div className="bd-preview">
          {animate ? <Buddy ref={buddy} size={112} follow label="Buddy preview" /> : <BuddyMark size={112} label="Buddy preview" />}
          <span className="bd-preview-name">{BUDDY_COLORS.find((c) => c.hex === color)?.name}</span>
        </div>
        <div className="bd-side">
          <div className="bd-swatches" role="radiogroup" aria-label="Buddy colour">
            {BUDDY_COLORS.map((c, i) => {
              const on = c.hex === color;
              return (
                <button key={c.hex} type="button" role="radio" aria-checked={on} tabIndex={on ? 0 : -1} className="bd-sw" onClick={() => pick(c.hex)} onKeyDown={(e) => onKey(e, i)}>
                  <span className="bd-sw-dot" style={{ background: c.hex }} aria-hidden />
                  <span className="bd-sw-name">{c.name}</span>
                </button>
              );
            })}
          </div>
          <SettingRow label="Animate" htmlFor="buddy-anim" layout="inline" hint="Off keeps the buddy still, in its logo pose, everywhere.">
            <Switch id="buddy-anim" checked={animate} onChange={(e) => setBuddyAnim(e.target.checked)} />
          </SettingRow>
        </div>
      </div>
    </SettingGroup>
  );
}
