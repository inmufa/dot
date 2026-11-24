"use client";
import { ArrowDown, AlertTriangle, Info } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Item } from "@/lib/stream/reducer";
import { CompactionDivider, PlanBlock, QuestionLine } from "./Aside";
import { Markdown } from "./Markdown";
import { Thinking } from "./Thinking";
import { SubagentLine } from "./SubagentLine";
import { ToolRow } from "./ToolRow";

const PIN_SLACK = 80;

function Entry({ item }: { item: Item }) {
  switch (item.kind) {
    case "user":
      return (
        <div className="turn-user">
          <span className="prompt" aria-hidden>&gt;</span>
          <span className="turn-text" dir="auto">{item.text}</span>
        </div>
      );
    case "assistant":
      return (
        <div className="turn-assistant">
          {item.thinking && <Thinking text={item.thinking} live={item.streaming && !item.text} />}
          {item.text && <Markdown text={item.text} settled={!item.streaming} />}
        </div>
      );
    case "tool":
      return <ToolRow tool={item} />;
    case "subagent":
      return <SubagentLine sub={item} />;
    case "compaction":
      return <CompactionDivider c={item} />;
    case "plan":
      return <PlanBlock text={item.text} />;
    case "question":
      return <QuestionLine q={item} />;
    case "notice": {
      const Icon = item.level === "error" ? AlertTriangle : Info;
      return (
        <div className="notice" data-level={item.level} role={item.level === "error" ? "alert" : "status"}>
          <Icon size={16} aria-hidden />
          <span>
            {item.text}
            {item.code !== undefined && <span className="muted"> (code {item.code})</span>}
          </span>
        </div>
      );
    }
  }
}

export function Transcript({ items, running, sessionId }: { items: Item[]; running: boolean; sessionId: string }) {
  const box = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const [away, setAway] = useState(false);

  const toBottom = useCallback(() => {
    const el = box.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  useLayoutEffect(() => {
    pinned.current = true;
    setAway(false);
    toBottom();
  }, [sessionId, toBottom]);

  useLayoutEffect(() => {
    if (pinned.current) toBottom();
  }, [items, toBottom]);

  useEffect(() => {
    const el = inner.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      if (pinned.current) toBottom();
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [toBottom]);

  const onScroll = () => {
    const el = box.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < PIN_SLACK;
    pinned.current = near;
    setAway(!near);
  };

  const last = items[items.length - 1];
  const waiting = running && (!last || last.kind === "user");

  return (
    <div className="stage">
      <div className="transcript" ref={box} onScroll={onScroll} role="log" aria-label="Conversation" aria-live="off" tabIndex={-1}>
        <div className="column" ref={inner}>
          {items.map((it) => (
            <Entry key={it.id} item={it} />
          ))}
          {waiting && <p className="waiting muted">Waiting for the model...</p>}
        </div>
      </div>
      {away && (
        <button
          type="button"
          className="btn jump"
          onClick={() => {
            pinned.current = true;
            setAway(false);
            toBottom();
          }}
        >
          <ArrowDown size={14} aria-hidden /> {running ? "Follow output" : "Jump to latest"}
        </button>
      )}
    </div>
  );
}
