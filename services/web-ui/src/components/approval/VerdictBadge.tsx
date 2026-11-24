import type { ClassifierVerdict } from "@/lib/stream/events";

const TEXT = { allow: "Classifier: safe", ask: "Classifier: unsure", deny: "Classifier: risky" } as const;

export function VerdictBadge({ verdict }: { verdict: ClassifierVerdict }) {
  return (
    <span className="badge" data-tone={verdict.decision} title={`${verdict.stage}: ${verdict.reason}`}>
      {TEXT[verdict.decision]}
    </span>
  );
}
