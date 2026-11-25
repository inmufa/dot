"use client";
import { ChevronsUpDown, ExternalLink, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CodeBlock } from "@/components/chat/CodeBlock";
import { Markdown } from "@/components/chat/Markdown";
import { Button, DropdownMenu, IconButton, MenuItem, Progress } from "@/components/ui";
import { ErrorBox, Skeletons, StateBox } from "@/components/ui/StateBox";
import { useResource } from "@/hooks/useResource";
import { api } from "@/lib/api/client";
import { useApp } from "@/lib/state/app";
import { chatStore } from "@/lib/state/store";
import { artifactMessage, parseArtifactEvent, type ArtifactIssue } from "./artifact";
import { extOf, fmtSize, parseCsv, previewKind } from "./derive";
import { useFiles } from "./useFiles";

const TEXT_CAP = 400_000;
const ROWS = 500;
const NUM = /^-?[\d\s.,]+%?$/;

function Csv({ text, path }: { text: string; path: string }) {
  const rows = parseCsv(text, extOf(path) === "tsv" ? "\t" : ",");
  const [head = [], ...body] = rows;
  if (head.length === 0) return <StateBox grid quiet title="Empty table.">This file has no rows.</StateBox>;
  // a column is numeric when every sampled cell looks like a number
  const num = head.map((_, j) => body.slice(0, 50).every((r) => (r[j] ?? "") === "" || NUM.test(r[j] ?? "")) && body.length > 0);
  return (
    <div className="cv-table table-wrap" tabIndex={0} role="region" aria-label={`Table ${path}`}>
      <table>
        <thead><tr>{head.map((c, i) => <th key={i} data-num={num[i]} title={c}>{c}</th>)}</tr></thead>
        <tbody>{body.map((r, i) => <tr key={i}>{head.map((_, j) => <td key={j} data-num={num[j]} title={r[j]} dir="auto">{r[j] ?? ""}</td>)}</tr>)}</tbody>
      </table>
      {rows.length > ROWS && <p className="cv-note rec">first {ROWS} rows shown</p>}
    </div>
  );
}

function TextBody({ sid, path, kind }: { sid: string; path: string; kind: "md" | "csv" | "code" | "other" }) {
  const r = useResource(() => api.fileText(sid, path), true, 0, `${sid}:${path}`);
  if (r.error) return <ErrorBox error={r.error} onRetry={r.reload} />;
  if (r.data === null) return <Skeletons n={6} />;
  if (r.data.trim() === "") return <StateBox grid quiet title="Empty file.">Nothing in it yet.</StateBox>;
  const cut = r.data.length > TEXT_CAP;
  const text = cut ? r.data.slice(0, TEXT_CAP) : r.data;
  const note = cut ? <p className="cv-note rec">first {Math.round(TEXT_CAP / 1000)}k characters shown</p> : null;
  if (kind === "md") return <><div className="cv-md" dir="auto"><Markdown text={text} settled /></div>{note}</>;
  if (kind === "csv") return <Csv text={text} path={path} />;
  return <><CodeBlock lang={extOf(path)} code={text} settled />{note}</>;
}

function Image({ url, path }: { url: string; path: string }) {
  const [dim, setDim] = useState<string | null>(null);
  const [bad, setBad] = useState(false);
  if (bad) return <StateBox grid quiet title="Cannot show this image.">The file is not a readable image.</StateBox>;
  return (
    <>
      <img src={url} alt={path} className="cv-img" onLoad={(e) => setDim(`${e.currentTarget.naturalWidth} x ${e.currentTarget.naturalHeight}`)} onError={() => setBad(true)} />
      {dim && <p className="rec">{dim}</p>}
    </>
  );
}

