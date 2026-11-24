"use client";
import { useState } from "react";
import { useResource } from "@/hooks/useResource";
import { api, type ToolInfo } from "@/lib/api/client";
import { clip } from "@/lib/format";
import { Sheet } from "../ui/Sheet";
import { ErrorBox, Skeletons, StateBox } from "../ui/StateBox";

function Tool({ t }: { t: ToolInfo }) {
  return (
    <li className="row">
      <div className="row-main">
        <span className="row-title mono">{t.name}</span>
        {t.source === "mcp" && <span className="badge">mcp</span>}
        <span className="badge" data-tone={t.mutating ? "warn" : "ok"}>{t.mutating ? "changes things" : "read-only"}</span>
        {t.needs_approval && <span className="badge" data-tone="ask">asks every time</span>}
      </div>
      <p className="row-desc muted line-clamp" dir="auto">{clip(t.description, 300)}</p>
    </li>
  );
}

function Group({ title, note, tools }: { title: string; note: string; tools: ToolInfo[] }) {
  if (tools.length === 0) return null;
  return (
    <section className="sys">
      <h3>{title} <span className="muted">({tools.length})</span></h3>
      <p className="muted">{note}</p>
      <ul className="rows">{tools.map((t) => <Tool key={t.name} t={t} />)}</ul>
    </section>
  );
}

export function ToolsPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const r = useResource(api.tools, open);
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const shown = (r.data ?? []).filter((t) => !needle || t.name.toLowerCase().includes(needle) || t.description.toLowerCase().includes(needle));
  return (
    <Sheet open={open} onClose={onClose} title="Tools">
      {r.error ? (
        <ErrorBox error={r.error} onRetry={r.reload} />
      ) : !r.data ? (
        <Skeletons />
      ) : r.data.length === 0 ? (
        <StateBox title="No tools registered">The backend reported an empty tool list.</StateBox>
      ) : (
        <>
          <input className="input" type="search" placeholder="Filter tools" aria-label="Filter tools" value={q} onChange={(e) => setQ(e.target.value)} />
          <Group title="Core" note="Always in Dot's prompt." tools={shown.filter((t) => !t.deferred)} />
          <Group title="Deferred" note="Found and loaded on demand with ToolSearch." tools={shown.filter((t) => t.deferred)} />
          {shown.length === 0 && <StateBox title="No match">No tool matches that filter.</StateBox>}
        </>
      )}
    </Sheet>
  );
}
