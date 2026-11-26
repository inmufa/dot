"use client";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, MenuItem, Sheet, useToast } from "@/components/ui";
import { ErrorBox } from "@/components/ui/StateBox";
import { useResource } from "@/hooks/useResource";
import { api, type ScheduleInfo } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/api/errors";
import { describeCron, parseCron } from "@/lib/util/cron";
import { clip, relativeTime } from "@/lib/util/format";
import { Empty, Item, Loading, Meta, PanelBar, RowMenu, Status } from "./parts";
import { ScheduleForm, stamp } from "./ScheduleForm";

function human(cron: string): string {
  const r = parseCron(cron);
  return r.ok ? describeCron(r.fields) : "Custom schedule";
}

function Row({ s, onDelete }: { s: ScheduleInfo; onDelete: (s: ScheduleInfo) => void }) {
  const last = s.last_run_at ? `${relativeTime(s.last_run_at)} ago${s.last_status ? `, ${s.last_status}` : ""}` : "never";
  return (
    <Item
      text={human(s.cron)}
      time={s.enabled ? stamp(s.next_run_at) : "paused"}
      actions={s.kind === "user" ? (
        <RowMenu label={`Actions for schedule ${clip(s.cron, 30)}`}>
          <MenuItem icon={<Trash2 size={16} />} danger onSelect={() => onDelete(s)}>Delete</MenuItem>
        </RowMenu>
      ) : undefined}
    >
      <Meta items={[<span key="c" className="mono" title={s.cron}>{clip(s.cron, 40)}</span>, s.kind === "builtin" && "built-in", <span key="l">last {last}</span>, <Status key="st" tone={s.enabled ? "ok" : "warn"}>{s.enabled ? "active" : "paused"}</Status>]} />
      <p className="pn-desc" dir="auto" title={s.prompt}>{clip(s.prompt, 220)}</p>
    </Item>
  );
}

export function SchedulesPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const r = useResource(api.schedules, open);
  const [adding, setAdding] = useState(false);
  const [confirm, setConfirm] = useState<ScheduleInfo | null>(null);
  const toast = useToast();
  const del = async () => {
    if (!confirm) return;
    try {
      await api.scheduleDelete(confirm.id);
      toast({ title: "Schedule deleted", tone: "ok" });
      r.reload();
    } catch (e) {
      toast({ title: "Could not delete the schedule", description: toErrorInfo(e).title, tone: "bad" });
    }
    setConfirm(null);
  };
  const n = r.data?.length;
  return (
    <Sheet open={open} onClose={onClose} title="Schedules" description="Prompts Dot runs on a timer, each in a fresh chat. Steps that need your approval wait for you.">
      {adding ? (
        <ScheduleForm onDone={() => { setAdding(false); r.reload(); }} onCancel={() => setAdding(false)} />
      ) : (
        <PanelBar count={n === undefined ? "reading" : `${n} ${n === 1 ? "schedule" : "schedules"}`}>
          <Button variant="solid" icon={<Plus size={16} />} onClick={() => setAdding(true)}>New schedule</Button>
        </PanelBar>
      )}
      {r.error && !r.data ? (
        <ErrorBox error={r.error} onRetry={r.reload} />
      ) : !r.data ? (
        <Loading />
      ) : r.data.length === 0 ? (
        <Empty title="Nothing scheduled." action={<Button icon={<Plus size={16} />} onClick={() => setAdding(true)}>New schedule</Button>}>A daily summary at 09:00 is a good first one.</Empty>
      ) : (
        <ul className="pn-list">{r.data.map((s) => <Row key={s.id} s={s} onDelete={setConfirm} />)}</ul>
      )}
      <Dialog open={confirm !== null} onClose={() => setConfirm(null)} title="Delete this schedule?" confirmLabel="Delete" danger onConfirm={() => void del()}>
        {confirm ? `${human(confirm.cron)} will stop running.` : null}
      </Dialog>
    </Sheet>
  );
}
