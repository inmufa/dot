"use client";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, Dialog, Entry, Input, MenuItem, Sheet, useToast } from "@/components/ui";
import { ErrorBox } from "@/components/ui/StateBox";
import { useResource } from "@/hooks/useResource";
import { api, type MemoryDraft, type MemoryFact } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/api/errors";
import { clip } from "@/lib/util/format";
import { EMPTY, MemoryForm } from "./MemoryForm";
import { Empty, Loading, Meta, PanelBar, RowMenu, stampOf } from "./parts";

export function MemoryPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [confirm, setConfirm] = useState<MemoryFact | null>(null);
  const toast = useToast();
  const r = useResource(() => api.memory(term), open, 0, term);
  const { reload } = r;
  useEffect(() => {
    const t = window.setTimeout(() => setTerm(q.trim()), 250);
    return () => window.clearTimeout(t);
  }, [q]);

  const save = (id: string | null) => async (d: MemoryDraft): Promise<string | null> => {
    try {
      if (id === null) await api.memoryAdd(d);
      else await api.memoryUpdate(id, d);
      setEditing(null);
      setAdding(false);
      reload();
      toast({ title: id === null ? "Fact saved" : "Fact updated", tone: "ok" });
      return null;
    } catch (e) {
      const i = toErrorInfo(e);
      return `${i.title}${i.code !== null ? ` (code ${i.code})` : ""}`;
    }
  };
  const remove = async () => {
    if (!confirm) return;
    try {
      await api.memoryDelete(confirm.id);
      toast({ title: "Fact deleted", tone: "ok" });
      reload();
    } catch (e) {
      toast({ title: "Could not delete the fact", description: toErrorInfo(e).title, tone: "bad" });
    }
    setConfirm(null);
  };
  const n = r.data?.length;

  return (
    <Sheet open={open} onClose={onClose} title="Memory">
      <p className="pn-intro">Notes Dot kept about you and your projects. They are never instructions. Edits apply from the next turn.</p>
      {adding ? (
        <MemoryForm init={EMPTY} onSave={save(null)} onCancel={() => setAdding(false)} />
      ) : (
        <PanelBar count={n === undefined ? "reading" : `${n} ${n === 1 ? "fact" : "facts"}${term ? " found" : ""}`}>
          <Input className="pn-search" type="search" dir="auto" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search facts" aria-label="Search facts" />
          <Button variant="solid" icon={<Plus size={16} />} onClick={() => setAdding(true)}>Add</Button>
        </PanelBar>
      )}
      {r.error ? (
        <ErrorBox error={r.error} onRetry={r.reload} />
      ) : !r.data ? (
        <Loading />
      ) : r.data.length === 0 ? (
        <Empty title={term ? "No fact matches that." : "Nothing logged yet."} action={term ? undefined : <Button icon={<Plus size={16} />} onClick={() => setAdding(true)}>Add a fact</Button>}>
          {term ? "Try fewer words." : "Say \"remember that ...\" in a chat, or add one by hand."}
        </Empty>
      ) : (
        <div className="pn-log">
          {r.data.map((f, i) => (
            <Entry key={f.id} time={stampOf(f.updated_at)} i={Math.min(i, 6)} className="pn-entry">
              {editing === f.id ? (
                <MemoryForm init={f} onSave={save(f.id)} onCancel={() => setEditing(null)} />
              ) : (
                <div className="pn-body">
                  <div className="pn-entry-head">
                    <span className="pn-title" dir="auto" title={f.name}>{clip(f.name, 120)}</span>
                    <span className="pn-act">
                      <RowMenu label={`Actions for ${clip(f.name, 40)}`}>
                        <MenuItem icon={<Pencil size={16} />} onSelect={() => setEditing(f.id)}>Edit</MenuItem>
                        <MenuItem icon={<Trash2 size={16} />} danger onSelect={() => setConfirm(f)}>Delete</MenuItem>
                      </RowMenu>
                    </span>
                  </div>
                  <Meta items={[f.kind]} />
                  {f.description && <p className="pn-desc" dir="auto">{clip(f.description, 200)}</p>}
                  <p className="pn-desc pn-clamp" dir="auto">{f.body}</p>
                </div>
              )}
            </Entry>
          ))}
        </div>
      )}
      <Dialog open={confirm !== null} onClose={() => setConfirm(null)} title="Delete this fact?" confirmLabel="Delete" danger onConfirm={() => void remove()}>
        {confirm ? `"${clip(confirm.name, 80)}" will be removed for good.` : null}
      </Dialog>
    </Sheet>
  );
}
