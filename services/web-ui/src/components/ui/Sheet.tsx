"use client";
import { X } from "lucide-react";
import { IconButton } from "./Button";
import { useEffect, useId, useRef, type ReactNode } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  center?: boolean;
  danger?: boolean;
  /** Wider side sheet for forms with label-control rows (Settings). */
  wide?: boolean;
}

/** Modal built on <dialog>: focus trap, Esc, inert background and focus return come from the platform. */
export function Sheet({ open, onClose, title, children, center, danger, wide }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions -- backdrop click; Esc closes natively
    <dialog
      ref={ref}
      className={center ? "sheet sheet-center" : wide ? "sheet sheet-wide" : "sheet"}
      data-danger={danger ? "true" : undefined}
      aria-labelledby={id}
      // React bubbles a nested confirm dialog's close through the tree; only our own counts
      onClose={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      {open && (
        <>
          <div className="sheet-head">
            <h2 id={id}>{title}</h2>
            <IconButton label="Close" onClick={onClose}>
              <X size={18} aria-hidden />
            </IconButton>
          </div>
          <div className="sheet-body">{children}</div>
        </>
      )}
    </dialog>
  );
}
