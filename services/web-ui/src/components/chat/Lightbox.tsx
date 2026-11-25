"use client";
import { ChevronLeft, ChevronRight, Download, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { IconButton } from "@/components/ui";

export interface LightboxItem {
  src: string;
  name: string;
}

interface Props {
  items: LightboxItem[];
  /** Open image index, or null when closed. */
  index: number | null;
  onIndex: (i: number) => void;
  onClose: () => void;
}

/** Full-screen image viewer on a native <dialog>: focus trap, Esc and focus return come from the platform. Arrows browse. */
export function Lightbox({ items, index, onIndex, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [closing, setClosing] = useState(false);
  const open = index !== null && items.length > 0;
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) { setClosing(false); d.showModal(); }
    if (!open && d.open) d.close();
  }, [open]);
  const n = items.length;
  const cur = index !== null ? items[index] : undefined;
  const step = (by: number) => { if (index !== null && n > 1) onIndex((index + by + n) % n); };
  // Exit plays 100ms before the dialog closes.
  const close = () => {
    setClosing(true);
    window.setTimeout(() => { ref.current?.close(); }, 100);
  };
  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- backdrop click; Esc closes natively
    <dialog
      ref={ref}
      className="lb"
      data-state={closing ? "closed" : "open"}
      aria-label={cur ? `Image ${cur.name}` : "Image"}
      onClose={onClose}
      onCancel={(e) => { e.preventDefault(); close(); }}
      onKeyDown={(e) => { if (e.key === "ArrowRight") step(1); else if (e.key === "ArrowLeft") step(-1); }}
      onClick={(e) => { if (e.target === ref.current || (e.target as HTMLElement).classList.contains("lb-stage")) close(); }}
    >
      {open && cur && (
        <>
          <div className="lb-bar">
            <a className="btn btn-ghost btn-icon btn-md" href={cur.src} download={cur.name} aria-label={`Download ${cur.name}`}><Download size={18} aria-hidden /></a>
            <IconButton label="Close" onClick={close}><X size={18} aria-hidden /></IconButton>
          </div>
          <div className="lb-stage">
            {n > 1 && <IconButton className="lb-nav lb-prev" label="Previous image" onClick={() => step(-1)}><ChevronLeft size={20} aria-hidden /></IconButton>}
            {/* key restarts the fade when browsing */}
            <img key={cur.src} className="lb-img" src={cur.src} alt={cur.name} />
            {n > 1 && <IconButton className="lb-nav lb-next" label="Next image" onClick={() => step(1)}><ChevronRight size={20} aria-hidden /></IconButton>}
          </div>
          <p className="lb-cap rec" aria-live="polite" title={cur.name}>{cur.name}{n > 1 && ` · ${index + 1} / ${n}`}</p>
        </>
      )}
    </dialog>
  );
}
