"use client";
import type { ReactNode } from "react";
import { Button } from "./Button";
import { Sheet } from "./Sheet";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  children?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  danger?: boolean;
  busy?: boolean;
}

/** Small centered confirm dialog: one primary action, one quiet cancel. Esc and backdrop cancel. */
export function Dialog({ open, onClose, title, children, confirmLabel = "Confirm", cancelLabel = "Cancel", onConfirm, danger, busy }: Props) {
  return (
    <Sheet open={open} onClose={onClose} title={title} center danger={danger}>
      {children && <div className="dlg-body">{children}</div>}
      <div className="dlg-actions">
        <Button variant="ghost" onClick={onClose}>{cancelLabel}</Button>
        <Button variant={danger ? "danger" : "solid"} onClick={onConfirm} loading={busy} data-autofocus>{confirmLabel}</Button>
      </div>
    </Sheet>
  );
}
