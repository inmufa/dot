"use client";
import { Check, Copy, GitBranch, History, Pencil, RotateCw } from "lucide-react";
import { useState } from "react";
import { IconButton, useToast } from "@/components/ui";
import { useApp } from "@/lib/state/app";
import { ReadAloud } from "./ReadAloud";
import { clock, fullDate } from "./time";

type Props = ({ kind: "user"; itemId: string; text: string } | { kind: "assistant"; text: string; canRegenerate: boolean }) & { at?: number };

/** Hover (or focus) actions per message. Hidden features (404) fall back inside the app handlers. */
export function MessageActions(p: Props) {
  const { regenerate, branchFromUser, rewindToUser, chat } = useApp();
  const toast = useToast();
  const [copied, setCopied] = useState(false);
  const copy = () => {
    // clipboard is undefined on insecure origins
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
    void navigator.clipboard?.writeText(p.text).then(() => {
      setCopied(true);
      toast({ title: "Copied", tone: "ok", ms: 1800 });
      window.setTimeout(() => setCopied(false), 1400);
    }, () => toast({ title: "Could not copy", tone: "bad" }));
  };
  return (
    <div className="msg-actions" role="group" aria-label={p.kind === "user" ? "Your message actions" : "Answer actions"}>
      {p.kind === "user" && p.at !== undefined && <time className="msg-time rec" dateTime={new Date(p.at).toISOString()} title={fullDate(p.at)}>{clock(p.at)}</time>}
      <IconButton size="sm" label={copied ? "Copied" : "Copy"} onClick={copy}>{copied ? <Check size={16} aria-hidden /> : <Copy size={16} aria-hidden />}</IconButton>
      {p.kind === "assistant" && <ReadAloud text={p.text} />}
      {p.kind === "assistant" && p.canRegenerate && (
        <IconButton size="sm" label="Regenerate" onClick={regenerate}><RotateCw size={16} aria-hidden /></IconButton>
      )}
      {p.kind === "user" && !chat.running && (
        <>
          <IconButton size="sm" label="Edit and branch" onClick={() => void branchFromUser(p.itemId, true)}><Pencil size={16} aria-hidden /></IconButton>
          <IconButton size="sm" label="Branch from here" onClick={() => void branchFromUser(p.itemId)}><GitBranch size={16} aria-hidden /></IconButton>
          <IconButton size="sm" label="Rewind to here" onClick={() => void rewindToUser(p.itemId)}><History size={16} aria-hidden /></IconButton>
        </>
      )}
      {p.kind === "assistant" && p.at !== undefined && <time className="msg-time rec" dateTime={new Date(p.at).toISOString()} title={fullDate(p.at)}>{clock(p.at)}</time>}
    </div>
  );
}
