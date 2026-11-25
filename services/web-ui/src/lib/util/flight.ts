let armed = false;
/** Call when the owner sends a message from the home screen: the next home unmount flies the dot. */
export const armFlight = (): void => { armed = true; };
/** Home left without a flight (glide already played, or nothing sent): drop a stale arm. */
export const disarmFlight = (): void => { armed = false; };

/** While the home dot is typing, the top-bar dot stays hidden so there is only one dot on screen. */
export const holdHomeDot = (on: boolean): void => {
  if (typeof document === "undefined") return;
  if (on) document.documentElement.dataset.homeDot = "typing";
  else delete document.documentElement.dataset.homeDot;
};

/** Glide a copy of the home dot to the top-bar dot (transform only, `--dur-glide`), then reveal the real one. */
export function flyDot(from: DOMRect, force = false): void {
  if (!force && !armed) { holdHomeDot(false); return; }
  armed = false;
  const target = typeof document === "undefined" ? null : document.querySelector<HTMLElement>("[data-flight-target] .dot");
  if (!target || from.width === 0 || window.matchMedia("(prefers-reduced-motion: reduce)").matches) { holdHomeDot(false); return; }
  const to = target.getBoundingClientRect();
  if (to.width === 0) { holdHomeDot(false); return; }
  const ghost = document.createElement("span");
  ghost.className = "dot dot-flight";
  ghost.dataset.state = "idle";
  Object.assign(ghost.style, { position: "fixed", left: `${from.left}px`, top: `${from.top}px`, width: `${from.width}px`, height: `${from.height}px`, zIndex: "200", pointerEvents: "none", background: "var(--accent)", transformOrigin: "center" });
  document.body.append(ghost);
  target.style.visibility = "hidden";
  holdHomeDot(false);
  const dx = to.left + to.width / 2 - (from.left + from.width / 2);
  const dy = to.top + to.height / 2 - (from.top + from.height / 2);
  const done = () => { ghost.remove(); target.style.visibility = ""; };
  const ease = getComputedStyle(document.documentElement).getPropertyValue("--ease-in-out").trim() || "cubic-bezier(0.77, 0, 0.175, 1)";
  const ms = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--dur-glide")) || 520;
  ghost
    .animate([{ transform: "none" }, { transform: `translate(${dx}px, ${dy}px) scale(${to.width / from.width})` }], { duration: ms, easing: ease, fill: "forwards" })
    .finished.then(done, done);
}
