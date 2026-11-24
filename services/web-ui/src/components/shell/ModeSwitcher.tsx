"use client";
import { ChevronDown, ShieldAlert } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { MODES, type PermissionMode } from "@/lib/stream/events";
import { Sheet } from "../ui/Sheet";

export const MODE_INFO: Record<PermissionMode, { label: string; desc: string }> = {
  plan: { label: "Plan", desc: "Read-only. Every change is refused." },
  default: { label: "Default", desc: "Asks before edits and commands." },
  acceptEdits: { label: "Accept edits", desc: "File edits go through. Commands still ask." },
  auto: { label: "Auto", desc: "A classifier decides. Risky calls still ask." },
  bypass: { label: "Bypass", desc: "Runs without asking. Only deny rules apply." },
};

interface Props {
  mode: PermissionMode | null;
  disabled: boolean;
  onChange: (m: PermissionMode) => void;
}

export function ModeSwitcher({ mode, disabled, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [idx, setIdx] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const list = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const pick = (m: PermissionMode) => {
    setOpen(false);
    root.current?.querySelector("button")?.focus();
    if (m === mode) return;
    if (m === "bypass") setConfirm(true);
    else onChange(m);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
      root.current?.querySelector("button")?.focus();
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setIdx((i) => (i + (e.key === "ArrowDown" ? 1 : MODES.length - 1)) % MODES.length);
    } else if (e.key === "Enter" && open) {
      e.preventDefault();
      pick(MODES[idx] ?? "default");
    }
  };

  const info = mode ? MODE_INFO[mode] : null;
  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- key events bubble from the listbox
    <div className="mode" ref={root} onKeyDown={onKey}>
      <button
        type="button"
        className="btn mode-btn"
        data-mode={mode ?? undefined}
        disabled={disabled || !mode}
        aria-haspopup="listbox"
        aria-label={`mode ${info?.label ?? "none"}, Permission mode menu`}
        aria-expanded={open}
        aria-controls={open ? list : undefined}
        onClick={() => {
          setIdx(Math.max(0, MODES.indexOf(mode ?? "default")));
          setOpen((o) => !o);
        }}
      >
        {mode === "bypass" && <ShieldAlert size={16} aria-hidden />}
        <span className="mode-key">mode</span>{" "}
        <span>{info?.label ?? "none"}</span>
        <ChevronDown size={14} aria-hidden />
      </button>
      {open && (
        <ul className="menu" id={list} role="listbox" aria-label="Permission mode" aria-activedescendant={`${list}-${idx}`} tabIndex={-1} ref={(el) => el?.focus()}>
          {MODES.map((m, i) => (
            // eslint-disable-next-line jsx-a11y/click-events-have-key-events -- keys handled on the listbox
            <li
              key={m}
              id={`${list}-${i}`}
              role="option"
              aria-selected={m === mode}
              data-active={i === idx}
              data-mode={m}
              onMouseEnter={() => setIdx(i)}
              onClick={() => pick(m)}
            >
              <span className="menu-title">{MODE_INFO[m].label}{m === mode ? " (current)" : ""}</span>
              <span className="menu-desc">{MODE_INFO[m].desc}</span>
            </li>
          ))}
        </ul>
      )}
      <Sheet open={confirm} onClose={() => setConfirm(false)} title="Enable bypass mode?" center danger>
        <p className="confirm-text">
          Dot will run edits and shell commands without asking you. Deny rules still apply, nothing else stops a bad
          command. Use it only in a workspace you can restore.
        </p>
        <div className="confirm-actions">
          {/* eslint-disable-next-line jsx-a11y/no-autofocus -- safe default for the destructive dialog */}
          <button type="button" className="btn" autoFocus onClick={() => setConfirm(false)}>
            Keep {info?.label ?? "current"} mode
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => {
              setConfirm(false);
              onChange("bypass");
            }}
          >
            Enable bypass
          </button>
        </div>
      </Sheet>
    </div>
  );
}
