"use client";
import { useState } from "react";
import { BASE } from "@/lib/api/client";
import { Lightbox } from "./Lightbox";
import type { UserAtt } from "@/lib/stream/reducer";

const href = (id: string): string => `${BASE}/v1/attachments/${encodeURIComponent(id)}/content`;
const extOf = (n: string): string => (n.includes(".") ? (n.split(".").pop() ?? "").slice(0, 4).toUpperCase() : "FILE");
const SHOW = 3;

/** Attachments on a sent message: image thumbnails (open the viewer) and file tiles. */
export function UserAtts({ items }: { items: UserAtt[] }) {
  const [view, setView] = useState<number | null>(null);
  const images = items.filter((a) => a.kind === "image");
  const shown = items.length > SHOW + 1 ? items.slice(0, SHOW) : items;
  const more = items.length - shown.length;
  return (
    <>
      <ul className="uatts" aria-label="Attachments">
        {shown.map((a) =>
          a.kind === "image" ? (
            <li key={a.id}>
              <button type="button" className="uatt btn-bare" onClick={() => setView(images.indexOf(a))} title={a.name} aria-label={`Open ${a.name}`}>
                <span className="uatt-box"><img src={href(a.id)} alt={a.name} loading="lazy" /></span>
                <span className="uatt-meta rec">image</span>
              </button>
            </li>
          ) : (
            <li key={a.id}>
              <a href={href(a.id)} target="_blank" rel="noreferrer noopener" className="uatt" title={a.name} download={a.name}>
                <span className="uatt-box"><span className="uatt-ext">{extOf(a.name)}</span></span>
                <span className="uatt-meta rec">{a.name}</span>
              </a>
            </li>
          ),
        )}
        {more > 0 && (
          <li>
            <button type="button" className="uatt btn-bare" onClick={() => setView(images.length ? 0 : null)} aria-label={`${more} more attachments`}>
              <span className="uatt-box"><span className="uatt-more">+{more}</span></span>
              <span className="uatt-meta rec">more</span>
            </button>
          </li>
        )}
      </ul>
      <Lightbox items={images.map((a) => ({ src: href(a.id), name: a.name }))} index={view} onIndex={setView} onClose={() => setView(null)} />
    </>
  );
}