function Html({ sid, url, path }: { sid: string; url: string; path: string }) {
  const [loaded, setLoaded] = useState(false);
  const [issues, setIssues] = useState<ArtifactIssue[]>([]);
  const [note, setNote] = useState("");
  const frame = useRef<HTMLIFrameElement>(null);
  useEffect(() => { setLoaded(false); setIssues([]); }, [url]);
  // the page reports errors and console output through postMessage (opaque origin: match by window)
  useEffect(() => {
    const on = (e: MessageEvent) => {
      if (e.source !== frame.current?.contentWindow) return;
      const issue = parseArtifactEvent(e.data);
      if (issue) setIssues((cur) => (cur.length >= 20 || cur.some((c) => c.message === issue.message) ? cur : [...cur, issue]));
    };
    window.addEventListener("message", on);
    return () => window.removeEventListener("message", on);
  }, []);
  const send = () => {
    void chatStore.send(sid, artifactMessage(path, issues, note));
    setNote("");
  };
  const errors = issues.filter((i) => i.kind === "error").length;
  return (
    <>
      {!loaded && <div className="cv-frame-load"><Progress label="Loading page" /></div>}
      {/* never add allow-same-origin: it would let the page reach this app */}
      <iframe ref={frame} title={`Preview of ${path}`} src={url} sandbox="allow-scripts" referrerPolicy="no-referrer" loading="lazy" onLoad={() => setLoaded(true)} />
      <form className="cv-fix" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <span className="cv-fix-status rec" role="status" data-bad={errors > 0 || undefined}>
          {issues.length === 0 ? "Running, no errors" : `${errors} error${errors === 1 ? "" : "s"}, ${issues.length - errors} warning${issues.length - errors === 1 ? "" : "s"}`}
        </span>
        <input className="cv-fix-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="What should change? (optional)" aria-label="Note for Dot" dir="auto" />
        <Button type="submit" size="sm" disabled={issues.length === 0 && note.trim() === ""}>Fix with Dot</Button>
      </form>
      {issues.length > 0 && (
        <ul className="cv-issues" aria-label="Page errors">
          {issues.map((i, n) => <li key={n} data-kind={i.kind}><span className="rec">{i.kind}</span> <span dir="auto">{i.message}</span></li>)}
        </ul>
      )}
    </>
  );
}

export function PreviewTab() {
  const { id, ui } = useApp();
  const files = useFiles(true);
  const path = ui.canvas.path;
  // nothing picked yet: show the most recent previewable file
  const first = files.data?.find((f) => f.kind !== "other" && f.kind !== "code")?.path;
  useEffect(() => {
    if (!path && first) ui.openCanvas("preview", first);
  }, [path, first, ui]);
  if (!files.available) return <StateBox grid quiet title="No preview yet.">This backend does not serve workspace files.</StateBox>;
  if (!id) return <StateBox grid quiet title="Nothing to show.">Open a chat. Pages, images, tables and notes Dot writes open here.</StateBox>;
  if (files.error && !files.data) return <ErrorBox error={files.error} onRetry={files.reload} />;
  const list = files.data ?? [];
  if (!path) {
    if (files.loading && !files.data) return <Skeletons n={4} />;
    return list.length
      ? <StateBox grid quiet title="Pick a file.">Choose one in the Files tab to read it here.</StateBox>
      : <StateBox grid quiet title="Nothing written yet.">When Dot writes a page, image, table or note, it opens here.</StateBox>;
  }
  const entry = list.find((f) => f.path === path);
  const kind = entry?.kind ?? previewKind(path);
  const url = api.fileUrl(id, path, kind === "html");
  const slash = path.lastIndexOf("/");
  const name = path.slice(slash + 1);
  const dir = slash > 0 ? path.slice(0, slash + 1) : "";
  return (
    <div className="cv-preview">
      <div className="cv-bar">
        <DropdownMenu align="start" label="Switch file" trigger={(p) => (
          <button type="button" className="cv-file-id" title={path} aria-label={`${path}. Switch file`} {...p}>
            <span className="cv-file-name">{name}</span>
            {dir && <span className="cv-file-dir rec"><bdi>{dir}</bdi></span>}
            <ChevronsUpDown size={16} aria-hidden className="cv-file-chev" />
          </button>
        )}>
          {!entry && <MenuItem selected>{path}</MenuItem>}
          {list.map((f) => <MenuItem key={f.path} selected={f.path === path} hint={fmtSize(f.size)} onSelect={() => ui.openCanvas("preview", f.path)}>{f.path}</MenuItem>)}
        </DropdownMenu>
        {entry && <span className="rec">{fmtSize(entry.size)}</span>}
        <IconButton label="Refresh files" size="sm" onClick={files.reload}><RefreshCw size={16} aria-hidden /></IconButton>
        <IconButton label="Open in a new tab" size="sm" onClick={() => window.open(url, "_blank", "noopener,noreferrer")}><ExternalLink size={16} aria-hidden /></IconButton>
      </div>
      <div className="cv-frame" data-kind={kind}>
        {kind === "html" ? <Html sid={id} url={url} path={path} /> : kind === "image" ? <Image url={url} path={path} /> : <TextBody sid={id} path={path} kind={kind} />}
      </div>
    </div>
  );
}
