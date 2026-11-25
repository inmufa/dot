"use client";
import { Check, Copy, Eye } from "lucide-react";
import { useEffect, useState } from "react";
import "./ModelPicker.css";
import { Badge, Bullet, Button, ErrorBox, Sheet, Skeletons, useToast } from "@/components/ui";
import { api, type ModelInfo } from "@/lib/api/client";
import { toErrorInfo, type DotErrorInfo } from "@/lib/api/errors";
import { useApp } from "@/lib/state/app";
import { compactTokens } from "@/lib/util/format";

const gb = (mb: number) => `${(mb / 1024).toFixed(1)} GB`;

function CopyCommand({ cmd }: { cmd: string }) {
  const toast = useToast();
  const [done, setDone] = useState(false);
  const copy = () => {
    const clip = navigator.clipboard as Clipboard | undefined;
    if (!clip) { toast({ title: "Could not copy. Select the command by hand.", tone: "warn" }); return; }
    clip.writeText(cmd).then(() => {
      setDone(true);
      toast({ title: "Copied", tone: "ok", ms: 2200 });
      window.setTimeout(() => setDone(false), 1600);
    }, () => toast({ title: "Could not copy.", tone: "warn" }));
  };
  return (
    <div className="mp-cmd">
      <code className="rec" dir="ltr">{cmd}</code>
      <Button size="sm" variant="ghost" onClick={copy} aria-label={`Copy command: ${cmd}`}>
        {done ? <Check size={16} aria-hidden /> : <Copy size={16} aria-hidden />}Copy
      </Button>
    </div>
  );
}

/** The model list. The UI cannot switch models: inactive ones show the host command that does. */
export function ModelPicker() {
  const { ui } = useApp();
  const open = ui.overlay === "model";
  const [models, setModels] = useState<ModelInfo[] | null>(null);
  const [err, setErr] = useState<DotErrorInfo | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!open) return;
    let live = true;
    api.models().then((m) => { if (live) { setModels(m); setErr(null); } }, (e: unknown) => { if (live) setErr(toErrorInfo(e)); });
    return () => { live = false; };
  }, [open, tick]);

  const list = (models ?? []).filter((m) => m.listed || m.active);
  return (
    <Sheet open={open} onClose={ui.closeOverlay} title="Models">
      <div className="mp">
        <p className="mp-lead">Dot runs one model at a time. Switching happens on the host.</p>
        {err ? <ErrorBox error={err} onRetry={() => setTick((t) => t + 1)} />
          : !models ? <Skeletons n={3} />
          : list.length === 0 ? <p className="mp-lead">No models found.</p>
          : (
            <ul className="mp-list">
              {list.map((m) => (
                <li key={m.name} className="mp-item" data-active={m.active || undefined}>
                  <div className="mp-head">
                    <span className="mp-mark">{m.active ? <Bullet /> : null}</span>
                    <span className="mp-name" dir="auto" title={m.name}>{m.display_name || m.name}</span>
                    {m.vision && <Badge icon={<Eye size={12} />}>vision</Badge>}
                    {m.active && <span className="mp-on rec">active</span>}
                  </div>
                  <p className="mp-meta rec">{gb(m.size_mb)}{m.context_max > 0 && <> · {compactTokens(m.context_max)} context</>}{m.thinking && <> · thinking</>}</p>
                  {!m.active && m.switch_command && <CopyCommand cmd={m.switch_command} />}
                </li>
              ))}
            </ul>
          )}
      </div>
    </Sheet>
  );
}
