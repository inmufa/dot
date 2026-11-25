"use client";
import { ChevronRight, RefreshCw } from "lucide-react";
import type { KeyboardEvent } from "react";
import { Bullet, IconButton, ListRow } from "@/components/ui";
import { ErrorBox, Skeletons, StateBox } from "@/components/ui/StateBox";
import { useApp } from "@/lib/state/app";
import { buildTree, fmtSize, type TreeNode } from "./derive";
import { useFiles } from "./useFiles";

const countFiles = (n: TreeNode): number => (n.file ? 1 : n.children.reduce((a, c) => a + countFiles(c), 0));

function Node({ n, depth, onOpen, current }: { n: TreeNode; depth: number; onOpen: (p: string) => void; current: string | null }) {
  if (n.file) {
    return (
      <li>
        <ListRow className="cv-file" title={<span title={n.path} dir="auto">{n.name}</span>} lead={current === n.path ? <Bullet /> : undefined} leader time={fmtSize(n.file.size)} selected={current === n.path} onSelect={() => onOpen(n.path)} />
      </li>
    );
  }
  return (
    <li>
      <details open={depth < 2}>
        <summary className="cv-dir">
          <ChevronRight size={16} aria-hidden className="chev" />
          <span className="cv-dir-name" title={n.path}>{n.name}/</span>
          <span className="rec">{countFiles(n)}</span>
        </summary>
        <ul className="cv-kids">{n.children.map((c) => <Node key={c.path} n={c} depth={depth + 1} onOpen={onOpen} current={current} />)}</ul>
      </details>
    </li>
  );
}

/** Arrow keys move between visible rows (directory summaries and file rows). */
function onTreeKey(e: KeyboardEvent<HTMLElement>) {
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp" && e.key !== "Home" && e.key !== "End") return;
  const rows = [...e.currentTarget.querySelectorAll<HTMLElement>("summary, .lr-hit")].filter((r) => r.offsetParent !== null);
  const i = rows.indexOf(document.activeElement as HTMLElement);
  const next = e.key === "Home" ? 0 : e.key === "End" ? rows.length - 1 : i + (e.key === "ArrowDown" ? 1 : -1);
  if (i < 0 || !rows[next]) return;
  e.preventDefault();
  rows[next].focus();
}

export function FilesTab() {
  const { ui, id } = useApp();
  const files = useFiles(true);
  if (!files.available) return <StateBox grid quiet title="No file index yet.">This backend does not list workspace files.</StateBox>;
  if (!id) return <StateBox grid quiet title="No chat open.">Open a chat to browse its workspace.</StateBox>;
  if (files.error && !files.data) return <ErrorBox error={files.error} onRetry={files.reload} />;
  if (!files.data) return <Skeletons n={7} />;
  if (files.data.length === 0) return <StateBox grid quiet title="No files yet.">Whatever Dot writes in this chat is indexed here.</StateBox>;
  const total = files.data.reduce((a, f) => a + f.size, 0);
  return (
    <div className="cv-files">
      <div className="cv-bar">
        <p className="cv-count rec">{files.data.length} {files.data.length === 1 ? "file" : "files"} · {fmtSize(total)}</p>
        <IconButton label="Refresh files" size="sm" onClick={files.reload}><RefreshCw size={16} aria-hidden /></IconButton>
      </div>
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- arrow-key roving over the rows inside */}
      <ul className="cv-tree" onKeyDown={onTreeKey}>{buildTree(files.data).map((n) => <Node key={n.path} n={n} depth={0} onOpen={(p) => ui.openCanvas("preview", p)} current={ui.canvas.path} />)}</ul>
    </div>
  );
}
