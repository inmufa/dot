"use client";
import { useRef } from "react";
import { Buddy, type BuddyHandle } from "@/components/buddy/Buddy";
import type { Emote } from "@/components/buddy/rig";
import { Switch } from "@/components/ui";
import { BUDDY_COLORS, setBuddyAnim, setBuddyColor, useBuddyAnim, useBuddyColor } from "@/lib/buddy/prefs";
import { SettingGroup, SettingRow } from "./SettingRow";

const TRY: [Emote, string][] = [["nod", "Nod"], ["wink", "Wink"], ["wonder", "Wonder"], ["squint", "Squint"], ["jump", "Jump"], ["done", "Done"]];

/** Buddy colour: named swatches on the left, a live buddy on the right that reacts to the pick. */
export function BuddySettings() {
  const color = useBuddyColor();
  const animate = useBuddyAnim();
  const buddy = useRef<BuddyHandle>(null);
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
        <div className="bd-preview">
          <Buddy ref={buddy} size={120} follow label="Buddy preview" />
          <div className="bd-try">
            {TRY.map(([e, label]) => <button key={e} type="button" className="bd-try-btn" onClick={() => buddy.current?.play(e)}>{label}</button>)}
          </div>
        </div>
      </div>
      <SettingRow label="Animate" htmlFor="buddy-anim" layout="inline" hint="Off keeps the buddy still, in its logo pose, everywhere.">
        <Switch id="buddy-anim" checked={animate} onChange={(e) => setBuddyAnim(e.target.checked)} />
      </SettingRow>
    </SettingGroup>
  );
}
