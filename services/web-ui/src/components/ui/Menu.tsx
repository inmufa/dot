"use client";
import { Check } from "lucide-react";
import { createContext, useContext, useRef, useState, type KeyboardEvent, type ReactElement, type ReactNode, type RefObject } from "react";
import { Popover } from "./Popover";
import type { Align, Side } from "./position";

interface MenuProps {
  open: boolean;
  onClose: () => void;
  anchorRef: RefObject<HTMLElement | null>;
  children: ReactNode;
  side?: Side | "auto";
  align?: Align;
  label?: string;
  className?: string;
}

const CloseCtx = createContext<(() => void) | null>(null);
const ITEMS = '[role^="menuitem"]:not([aria-disabled="true"])';

/** Roving focus inside a menu: arrows, Home/End, first-letter jump. */
function onMenuKey(e: KeyboardEvent<HTMLDivElement>) {
  const items = Array.from(e.currentTarget.querySelectorAll<HTMLElement>(ITEMS));
  if (!items.length) return;
  const i = items.indexOf(document.activeElement as HTMLElement);
  let n = -1;
  if (e.key === "ArrowDown") n = (i + 1) % items.length;
  else if (e.key === "ArrowUp") n = (i <= 0 ? items.length : i) - 1;
  else if (e.key === "Home") n = 0;
  else if (e.key === "End") n = items.length - 1;
  else if (e.key.length === 1 && /\S/.test(e.key) && !e.metaKey && !e.ctrlKey) {
    const k = e.key.toLowerCase();
    const order = [...items.slice(i + 1), ...items.slice(0, i + 1)];
    const hit = order.find((x) => x.textContent.trim().toLowerCase().startsWith(k));
    if (hit) n = items.indexOf(hit);
  }
  if (n < 0) return;
  e.preventDefault();
  items[n]?.focus();
}

export function Menu({ open, onClose, anchorRef, children, side, align, label, className }: MenuProps) {
  return (
    <Popover open={open} onClose={onClose} anchorRef={anchorRef} side={side} align={align} role="menu" label={label} className={`ui-menu${className ? ` ${className}` : ""}`}>
      {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions -- key handling for the menu role container */}
      <div className="m-inner" onKeyDown={onMenuKey}>{children}</div>
    </Popover>
  );
}

interface ItemProps {
  children: ReactNode;
  onSelect?: () => void;
  icon?: ReactNode;
  hint?: ReactNode;
  danger?: boolean;
  disabled?: boolean;
  /** Renders a check; makes the item a menuitemradio (a menuitemcheckbox with `checkbox`). */
  selected?: boolean;
  /** With `selected`: this item is an independent toggle, not one of a single-choice group. */
  checkbox?: boolean;
  keepOpen?: boolean;
  href?: string;
}

export function MenuItem({ children, onSelect, icon, hint, danger, disabled, selected, checkbox, keepOpen, href }: ItemProps) {
  const close = useContext(CloseCtx);
  const run = () => {
    if (disabled) return;
    onSelect?.();
    if (!keepOpen) close?.();
  };
  const role = selected === undefined ? "menuitem" : checkbox ? "menuitemcheckbox" : "menuitemradio";
  const shared = {
    role,
    tabIndex: -1,
    className: "m-item",
    "data-danger": danger ? "true" : undefined,
    "aria-disabled": disabled || undefined,
    "aria-checked": selected === undefined ? undefined : selected,
  };
  const body = (
    <>
      <span className="m-ic" aria-hidden>{icon}</span>
      <span className="m-label">{children}</span>
      {hint != null && <span className="m-hint">{hint}</span>}
      {selected && <Check size={15} className="m-check" aria-hidden />}
    </>
  );
  if (href) return <a {...shared} href={href} onClick={run}>{body}</a>;
  return <button type="button" {...shared} onClick={run}>{body}</button>;
}

export function MenuSeparator() {
  return <div role="separator" className="m-sep" />;
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <div role="presentation" className="m-title">{children}</div>;
}

interface TriggerProps { ref: RefObject<HTMLButtonElement | null>; onClick: () => void; "aria-haspopup": "menu"; "aria-expanded": boolean; "data-open": boolean | undefined }
interface DropdownProps extends Omit<MenuProps, "open" | "onClose" | "anchorRef" | "children"> {
  trigger: (p: TriggerProps) => ReactElement;
  children: ReactNode;
}

/** Trigger + Menu with its own open state. Items auto-close on select. */
export function DropdownMenu({ trigger, children, ...rest }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);
  const close = () => setOpen(false);
    return (
    <>
      {trigger({ ref, onClick: () => setOpen((o) => !o), "aria-haspopup": "menu", "aria-expanded": open, "data-open": open || undefined })}
      <Menu open={open} onClose={close} anchorRef={ref} {...rest}><CloseCtx.Provider value={close}>{children}</CloseCtx.Provider></Menu>
    </>
  );
}
