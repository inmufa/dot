import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";

export type Tone = "neutral" | "accent" | "ok" | "warn" | "bad" | "info";

/** Static label: tinted, no outline. Pair colour with text or icon. */
export function Badge({ tone = "neutral", icon, children, title }: { tone?: Tone; icon?: ReactNode; children: ReactNode; title?: string }) {
  return (
    <span className="badge" data-tone={tone} title={title}>
      {icon && <span className="badge-ic" aria-hidden>{icon}</span>}
      {children}
    </span>
  );
}

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: ReactNode;
  /** Optional mode colour (e.g. "var(--mode-plan)"); tints icon and label. */
  color?: string;
  selected?: boolean;
  ref?: Ref<HTMLButtonElement>;
}

/** Quiet interactive chip (meta row, filters). Selection is a tint; the size never changes. */
export function Chip({ icon, color, selected, children, className, type = "button", style, ref, ...rest }: ChipProps) {
  return (
    <button ref={ref} type={type} className={`chip${className ? ` ${className}` : ""}`} data-selected={selected || undefined} aria-pressed={selected} style={color ? { ...style, "--chip-c": color } as React.CSSProperties : style} {...rest}>
      {icon && <span className="chip-ic" aria-hidden>{icon}</span>}
      {children}
    </button>
  );
}
