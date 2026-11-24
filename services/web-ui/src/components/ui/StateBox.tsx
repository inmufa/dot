import type { ReactNode } from "react";
import type { DotErrorInfo } from "@/lib/api/errors";

export function StateBox({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="state-box">
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

export function Skeletons({ n = 5 }: { n?: number }) {
  return (
    <div aria-hidden style={{ display: "grid", gap: "0.9rem" }}>
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="skeleton" style={{ width: `${90 - ((i * 17) % 40)}%` }} />
      ))}
    </div>
  );
}
