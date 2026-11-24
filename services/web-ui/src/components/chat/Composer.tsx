"use client";
import { ArrowUp, Square } from "lucide-react";
import { useEffect, useId, useImperativeHandle, useLayoutEffect, useMemo, useRef, useState, type Ref } from "react";
import type { SkillInfo } from "@/lib/api/client";
import { filterSlash, slashItems, slashQuery, type SlashItem } from "@/lib/slash";
import type { DotPhase } from "@/lib/stream/reducer";
import { StateDot } from "../ui/StateDot";
import { SlashMenu } from "./SlashMenu";

export interface ComposerHandle {
  focus: () => void;
  setText: (t: string) => void;
}

interface Props {
  ref?: Ref<ComposerHandle>;
  sessionId: string | null;
  phase: DotPhase;
  running: boolean;
  blocked: boolean;
  blockedText?: string;
  skills: SkillInfo[];
  onSend: (text: string) => void;
  onStop: () => void;
}

const drafts = new Map<string, string>();

export function Composer({ ref, sessionId, phase, running, blocked, blockedText, skills, onSend, onStop }: Props) {
  const [text, setText] = useState("");
  const [active, setActive] = useState(0);
  const [menuOff, setMenuOff] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null);
  const menuId = useId();

  useImperativeHandle(ref, () => ({ focus: () => area.current?.focus(), setText: (t) => { setText(t); area.current?.focus(); } }), []);

  useEffect(() => {
    setText(sessionId ? (drafts.get(sessionId) ?? "") : "");
    setMenuOff(false);
  }, [sessionId]);
  useEffect(() => {
    if (sessionId) drafts.set(sessionId, text);
  }, [sessionId, text]);

  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, window.innerHeight * 0.4)}px`;
  }, [text]);

  const all = useMemo(() => slashItems(skills), [skills]);
  const q = slashQuery(text);
  const matches = useMemo(() => (q === null ? [] : filterSlash(all, q)), [all, q]);
  const menuOpen = q !== null && !menuOff;
  const idx = Math.min(active, Math.max(0, matches.length - 1));

  const submit = () => {
    const t = text.trim();
    if (!t || !sessionId) return;
    if (running && !t.startsWith("/stop")) return;
    setText("");
    onSend(t);
  };

  const pick = (it: SlashItem) => {
    setText(`/${it.name} `);
    setActive(0);
    area.current?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing) return;
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
    if (e.key === "Escape") {
      if (menuOpen) setMenuOff(true);
      else if (running) onStop();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const placeholder = blocked
    ? (blockedText ?? "Decide above first")
    : running
      ? "Working. Esc to stop"
      : sessionId
        ? "Ask Dot, or type /"
        : "Start a session first";

  return (
    <div className="composer">
      {menuOpen && <SlashMenu id={menuId} items={matches} active={idx} onPick={pick} onHover={setActive} />}
      <div className="composer-box">
        <span className="composer-dot"><StateDot state={phase} /></span>
        <textarea
          ref={area}
          rows={1}
          value={text}
          disabled={!sessionId || blocked}
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
          onChange={(e) => {
            setText(e.target.value);
            setMenuOff(false);
            setActive(0);
          }}
          onKeyDown={onKeyDown}
        />
        {running ? (
          <button type="button" className="btn btn-icon send" onClick={onStop} aria-label="Stop" title="Stop (Esc)">
            <Square size={14} fill="currentColor" aria-hidden />
          </button>
        ) : (
          <button type="button" className="btn btn-primary btn-icon send" onClick={submit} disabled={!text.trim() || !sessionId || blocked} aria-label="Send" title="Send (Enter)">
            <ArrowUp size={18} aria-hidden />
          </button>
        )}
      </div>
      <p className="composer-hint">
        <kbd>Enter</kbd> send <kbd>Shift</kbd>+<kbd>Enter</kbd> new line <kbd>/</kbd> commands
      </p>
    </div>
  );
}
