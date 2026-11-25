"use client";
import type { Palette } from "@/lib/palettes";
import { PALETTES } from "@/lib/palettes";

const NOTE: Record<Palette, string> = { sage: "moss", clay: "kiln", ink: "blueprint", plum: "ledger", sand: "parchment", mono: "graphite" };

/** Radio group (arrow keys move the choice): each palette as page tone, surface and its dot, with a name and a one-word note. */
export function PalettePicker({ value, onChange }: { value: Palette; onChange: (p: Palette) => void }) {
  const pick = (i: number) => {
    const p = PALETTES[(i + PALETTES.length) % PALETTES.length];
    if (p) onChange(p.id);
  };
  return (
    <div className="pal-grid" role="radiogroup" aria-label="Colour palette">
      {PALETTES.map((p, i) => (
        <button
          key={p.id}
          type="button"
          role="radio"
          aria-checked={value === p.id}
          tabIndex={value === p.id ? 0 : -1}
          className="pal-opt"
          onClick={() => onChange(p.id)}
          onKeyDown={(e) => {
            const d = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
            if (!d) return;
            e.preventDefault();
            pick(i + d);
            window.requestAnimationFrame(() => e.currentTarget.parentElement?.querySelectorAll<HTMLElement>('[role="radio"]')[(i + d + PALETTES.length) % PALETTES.length]?.focus());
          }}
        >
          <span className="pal-sw" data-p={p.id} aria-hidden>
            <i className="pal-surf" />
            <i className="pal-acc" />
          </span>
          <span className="pal-name">{p.label}</span>
          <span className="pal-note rec">{NOTE[p.id]}</span>
        </button>
      ))}
    </div>
  );
}
