"use client";
import { Archive, MoreHorizontal, Pencil, Pin, PinOff, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { SessionInfo } from "@/lib/api/client";
import { Bullet, Dialog, DropdownMenu, ListRow, MenuItem, StateDot } from "@/components/ui";
import type { DotPhase } from "@/lib/stream/reducer";
import { lastActive } from "@/lib/util/days";
import { sessionTitle } from "@/lib/util/format";
import { indexTime } from "@/lib/util/indexTime";
import { useTyped } from "@/lib/util/useTyped";

interface Props {
  s: SessionInfo;
  phase: DotPhase;
  current: boolean;
  actions: boolean;
  onSelect: () => void;
  onPatch: (p: { title?: string; pinned?: boolean; archived?: boolean }) => void;
  onDelete: () => void;
}

/** One chat line: title, dotted leader, time, menu with inline rename and delete confirm. */
export function SessionRow({ s, phase, current, actions, onSelect, onPatch, onDelete }: Props) {
  const [edit, setEdit] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const name = sessionTitle(s.title);
  const title = useTyped(name);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!edit) return;
    const t = window.setTimeout(() => input.current?.select(), 30);
    return () => window.clearTimeout(t);
  }, [edit]);

  const commit = (v: string) => {
    setEdit(false);
    const t = v.trim();
    if (t && t !== (s.title ?? "")) onPatch({ title: t });
  };
  const lead = phase !== "idle" ? <StateDot state={phase} /> : current ? <Bullet /> : null;

  return (
    <li className="sb-item" data-active={current || undefined}>
      {edit ? (
        <div className="sb-edit">
          <input
            ref={input}
            className="sb-rename"
            defaultValue={s.title ?? ""}
            aria-label="Chat title"
            dir="auto"
            maxLength={120}
            onBlur={(e) => commit(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") commit(e.currentTarget.value); if (e.key === "Escape") setEdit(false); }}
          />
        </div>
      ) : (
        <div onDoubleClick={() => actions && setEdit(true)}>
          <ListRow
            className="sb-row"
            lead={lead}
            title={<span className="sb-title" dir="auto" title={`${name}  ${indexTime(lastActive(s))}`}>{title}</span>}
            leader
            time={<>{indexTime(lastActive(s))}{phase !== "idle" && <span className="sr-only">{phase === "waiting" ? ", needs approval" : ", working"}</span>}</>}
            selected={current}
            onSelect={onSelect}
            actions={actions && (
              <DropdownMenu
                align="end"
                label={`Actions for ${name}`}
                trigger={(p) => (
                  <button type="button" {...p} className="sb-more" aria-label={`Actions for ${name}`}>
                    <MoreHorizontal size={16} aria-hidden />
                  </button>
                )}
              >
                <MenuItem icon={<Pencil size={16} />} onSelect={() => setEdit(true)}>Rename</MenuItem>
                <MenuItem icon={s.pinned ? <PinOff size={16} /> : <Pin size={16} />} onSelect={() => onPatch({ pinned: !s.pinned })}>{s.pinned ? "Unpin" : "Pin"}</MenuItem>
                <MenuItem icon={<Archive size={16} />} onSelect={() => onPatch({ archived: true })}>Archive</MenuItem>
                <MenuItem icon={<Trash2 size={16} />} danger onSelect={() => setConfirm(true)}>Delete</MenuItem>
              </DropdownMenu>
            )}
          />
        </div>
      )}
      <Dialog open={confirm} onClose={() => setConfirm(false)} title="Delete this chat?" confirmLabel="Delete" danger onConfirm={() => { setConfirm(false); onDelete(); }}>
        <span dir="auto">&quot;{name}&quot;</span> and its messages will be removed for good.
      </Dialog>
    </li>
  );
}
