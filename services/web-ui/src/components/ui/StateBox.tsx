import type { ReactNode } from "react";
import type { DotErrorInfo } from "@/lib/api/errors";

/** `quiet` drops the heading weight and size: for inline panes (canvas, sheets) where a bold title shouts. */
/** Sparse dot-matrix texture with one accent dot, for empty states. */
export function DotGrid() {
  const cols = 9, rows = 3;
  return (
    <svg className="dot-grid" width={cols * 14} height={rows * 14} viewBox={`0 0 ${cols * 14} ${rows * 14}`} aria-hidden focusable="false">
      {Array.from({ length: cols * rows }, (_, i) => {
        const x = (i % cols) * 14 + 7, y = Math.floor(i / cols) * 14 + 7;
        return <circle key={i} cx={x} cy={y} r={i === 13 ? 3 : 1.6} className={i === 13 ? "dot-grid-hot" : undefined} />;
      })}
    </svg>
  );
}

/** `quiet` shrinks the heading for inline panes. `grid` adds the dot-matrix texture (empty states only). */
export function StateBox({ title, children, action, quiet, grid }: { title: string; children?: ReactNode; action?: ReactNode; quiet?: boolean; grid?: boolean }) {
  return (
    <div className="state-box" data-quiet={quiet || undefined}>
      {grid && <DotGrid />}
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: DotErrorInfo; onRetry?: () => void }) {
  return (
    <StateBox
      title={error.kind === "offline" ? "Backend unreachable" : "Could not load"}
      action={
        onRetry && (
          <button type="button" className="btn" onClick={onRetry}>
            Retry
          </button>
        )
      }
    >
      {error.title}
      {error.hint ? ` ${error.hint}` : ""}
      {error.code !== null ? ` (code ${error.code})` : ""}
    </StateBox>
  );
}

export function Skeleton({ width = "100%", height }: { width?: string; height?: string }) {
  return <div aria-hidden className="skeleton" style={{ width, height }} />;
}

export function Skeletons({ n = 5 }: { n?: number }) {
  return (
    <div aria-hidden style={{ display: "grid", gap: "0.9rem" }}>
      {Array.from({ length: n }, (_, i) => (
        <Skeleton key={i} width={`${90 - ((i * 17) % 40)}%`} />
      ))}
    </div>
  );
}
