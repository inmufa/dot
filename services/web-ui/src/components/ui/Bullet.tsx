type Tone = "accent" | "faint" | "ok" | "warn" | "bad" | "info";
/** The motif at rest: a static dot (list marker, rail node, separator). Live status uses StateDot. Decorative. */
export function Bullet({ size = "s", tone = "accent" }: { size?: "s" | "m"; tone?: Tone }) {
  return <span className="bullet" data-size={size} data-tone={tone} aria-hidden />;
}
