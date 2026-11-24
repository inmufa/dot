import { PlugZap, RefreshCw } from "lucide-react";
import type { Link } from "@/hooks/useConnection";
import type { DotErrorInfo } from "@/lib/api/errors";

export function Banner({ link, error, backend, onRetry }: { link: Link; error: DotErrorInfo | null; backend: string | null; onRetry: () => void }) {
  if (link === "online" || link === "checking") return null;
  const offline = link === "offline";
  return (
    <div className="banner" role="alert" data-tone={offline ? "bad" : "warn"}>
      <PlugZap size={16} aria-hidden />
      <p>
        <strong>{offline ? "Backend unreachable." : "Backend is up but not ready."}</strong>{" "}
        {error?.hint ?? "Check the backend."} {backend ? <code>{backend}</code> : null}
      </p>
      <button type="button" className="btn btn-sm" onClick={onRetry}>
        <RefreshCw size={14} aria-hidden /> Retry
      </button>
    </div>
  );
}
