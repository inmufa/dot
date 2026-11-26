"use client";
import { ArrowDown } from "lucide-react";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { groupTurns } from "@/lib/stream/turns";
import type { Item } from "@/lib/stream/reducer";
import { useApp } from "@/lib/state/app";
import { dayLabel, sameDay } from "./time";
import { TurnView } from "./Turn";
import { useStickToBottom } from "./useStickToBottom";

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

function TranscriptView({ items, running, sessionId, planning }: { items: Item[]; running: boolean; sessionId: string; planning: boolean }) {
  const { box, inner, away, fresh, onScroll, jump } = useStickToBottom(items, sessionId);
  const turns = useMemo(() => groupTurns(items, running), [items, running]);
  const announce = useAnnounce(items, running);
  const [today] = useState(() => Date.now());

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
          {waiting && <p className="waiting rec" role="status">{planning ? "generating research plan..." : "waiting for the model..."}</p>}
        </div>
      </div>
      <div className="sr-only" role="status" aria-live="polite">{announce}</div>
      {away && (
        <button
          type="button"
          className="btn jump press"
          aria-label={fresh > 0 ? `Jump to latest, ${fresh} new` : running ? "Follow output" : "Jump to latest"}
          title={running ? "Follow output" : "Jump to latest"}
          onClick={jump}
        >
          <ArrowDown size={18} aria-hidden />
          {fresh > 0 && <span className="jump-dot" aria-hidden />}
        </button>
      )}
    </div>
  );
}

export function Transcript() {
  const { chat, id, researchTurn } = useApp();
  return id ? <TranscriptView items={chat.items} running={chat.running} sessionId={id} planning={researchTurn && !chat.items.some((i) => i.kind === "plan")} /> : null;
}
