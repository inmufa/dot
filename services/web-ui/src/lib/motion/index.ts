/** Small WAAPI helpers for values CSS cannot spring (dynamic heights). Compositor props stay in CSS. */
export const reducedMotion = (): boolean => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Spring curve from the CSS tokens (linear() easing), with a safe fallback. */
export function springEase(name: "snap" | "soft" | "pop" | "sheet" = "soft"): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--spring-${name}`).trim();
  return v || "cubic-bezier(0.23, 1, 0.32, 1)";
}

/** Animate an element's height between two measured values; the final height is already applied by the caller. */
export function animateHeight(el: HTMLElement, from: number, to: number, ms = 240): Animation | null {
  if (reducedMotion() || Math.abs(from - to) < 2 || typeof el.animate !== "function") return null;
  // height is the one layout property animated here: a text field has no transform-only way to grow
  return el.animate([{ height: `${from}px` }, { height: `${to}px` }], { duration: ms, easing: springEase("soft") });
}

export const clamp = (n: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, n));
