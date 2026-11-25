"use client";
import { useState } from "react";
import { Input, Sheet } from "@/components/ui";
import { ErrorBox } from "@/components/ui/StateBox";
import { useResource } from "@/hooks/useResource";
import { api, type ToolInfo } from "@/lib/api/client";
import { clip } from "@/lib/util/format";
import { Empty, GroupLabel, Item, Loading, Meta, PanelBar } from "./parts";

function Tool({ t }: { t: ToolInfo }) {
  return (
    <Item text={t.name} mono time={t.mutating ? "changes things" : "read-only"}>
      <p className="pn-desc" dir="auto" title={t.description}>{clip(t.description, 300)}</p>
      <Meta items={[t.source === "mcp" && "mcp", t.needs_approval && "asks every time"]} />
    </Item>
  );
}

function Group({ title, tools }: { title: string; tools: ToolInfo[] }) {
  if (tools.length === 0) return null;
  return (
    <>
      <GroupLabel n={tools.length}>{title}</GroupLabel>
      <ul className="pn-list">{tools.map((t) => <Tool key={t.name} t={t} />)}</ul>
    </>
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
        <Loading />
      ) : r.data.length === 0 ? (
        <Empty title="No tools reported.">Is the backend up? Tools come from dot-backend at start.</Empty>
      ) : (
        <>
          <PanelBar count={needle ? `${shown.length} of ${r.data.length} tools` : `${r.data.length} tools`}>
            <Input className="pn-search" type="search" placeholder="Filter tools" aria-label="Filter tools" value={q} onChange={(e) => setQ(e.target.value)} />
          </PanelBar>
          <Group title="core, always in the prompt" tools={shown.filter((t) => !t.deferred)} />
          <Group title="deferred, loaded with ToolSearch" tools={shown.filter((t) => t.deferred)} />
          {shown.length === 0 && <Empty title="No tool matches that." />}
        </>
      )}
    </Sheet>
  );
}
