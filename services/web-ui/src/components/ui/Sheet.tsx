"use client";
import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  center?: boolean;
  danger?: boolean;
}

/** Modal built on <dialog>: focus trap, Esc, inert background and focus return come from the platform. */
export function Sheet({ open, onClose, title, children, center, danger }: Props) {
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
      className={center ? "sheet sheet-center" : "sheet"}
      data-danger={danger ? "true" : undefined}
      aria-labelledby={id}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      {open && (
        <>
          <div className="sheet-head">
            <h2 id={id}>{title}</h2>
            <button type="button" className="btn btn-ghost btn-icon" onClick={onClose} aria-label="Close">
              <X size={18} aria-hidden />
            </button>
          </div>
          <div className="sheet-body">{children}</div>
        </>
      )}
    </dialog>
  );
}
