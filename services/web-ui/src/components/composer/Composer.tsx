"use client";
import { SendHorizontal, Undo2 } from "lucide-react";
import { useEffect, useId, useImperativeHandle, useMemo, useRef, useState, type Ref } from "react";
import { IconButton, StateDot, useToast } from "@/components/ui";
import { useCap } from "@/lib/api/caps";
import { filterCommands, slashQuery, type CommandDef } from "@/lib/commands/registry";
import { hasUltrathink, splitUltrathink } from "@/lib/effort/levels";
import { useDictation } from "@/lib/voice/dictation";
import { VoiceStrip } from "./VoiceStrip";
import { useVoice } from "@/lib/voice/status";
import { chatStore } from "@/lib/state/store";
import { useApp, type ComposerHandle } from "@/lib/state/app";
import { AttachChips, useAttachments } from "./Attachments";
import { useComposerLayout } from "./useComposerLayout";
import { useDragFiles } from "./useDragFiles";
import { ControlRow, MetaRow } from "./ControlRow";
import { SlashMenu } from "./SlashMenu";
import "./Composer.css";
import "./ComposerMeta.css";

export type { ComposerHandle } from "@/lib/state/app";

const drafts = new Map<string, string>();

export function Composer({ ref }: { ref?: Ref<ComposerHandle | null> }) {
  const app = useApp();
  const { id, phase, chat, commands, composer, telemetry, effort } = app;
  const running = chat.running;
  const blocked = chat.approval !== null || chat.question !== null;
  const [text, setText] = useState("");
  const [active, setActive] = useState(0);
  const [menuOff, setMenuOff] = useState(false);
  const [turnUltra, setTurnUltra] = useState(false);
  const mirror = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const { area, root } = useComposerLayout(text);
  const toast = useToast();
  const att = useAttachments(id, toast);
  const canAttach = useCap("attachments");
  const canBranch = useCap("branch");
  const dictation = useDictation((t) => {
    setText((p) => (p.trim() ? `${p.trimEnd()} ${t}` : t));
    area.current?.focus();
  });
  const dictating = dictation.phase !== "idle";
  const wasDictating = useRef(false);
  useEffect(() => {
    // strip gone (done, cancelled or failed): the text box is back with its draft intact
    if (wasDictating.current && !dictating) area.current?.focus();
    wasDictating.current = dictating;
  }, [dictating, area]);
  const voice = useVoice();
  const canTalk = voice.state === "up" && voice.stt && !!id && !blocked;
  const held = useRef(false);
  const dragging = useDragFiles((f) => (canAttach ? att.add(f) : toast({ title: "Attachments are not available yet", tone: "warn" })));

  useImperativeHandle(ref ?? composer, () => ({ focus: () => area.current?.focus(), setText: (t) => { setText(t); area.current?.focus(); } }), [ref, area, composer]);
  useEffect(() => {
    setText(id ? (drafts.get(id) ?? "") : "");
    setMenuOff(false);
  }, [id]);
  useEffect(() => {
    if (id) drafts.set(id, text);
  }, [id, text]);
  useEffect(() => {
    if (!running) setTurnUltra(false);
  }, [running]);


  const q = slashQuery(text);
  const matches = useMemo(() => (q === null ? [] : filterCommands(commands, q)), [commands, q]);
  const menuOpen = q !== null && !menuOff;
  const idx = Math.min(active, Math.max(0, matches.length - 1));
  const ultra = hasUltrathink(text) || turnUltra;
  const level = ultra ? "max" : effort;
  const lastUser = [...chat.items].reverse().find((i) => i.kind === "user");

  const submit = () => {
    const t = text.trim();
    if (!t || !id || att.busy || blocked) return;
    if (hasUltrathink(t)) setTurnUltra(true);
    if (!app.send(t, att.ids.length ? { attachments: att.ids, attInfo: att.items.flatMap((a) => (a.id ? [{ id: a.id, name: a.name, kind: a.kind }] : [])) } : undefined)) return;
    setText("");
    att.clear();
  };
  const pick = (it: CommandDef) => {
    setText(`/${it.name} `);
    setActive(0);
    area.current?.focus();
  };
  const retract = (qid: string) => {
    const t = id ? chatStore.retract(id, qid) : null;
    if (t) { setText(t); area.current?.focus(); }
  };
  const editLast = () => {
    if (lastUser?.kind !== "user") return;
    if (!canBranch) setText(lastUser.text);
    else void app.branchFromUser(lastUser.id, true);
  };
  const sendAllNow = () => { if (id) void chatStore.sendAllNow(id); };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing) return;
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && chat.queue.length > 0) {
      e.preventDefault();
      sendAllNow();
      return;
    }
    if (menuOpen && matches.length) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setActive((idx + (e.key === "ArrowDown" ? 1 : matches.length - 1)) % matches.length);
        return;
      }
      const sel = matches[idx];
      if ((e.key === "Tab" || (e.key === "Enter" && !e.shiftKey)) && sel && text.trim() !== `/${sel.name}`) {
        e.preventDefault();
        if (sel.available) pick(sel);
        return;
      }
    }
    if (e.key === " " && !text && !e.repeat && !e.ctrlKey && !e.metaKey && !e.altKey && dictation.phase === "idle" && canTalk) {
      e.preventDefault();
      held.current = true;
      dictation.start();
      return;
    }
    if (e.key === " " && e.repeat && held.current && !text) {
      e.preventDefault();
      return;
    }
    if (e.key === "Escape") {
      if (menuOpen) setMenuOff(true);
      else if (running) app.stop();
    } else if (e.key === "ArrowUp" && !text && !running && !menuOpen) {
      e.preventDefault();
      editLast();
    } else if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };
  const onKeyUp = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === " " && held.current) { held.current = false; dictation.stop(); }
  };
  const onPaste = (e: React.ClipboardEvent) => {
    const files = [...e.clipboardData.files];
    if (!files.length) return;
    e.preventDefault();
    if (canAttach) att.add(files);
    else toast({ title: "Attachments are not available yet", tone: "warn" });
  };

  const placeholder = chat.question ? "Answer above first" : blocked ? "Decide above first" : !id ? "Start a chat first" : running ? "Type to queue, Esc stops" : "Ask Dot, or type /";
  const parts = useMemo(() => splitUltrathink(text), [text]);
  const hot = parts.some((p) => p.hot);

  return (
    <div className="composer" ref={root} data-running={running} data-voice={dictating || undefined} data-blocked={blocked || undefined} data-drag={dragging}>
      <div className="composer-body">
      {menuOpen && <SlashMenu id={menuId} items={matches} active={idx} onPick={pick} onHover={setActive} />}
      {chat.queue.length > 0 && (
        <div className="queue-wrap">
          <ul className="queue" aria-label="Queued messages">
            {chat.queue.map((m) => (
              <li key={m.id}>
                <span className="rec">queued</span>
                <span className="queue-txt" dir="auto">{m.text}</span>
                <IconButton size="sm" label="Retract queued message" onClick={() => retract(m.id)}><Undo2 size={14} aria-hidden /></IconButton>
              </li>
            ))}
          </ul>
          <button type="button" className="queue-send" onClick={sendAllNow}>
            <SendHorizontal size={14} aria-hidden />
            Send now{chat.queue.length > 1 ? ` (${chat.queue.length})` : ""}
            <kbd>Ctrl/⌘+Enter</kbd>
          </button>
        </div>
      )}
      <div className="composer-card">
        <AttachChips items={att.items} onRemove={att.remove} onRetry={att.retry} vision={telemetry?.vision ?? false} />
        <div className="composer-field" data-voice={dictating || undefined}>
          <span className="composer-dot"><StateDot state={phase} /></span>
          {dictating && <VoiceStrip d={dictation} />}
          <div className="ta" data-hot={hot}>
            {hot && (
              <div className="ta-mirror" ref={mirror} aria-hidden>
                {parts.map((p, i) => (p.hot ? <mark key={i} className="ultra">{p.text}</mark> : <span key={i}>{p.text}</span>))}
                {"\n"}
              </div>
            )}
            <textarea
              ref={area}
              id="composer"
              rows={1}
              value={text}
              disabled={!id || blocked}
              placeholder={placeholder}
              aria-label="Message"
              aria-autocomplete="list"
              aria-expanded={menuOpen}
              aria-controls={menuOpen ? menuId : undefined}
              aria-activedescendant={menuOpen && matches.length ? `${menuId}-${idx}` : undefined}
              role="combobox"
              autoComplete="off"
              spellCheck
              dir="auto"
              onChange={(e) => { setText(e.target.value); setMenuOff(false); setActive(0); }}
              onScroll={(e) => { if (mirror.current) mirror.current.scrollTop = e.currentTarget.scrollTop; }}
              onKeyDown={onKeyDown}
              onKeyUp={onKeyUp}
              onBlur={() => { if (held.current) { held.current = false; dictation.stop(); } }}
              onPaste={onPaste}
            />
          </div>
        </div>
        <ControlRow
          hasText={text.trim().length > 0}
          level={level}
          ultra={ultra}
          busy={att.busy}
          canAttach={canAttach}
          onFiles={att.add}
          onSubmit={submit}
          dictation={dictation}
        />
      </div>
      <MetaRow />
      </div>
      {dragging && <div className="drop-veil" aria-hidden><span>Drop files to attach</span></div>}
    </div>
  );
}
