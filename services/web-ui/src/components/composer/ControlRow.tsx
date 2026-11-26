"use client";
import { ArrowUp, Brain, Cpu, ListChecks, Paperclip, Plus, Square, Telescope } from "lucide-react";
import { useRef } from "react";
import { Chip, DropdownMenu, IconButton, MenuItem, Tooltip, useToast } from "@/components/ui";
import type { Effort } from "@/lib/api/types";
import { ContextMeter } from "@/components/shell/ContextMeter";
import { useApp } from "@/lib/state/app";
import type { Dictation } from "@/lib/voice/dictation";
import { MicButton } from "./MicButton";
import { ModeSwitcher } from "./ModeChip";

interface Props {
  hasText: boolean;
  level: Effort;
  ultra: boolean;
  busy: boolean;
  canAttach: boolean;
  onFiles: (f: File[]) => void;
  onSubmit: () => void;
  dictation: Dictation;
}

/** Short display name: drop quant and vendor noise. */
export const shortModel = (m: string): string => m.replace(/\.gguf$/i, "").replace(/[-_](Q\d\w*|IQ\d\w*|BF16|F16)$/i, "").replace(/-?(Uncensored|HauhauCS|Aggressive)/gi, "").replace(/^[-_ ]+|[-_ ]+$/g, "");

/** One slim row: "+" menu and Plan on the left; Think, mic, send on the right. */
export function ControlRow({ hasText, level, ultra, busy, canAttach, onFiles, onSubmit, dictation }: Props) {
  const app = useApp();
  const toast = useToast();
  const { id, chat, S, telemetry, ui, researchOn } = app;
  const why = id ? undefined : "Start a chat first";
  const file = useRef<HTMLInputElement>(null);
  const mode = S.active?.mode ?? null;
  const planning = app.planOn || mode === "plan";
  const togglePlan = () => {
    if (mode === "plan") void app.changeMode("default");
    else app.togglePlan();
  };
  const running = chat.running;
  const blocked = chat.approval !== null || chat.question !== null;
  const stop = running && !hasText && !blocked;
  const model = telemetry?.model ? telemetry.model.replace(/\.gguf$/i, "") : null;
  const sendWhy = blocked ? "Decide above first" : !id ? "Start a chat first" : busy ? "Uploading files" : dictation.phase !== "idle" ? "Finish the recording first" : !hasText ? "Type a message" : undefined;
  const sendOff = !stop && sendWhy !== undefined;
  return (
    <div className="ctl">
      <div className="ctl-l">
        <input ref={file} type="file" multiple hidden onChange={(e) => { onFiles([...(e.target.files ?? [])]); e.target.value = ""; }} />
        <DropdownMenu
          side="top"
          align="start"
          label="Add and tools"
          trigger={(t) => (
            <Tip text={why}>
              <IconButton {...t} onClick={id ? t.onClick : undefined} label="Add and tools" className="ctl-plus" aria-disabled={!id || undefined}>
                <Plus size={18} aria-hidden />
              </IconButton>
            </Tip>
          )}
        >
          <MenuItem icon={<Paperclip size={16} />} hint="from this computer" onSelect={() => { if (canAttach) file.current?.click(); else toast({ title: "Attachments are not available yet", tone: "warn" }); }}>Add photos and files</MenuItem>
          <MenuItem icon={<Telescope size={16} />} hint="cited report" selected={researchOn} checkbox onSelect={app.toggleResearch}>Research</MenuItem>
          {model && <MenuItem icon={<Cpu size={16} />} hint={shortModel(model)} onSelect={() => ui.openOverlay("model")}>Change model</MenuItem>}
        </DropdownMenu>
        <Tip text={why ?? (planning ? "Plan is on for the next message: read-only until you approve, then it runs in your current mode" : "Plan first: Dot proposes a plan, then runs it in your current mode")}>
          <Chip className="ctl-chip plan" aria-label="Plan" icon={<ListChecks size={16} />} selected={planning} color={planning ? "var(--mode-plan)" : undefined} aria-disabled={!id || undefined} onClick={id ? togglePlan : undefined}>
            <span className="ctl-lbl">Plan</span>
          </Chip>
        </Tip>
      </div>
      <div className="ctl-r">
        <Tip text={why ?? "Think deeper (Ctrl+Shift+E). Typing ultrathink does it for one message"}>
          <Chip className="ctl-chip think" aria-label="Think" icon={<Brain size={16} />} selected={level === "max"} color={level === "max" ? "var(--accent-text)" : undefined} data-ultra={ultra} aria-disabled={!id || undefined} onClick={id ? app.toggleDeep : undefined}>
            <span className="ctl-lbl">Think</span>
          </Chip>
        </Tip>
        <Tip text={why}><MicButton d={dictation} disabled={!id} /></Tip>
        <button
          type="button"
          className="send"
          data-run={stop}
          data-blocked={blocked || undefined}
          onClick={sendOff ? undefined : stop ? app.stop : onSubmit}
          aria-disabled={sendOff || undefined}
          aria-label={stop ? "Stop" : running ? "Queue message" : "Send"}
          title={sendOff ? sendWhy : stop ? "Stop (Esc)" : running ? "Queue (Enter)" : "Send (Enter)"}
        >
          <ArrowUp size={18} strokeWidth={2.4} aria-hidden className="send-up" />
          <Square size={13} fill="currentColor" aria-hidden className="send-stop" />
        </button>
      </div>
    </div>
  );
}

/** Tooltip only when there is a reason to show (disabled controls explain themselves). */
function Tip({ text, children }: { text: string | undefined; children: React.ReactElement }) {
  return text ? <Tooltip text={text} side="top">{children}</Tooltip> : children;
}

/** Status row under the card: mode and Research chips, context and model. */
export function MetaRow() {
  const app = useApp();
  const { id, S, chat, telemetry, ui, researchOn } = app;
  const model = telemetry?.model ? shortModel(telemetry.model) : null;
  return (
    <div className="meta">
      <div className="meta-l">
        <ModeSwitcher mode={S.active?.mode === "acceptEdits" ? "auto" : (S.active?.mode ?? null)} disabled={!id} onChange={(m) => void app.changeMode(m)} />
        {researchOn && (
          <Chip className="meta-research" icon={<Telescope size={14} />} selected color="var(--accent-text)" onClick={app.toggleResearch} title="Research is on. Click to turn off">Research</Chip>
        )}
      </div>
      <div className="meta-r">
        <ContextMeter compact usage={chat.usage} sessionId={S.activeId} running={chat.running} />
        {model && (
          <button type="button" className="meta-model" onClick={() => ui.openOverlay("model")} title={`Model: ${telemetry?.model}. Click to change`}>
            <span className="meta-name">{model}</span>
          </button>
        )}
      </div>
    </div>
  );
}
