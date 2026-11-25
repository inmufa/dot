import { useState } from "react";
import { Button, Input, Sheet } from "@/components/ui";
import { ErrorBox } from "@/components/ui/StateBox";
import type { SkillInfo } from "@/lib/api/client";
import type { DotErrorInfo } from "@/lib/api/errors";
import { Empty, Item, Loading, Meta, PanelBar, Status } from "./parts";

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
        <Loading />
      ) : skills.length === 0 ? (
        <Empty title="No skills installed.">Put a skill folder in .dot/skills in the workspace or in ~/.dot/skills, then type / in the composer.</Empty>
      ) : (
        <>
          <PanelBar count={needle ? `${shown.length} of ${skills.length} skills` : `${skills.length} skills`}>
            <Input className="pn-search" type="search" placeholder="Filter skills" aria-label="Filter skills" value={q} onChange={(e) => setQ(e.target.value)} />
          </PanelBar>
          <ul className="pn-list">
            {shown.map((s) => (
              <Item
                key={s.name}
                text={`/${s.name}`}
                mono
                time={s.source}
                actions={<Button variant="ghost" size="sm" disabled={!s.available} title={s.available ? undefined : (s.reason ?? "Unavailable")} aria-label={`Use /${s.name} in composer`} onClick={() => { onPick(s.name); onClose(); }}>Use</Button>}
              >
                <p className="pn-desc" title={s.description}>{s.description}</p>
                {(!s.available || !s.model_invocable) && <Meta items={[!s.available && <span key="u" data-tone="warn">unavailable</span>, !s.model_invocable && "manual only"]} />}
                {!s.available && s.reason && <Status tone="warn">{s.reason}</Status>}
              </Item>
            ))}
            {shown.length === 0 && <li><Empty title="No skill matches that." /></li>}
          </ul>
        </>
      )}
    </Sheet>
  );
}
