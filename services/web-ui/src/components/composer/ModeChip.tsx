"use client";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Dialog, DropdownMenu, MenuItem } from "@/components/ui";
import { MODE_META } from "@/lib/modes/meta";
import { MODES, type PermissionMode } from "@/lib/stream/events";

export const MODE_INFO = MODE_META;

interface Props {
  mode: PermissionMode | null;
  disabled: boolean;
  onChange: (m: PermissionMode) => void;
}

/** Mode chip (colour + icon + label) that opens the kit menu; bypass asks for confirmation. */
export function ModeSwitcher({ mode, disabled, onChange }: Props) {
  const [confirm, setConfirm] = useState(false);
  const info = mode ? MODE_INFO[mode] : null;
  const pick = (m: PermissionMode) => {
    if (m === mode) return;
    if (m === "bypass") setConfirm(true);
    else onChange(m);
  };
  return (
    <>
      <DropdownMenu
        side="top"
        align="start"
        label="Permission mode"
        className="mode-menu"
        trigger={(t) => (
          <button
            {...t}
            type="button"
            className="meta-model meta-mode"
            data-mode={mode ?? undefined}
            disabled={disabled || !mode}
            aria-label={`mode ${info?.label ?? "Default"}, Permission mode menu`}
          >
            <span className="meta-name">{info?.label ?? "Default"}</span>
            <ChevronDown size={14} aria-hidden className="mode-chev" />
          </button>
        )}
      >
        {MODES.map((m) => (
          <MenuItem key={m} selected={m === mode} onSelect={() => pick(m)}>
            <span className="mode-txt" data-mode={m}>
              <span className="mode-title">{MODE_INFO[m].label}</span>
              <span className="mode-desc">{MODE_INFO[m].desc}</span>
            </span>
          </MenuItem>
        ))}
      </DropdownMenu>
      <Dialog
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Enable bypass mode?"
        danger
        cancelLabel={`Keep ${info?.label ?? "current"} mode`}
        confirmLabel="Enable bypass"
        onConfirm={() => {
          setConfirm(false);
          onChange("bypass");
        }}
      >
        <p className="confirm-text">
          Dot will run edits and shell commands without asking you. Deny rules still apply, nothing else stops a bad
          command. Use it only in a workspace you can restore.
        </p>
      </Dialog>
    </>
  );
}
