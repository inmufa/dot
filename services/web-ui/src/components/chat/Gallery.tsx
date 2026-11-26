"use client";
import { Check, Download, Images, Share2 } from "lucide-react";
import { useState } from "react";
import type { GalleryItem } from "@/lib/util/markdown";
import { Lightbox } from "./Lightbox";

/** Browser URL for an image: remote and workspace paths go through the media proxy. */
export function mediaUrl(src: string): string {
  return src.startsWith("data:") ? src : `/api/dot/v1/media?src=${encodeURIComponent(src)}`;
}

function fileName(it: GalleryItem): string {
  const base = it.src.split(/[?#]/)[0]?.split("/").pop() ?? "";
  return base && /\.[a-z0-9]{2,5}$/i.test(base) ? base : `${it.alt.trim().slice(0, 40) || "image"}.png`;
}

function Tile({ it, i, onOpen }: { it: GalleryItem; i: number; onOpen: (i: number) => void }) {
  const [state, setState] = useState<"load" | "ok" | "fail">("load");
  const [copied, setCopied] = useState(false);
  const url = mediaUrl(it.src);
  const original = /^https?:\/\//i.test(it.src) ? it.src : new URL(url, window.location.href).href;
  const copy = () => {
    void navigator.clipboard.writeText(original).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    });
  };
  if (state === "fail") {
    return (
      <div className="gal-tile gal-fail">
        <span className="gal-fail-alt">{it.alt || "Image failed to load"}</span>
        <a href={url} target="_blank" rel="noreferrer noopener">Open link</a>
      </div>
    );
  }
  return (
    <div className="gal-tile" data-state={state}>
      <button type="button" className="gal-open" onClick={() => onOpen(i)} aria-label={it.alt ? `Open image: ${it.alt}` : `Open image ${i + 1}`}>
        <img src={url} alt={it.alt} loading="lazy" decoding="async" referrerPolicy="no-referrer" onLoad={() => setState("ok")} onError={() => setState("fail")} />
      </button>
      <div className="gal-acts">
        <button type="button" className="gal-act" onClick={copy} aria-label={copied ? "Link copied" : "Copy link"} title="Copy link">
          {copied ? <Check size={14} aria-hidden /> : <Share2 size={14} aria-hidden />}
        </button>
        <a className="gal-act" href={url} download={fileName(it)} aria-label="Save image" title="Save image"><Download size={14} aria-hidden /></a>
      </div>
    </div>
  );
}

/** One image = figure, 2 = pair, 3 = row, 4+ = big left with two stacked right and a count pill. */
export function Gallery({ items }: { items: GalleryItem[] }) {
  const [open, setOpen] = useState<number | null>(null);
  const n = items.length;
  const shown = items.slice(0, n > 3 ? 3 : n);
  const Root = n === 1 ? "figure" : "div";
  return (
    <>
      <Root className="gal" data-n={n > 3 ? "many" : n}>
        {shown.map((it, i) => <Tile key={`${i}-${it.src}`} it={it} i={i} onOpen={setOpen} />)}
        {n > 3 && <span className="gal-count rec"><Images size={13} aria-hidden />{n}</span>}
      </Root>
      {open !== null && (
        <Lightbox items={items.map((it) => ({ src: mediaUrl(it.src), name: it.alt }))} index={open} onIndex={setOpen} onClose={() => setOpen(null)} />
      )}
    </>
  );
}
