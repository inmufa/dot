/** The Dot mark: an inverted tile (graphite on light UI, paper on dark) with the accent dot. Follows the active palette. `small` uses the bigger dot for 24 px and below. */
export function Mark({ size = 24, small = size <= 24, label }: { size?: number; small?: boolean; label?: string }) {
  const r = small ? 18.56 : 13.76;
  return (
    <svg className="dot-mark" width={size} height={size} viewBox="0 0 64 64" role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true} focusable="false">
      <rect width="64" height="64" rx="17.3" className="dot-mark-tile" />
      <circle cx="32" cy="32" r={r} className="dot-mark-dot" />
    </svg>
  );
}
