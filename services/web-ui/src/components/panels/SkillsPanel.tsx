import { useState } from "react";
import type { SkillInfo } from "@/lib/api/client";
import type { DotErrorInfo } from "@/lib/api/errors";
import { Sheet } from "../ui/Sheet";
import { ErrorBox, Skeletons, StateBox } from "../ui/StateBox";

interface Props {
  open: boolean;
  onClose: () => void;
  skills: SkillInfo[] | null;
  error: DotErrorInfo | null;
  onRetry: () => void;
  onPick: (name: string) => void;
}

export function SkillsPanel({ open, onClose, skills, error, onRetry, onPick }: Props) {
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const shown = (skills ?? []).filter((s) => !needle || s.name.toLowerCase().includes(needle) || s.description.toLowerCase().includes(needle));
  return (
    <Sheet open={open} onClose={onClose} title="Skills">
      {error ? (
        <ErrorBox error={error} onRetry={onRetry} />
      ) : !skills ? (
        <Skeletons />
      ) : skills.length === 0 ? (
        <StateBox title="No skills found">Put a skill folder in the workspace .dot/skills, in ~/.dot/skills or in the bundled skills directory.</StateBox>
      ) : (
        <>
          <input className="input" type="search" placeholder="Filter skills" aria-label="Filter skills" value={q} onChange={(e) => setQ(e.target.value)} />
          <ul className="rows">
            {shown.map((s) => (
              <li key={s.name} className="row">
                <div className="row-main">
                  <span className="row-title">/{s.name}</span>
                  <span className="badge">{s.source}</span>
                  {!s.available && <span className="badge" data-tone="warn">unavailable</span>}
                  {!s.model_invocable && <span className="badge">manual only</span>}
                </div>
                <p className="row-desc">{s.description}</p>
                {s.reason && <p className="row-desc muted">{s.reason}</p>}
                <button type="button" className="btn btn-sm" disabled={!s.available} onClick={() => { onPick(s.name); onClose(); }}>
                  Use in composer
                </button>
              </li>
            ))}
            {shown.length === 0 && <li><StateBox title="No match">No skill matches that filter.</StateBox></li>}
          </ul>
        </>
      )}
    </Sheet>
  );
}
