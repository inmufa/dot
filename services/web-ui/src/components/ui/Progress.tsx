/** Determinate bar (value 0..1) or indeterminate (omit value). Track = quiet fill, bar = accent. Transform only. */
export function Progress({ value, label, tone = "accent" }: { value?: number; label: string; tone?: "accent" | "ok" | "warn" | "bad" }) {
  const v = value == null ? undefined : Math.min(1, Math.max(0, value));
  return (
    <div className="progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={v == null ? undefined : Math.round(v * 100)} data-tone={tone} data-indeterminate={v == null}>
      <span className="progress-bar" style={v == null ? undefined : { transform: `scaleX(${v})` }} />
      <span className="progress-head" style={v == null ? undefined : { transform: `translateX(${(v - 1) * 100}%)` }} />
    </div>
  );
}
