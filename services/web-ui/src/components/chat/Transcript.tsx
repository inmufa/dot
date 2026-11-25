"use client";
import { ArrowDown } from "lucide-react";
import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { groupTurns } from "@/lib/stream/turns";
import type { Item } from "@/lib/stream/reducer";
import { useApp } from "@/lib/state/app";
import { dayLabel, sameDay } from "./time";
import { TurnView } from "./Turn";

const PIN_SLACK = 80;

/** Polite, throttled announcement: one line when a turn starts and the start of the answer when it ends. */
function useAnnounce(items: Item[], running: boolean): string {
  const [msg, setMsg] = useState("");
  const was = useRef(running);
  useEffect(() => {
    if (running && !was.current) setMsg("Dot is working");
    if (!running && was.current) {
      const last = [...items].reverse().find((i) => i.kind === "assistant" && i.text);
      setMsg(last?.kind === "assistant" ? `Dot replied: ${last.text.slice(0, 240)}` : "Dot finished");
    }
    was.current = running;
  }, [running, items]);
  return msg;
}

function TranscriptView({ items, running, sessionId }: { items: Item[]; running: boolean; sessionId: string }) {
  const box = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const seen = useRef(items.length);
  const [away, setAway] = useState(false);
  const [fresh, setFresh] = useState(0);
  const turns = useMemo(() => groupTurns(items, running), [items, running]);
  const announce = useAnnounce(items, running);
  const [today] = useState(() => Date.now());

  const toBottom = useCallback(() => {
    const el = box.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  useLayoutEffect(() => {
    pinned.current = true;
    seen.current = items.length;
    setAway(false);
    setFresh(0);
    toBottom();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset only when the session changes
  }, [sessionId, toBottom]);

  useLayoutEffect(() => {
    if (pinned.current) {
      seen.current = items.length;
      toBottom();
    } else if (items.length > seen.current) {
      setFresh((n) => n + (items.length - seen.current));
      seen.current = items.length;
    }
  }, [items, toBottom]);

  useEffect(() => {
    const el = inner.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      if (pinned.current) toBottom();
    });
    ro.observe(el);
    // The dock grows with approvals and attachments; keep the end in view.
    const dock = document.getElementById("dock");
    const dr = new ResizeObserver(() => requestAnimationFrame(() => { if (pinned.current) toBottom(); }));
    if (dock) dr.observe(dock);
    return () => { ro.disconnect(); dr.disconnect(); };
  }, [toBottom]);

  // Stops following the moment the user scrolls up.
  const onScroll = () => {
    const el = box.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < PIN_SLACK;
    pinned.current = near;
    setAway(!near);
    if (near) setFresh(0);
  };

  const last = items[items.length - 1];
  const waiting = running && (!last || last.kind === "user");

  return (
    <div className="stage">
      <div className="transcript" ref={box} onScroll={onScroll} role="log" aria-label="Conversation" aria-live="off" tabIndex={-1}>
        <div className="log turns" ref={inner}>
          {turns.map((t, i) => {
            const at = t.user?.at;
            const prev = turns[i - 1]?.user?.at;
            const label = at !== undefined && !sameDay(at, prev ?? today) ? dayLabel(at, today) : null;
            return (
              <Fragment key={t.id}>
                {label && <div className="day rec" role="separator"><span>{label}</span></div>}
                <TurnView turn={t} isLast={i === turns.length - 1} />
              </Fragment>
            );
          })}
          {waiting && <p className="waiting rec" role="status">waiting for the model...</p>}
        </div>
      </div>
      <div className="sr-only" role="status" aria-live="polite">{announce}</div>
      {away && (
        <button
          type="button"
          className="btn jump press"
          onClick={() => {
            pinned.current = true;
            setAway(false);
            setFresh(0);
            toBottom();
          }}
        >
          <ArrowDown size={14} aria-hidden />
          <span>{running ? "follow output" : "latest"}</span>
          {fresh > 0 && <span className="jump-n rec">{fresh} new</span>}
        </button>
      )}
    </div>
  );
}

export function Transcript() {
  const { chat, id } = useApp();
  return id ? <TranscriptView items={chat.items} running={chat.running} sessionId={id} /> : null;
}
