"use client";
import { useEffect, useRef, useState } from "react";

const SW = ["bg", "surface", "surface-2", "surface-3", "border", "text", "text-muted", "text-faint", "accent", "accent-contrast", "success", "warning", "danger", "info", "state-idle", "state-thinking", "state-waiting", "mode-plan", "mode-default", "mode-acceptEdits", "mode-auto", "mode-bypass", "chart-1", "chart-2", "chart-3", "chart-4", "chart-5", "chart-6", "sh-token-keyword", "sh-token-string", "sh-token-function", "sh-token-constant", "sh-token-comment", "sh-token-number"];
// [foreground, background, minimum, label]
const PAIRS: [string, string, number, string][] = [
  ["text", "bg", 7, "text on bg"], ["text", "surface-3", 7, "text on surface-3"], ["text-muted", "surface-3", 4.5, "muted on surface-3"], ["text-faint", "surface-2", 4.5, "faint on surface-2"], ["accent", "surface-2", 4.5, "accent on surface-2"], ["text", "surface", 7, "text on surface"], ["text-muted", "bg", 4.5, "muted on bg"], ["text-muted", "surface-2", 4.5, "muted on surface-2"],
  ["text-faint", "bg", 4.5, "faint on bg"], ["accent", "bg", 4.5, "accent text on bg"], ["accent-contrast", "accent", 4.5, "label on accent button"],
  ["success", "bg", 4.5, "success"], ["warning", "bg", 4.5, "warning"], ["danger", "bg", 4.5, "danger"], ["info", "bg", 4.5, "info"],
  ["state-idle", "bg", 3, "dot idle"], ["state-thinking", "bg", 3, "dot thinking"], ["state-waiting", "bg", 3, "dot waiting"],
  ["success", "surface-2", 4.5, "success on surface-2"], ["danger", "surface-2", 4.5, "danger on surface-2"],
  ["chart-1", "surface", 3, "chart 1"], ["chart-2", "surface", 3, "chart 2"], ["chart-3", "surface", 3, "chart 3"], ["chart-4", "surface", 3, "chart 4"], ["chart-5", "surface", 3, "chart 5"], ["chart-6", "surface", 3, "chart 6"],
  ["sh-token-keyword", "surface-2", 4.5, "code keyword"], ["sh-token-string", "surface-2", 4.5, "code string"], ["sh-token-function", "surface-2", 4.5, "code function"], ["sh-token-constant", "surface-2", 4.5, "code constant"], ["sh-token-comment", "surface-2", 4.5, "code comment"], ["sh-token-number", "surface-2", 4.5, "code number"],
  ["mode-plan", "bg", 4.5, "mode plan"], ["mode-default", "bg", 4.5, "mode default"], ["mode-acceptEdits", "bg", 4.5, "mode accept"], ["mode-auto", "bg", 4.5, "mode auto"], ["mode-bypass", "bg", 4.5, "mode bypass"],
];

const lin = (c: number) => { const s = c / 255; return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
function lum(rgb: string) {
  const m = rgb.match(/[\d.]+/g)?.map(Number) ?? [0, 0, 0];
  return 0.2126 * lin(m[0] ?? 0) + 0.7152 * lin(m[1] ?? 0) + 0.0722 * lin(m[2] ?? 0);
}

/** Swatches resolved from the live CSS variables, with WCAG ratios computed in the browser for the active theme. */
export const PALETTES = ["sage", "clay", "ink", "plum", "sand", "mono"] as const;

/** Palette and scheme switcher for the whole kit page (sets the same attributes Settings sets). */
export function KitSwitch() {
  const [pal, setPal] = useState("sage");
  const [theme, setTheme] = useState("system");
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    const p = q.get("palette"), t = q.get("theme");
    if (p) setPal(p);
    if (t) setTheme(t);
  }, []);
  useEffect(() => {
    const el = document.documentElement;
    if (pal === "sage") el.removeAttribute("data-palette"); else el.setAttribute("data-palette", pal);
    if (theme === "light" || theme === "dark") el.setAttribute("data-theme", theme); else el.removeAttribute("data-theme");
  }, [pal, theme]);
  return (
    <div className="kit-switch" role="group" aria-label="Kit palette and theme">
      {PALETTES.map((p) => <button key={p} type="button" className="chip" data-selected={pal === p} aria-pressed={pal === p} onClick={() => setPal(p)}>{p}</button>)}
      <span className="kit-sep" />
      {["system", "light", "dark"].map((t) => <button key={t} type="button" className="chip" data-selected={theme === t} aria-pressed={theme === t} onClick={() => setTheme(t)}>{t}</button>)}
    </div>
  );
}

export function Palette() {
  const host = useRef<HTMLDivElement>(null);
  const [res, setRes] = useState<{ colors: Record<string, string>; scheme: string } | null>(null);
  useEffect(() => {
    const read = () => {
      const colors: Record<string, string> = {};
      host.current?.querySelectorAll<HTMLElement>("[data-v]").forEach((el) => { colors[el.dataset.v ?? ""] = getComputedStyle(el).backgroundColor; });
      setRes({ colors, scheme: getComputedStyle(document.documentElement).colorScheme });
    };
    read();
    const mo = new MutationObserver(read);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-palette"] });
    const mq = matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", read);
    return () => { mo.disconnect(); mq.removeEventListener("change", read); };
  }, []);
  const ratio = (a: string, b: string) => {
    const x = lum(res?.colors[a] ?? ""), y = lum(res?.colors[b] ?? "");
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
  };
  return (
    <div ref={host} className="pal-kit">
      <div className="pal-sw">
        {SW.map((v) => (
          <div key={v}><span className="pal-chip" data-v={v} style={{ background: `var(--${v})` }} /><small>{v}</small></div>
        ))}
      </div>
      {res && (
        <table className="pal-tbl">
          <tbody>
            {PAIRS.map(([f, b, min, label]) => {
              const r = ratio(f, b);
              return (
                <tr key={label}>
                  <td><span className="pal-aa" style={{ color: `var(--${f})`, background: `var(--${b})` }}>Aa</span></td>
                  <td>{label}</td>
                  <td className="tnum">{r.toFixed(2)}</td>
                  <td className="tnum">{min}:1</td>
                  <td data-pass={r >= min}>{r >= min ? "pass" : "FAIL"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
