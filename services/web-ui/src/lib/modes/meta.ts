import type { PermissionMode } from "@/lib/stream/events";

export interface ModeMeta {
  label: string;
  desc: string;
  /** Glyph drawn inside the shield (see ui/ModeIcon). */
  glyph: "book" | "check" | "pencil" | "spark" | "alert";
}

export const MODE_META: Record<PermissionMode, ModeMeta> = {
  plan: { label: "Plan", desc: "Read-only. Every change is refused.", glyph: "book" },
  default: { label: "Default", desc: "Asks before edits and commands", glyph: "check" },
  acceptEdits: { label: "Accept edits", desc: "File edits go through. Commands still ask.", glyph: "pencil" },
  auto: { label: "Auto", desc: "Edits go through, risky calls still ask", glyph: "spark" },
  bypass: { label: "Bypass", desc: "Never asks, only deny rules apply", glyph: "alert" },
};

/** CSS variable holding the mode colour (defined in styles/brand.css, AA on the page background). */
export const modeVar = (m: PermissionMode): string => `var(--mode-${m})`;
