"use client";
import { Eye, X } from "lucide-react";
import { Button, IconButton } from "@/components/ui";
import { usePreviewOffer } from "./usePreviewOffer";
import "./canvas.css";

/** Quiet line above the composer: the agent wrote a previewable file, open it in the canvas. */
export function PreviewOffer() {
  const offer = usePreviewOffer();
  if (!offer) return null;
  return (
    <div className="cv-offer" role="status">
      <Button variant="ghost" size="sm" className="cv-offer-open" icon={<Eye size={14} />} onClick={offer.open}>
        Open preview <span className="cv-offer-name">{offer.path}</span>
      </Button>
      <IconButton label="Dismiss preview offer" size="sm" onClick={offer.dismiss}><X size={14} aria-hidden /></IconButton>
    </div>
  );
}
