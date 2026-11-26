"use client";
import dynamic from "next/dynamic";
import { AlertTriangle, Info } from "lucide-react";
import { CompactionLine, PlanBlock, QuestionLine } from "@/components/activity/Aside";
import { ActivityBlock } from "@/components/activity/ActivityBlock";
import { ToolStep } from "@/components/activity/Steps";
import { SubagentLine } from "@/components/activity/SubagentLine";
import { Thinking } from "@/components/activity/Thinking";
import { Entry } from "@/components/ui";
import type { SourceItem } from "@/lib/api/types";
import type { Item } from "@/lib/stream/reducer";
import type { Turn } from "@/lib/stream/turns";
import { useApp } from "@/lib/state/app";
import { useLiveOpen } from "@/lib/state/liveOpen";
import { SourcesCtx } from "./Cite";
import { Markdown } from "./Markdown";
import { MessageActions } from "./MessageActions";
import { Sources } from "./Sources";
import { stamper } from "./time";
import { UserAtts } from "./UserAtts";
import "./Turn.css";

const Widget = dynamic(() => import("@/components/widgets").then((m) => m.Widget), { ssr: false, loading: () => <div className="widget-skel" aria-hidden /> });

const atOf = (it: Item): number | undefined => ("at" in it ? it.at : undefined);

/** Plain text of the turn's answer (assistant items outside the activity block). */
const answerText = (t: Turn): string =>
  t.parts.flatMap((p) => (p.kind === "item" && p.item.kind === "assistant" ? [p.item.text] : [])).join("\n\n").trim();

/** One non-message item as a log entry. */
function ItemEntry({ item, time, i, actions, first, hideThinking }: { item: Item; time: React.ReactNode; i: number; actions: React.ReactNode; first: boolean; hideThinking: boolean }) {
  switch (item.kind) {
    case "assistant":
      if (hideThinking && !item.text) return null; // the live line says it is thinking
      return (
        <Entry time={time} i={i} state={item.streaming ? "thinking" : undefined} className="e-answer">
          {first && (item.text || item.thinking) && <div className="a-label rec">dot</div>}
          {item.thinking && <Thinking text={item.thinking} live={item.streaming && !item.text && item.thinkMs === undefined} startedAt={item.thinkStartedAt} ms={item.thinkMs} />}
          {item.text && (
            <div className="turn-assistant" data-streaming={item.streaming}>
              <Markdown text={item.text} settled={!item.streaming} />
            </div>
          )}
          {actions}
        </Entry>
      );
    case "tool":
      return <ToolStep tool={item} i={i} time={time} />;
    case "subagent":
      return <Entry time={time} i={i} className="e-step"><SubagentLine sub={item} /></Entry>;
    case "compaction":
      return <Entry time={time} i={i} className="e-quiet"><CompactionLine c={item} /></Entry>;
    case "plan":
      return <Entry time={time} i={i}><PlanBlock text={item.text} /></Entry>;
    case "question":
      return <Entry time={time} i={i} className="e-quiet"><QuestionLine q={item} /></Entry>;
    case "widget":
      return <Entry time={time} i={i} className="e-widget"><Widget kind={item.wkind} title={item.title} props={item.props} /></Entry>;
    case "sources":
      return <Entry time={time} i={i} className="e-quiet"><Sources items={item.items} /></Entry>;
    case "notice": {
      const Icon = item.level === "error" ? AlertTriangle : Info;
      return (
        <Entry time={time} i={i} className={`e-notice e-${item.level}`}>
          <div className="notice" data-level={item.level} role={item.level === "error" ? "alert" : "status"}>
            <Icon size={16} aria-hidden />
            <span>
              {item.text}
              {item.code !== undefined && <span className="rec"> code {item.code}</span>}
            </span>
          </div>
        </Entry>
      );
    }
    case "user":
      return null;
  }
}

export function TurnView({ turn, isLast }: { turn: Turn; isLast: boolean }) {
  const { chat } = useApp();
  const liveOpen = useLiveOpen();
  const text = answerText(turn);
  const u = turn.user;
  const stamp = stamper(u?.at);
  const lastAnswer = [...turn.parts].reverse().find((p) => p.kind === "item" && p.item.kind === "assistant" && p.item.text);
  const lastId = lastAnswer?.kind === "item" ? lastAnswer.item.id : null;
  const fa = turn.parts.find((p) => p.kind === "item" && p.item.kind === "assistant" && (p.item.text || p.item.thinking));
  const firstAnswer = fa?.kind === "item" ? fa.item.id : null;
  let n = 0;
  const cites = new Map<number, SourceItem>();
  for (const p of turn.parts) if (p.kind === "item" && p.item.kind === "sources") for (const s of p.item.items) cites.set(s.n, s);
  return (
    <SourcesCtx.Provider value={cites}>
    <article className="turn" data-live={turn.live} aria-label={u ? "Exchange" : "Dot"}>
      {u && (
        <Entry time={stamper()(u.at)} i={0} className="e-user">
          <div className="u-block" data-queued={u.queued || undefined}>
            {u.atts?.length ? <UserAtts items={u.atts} /> : null}
            <div className="u-text" dir="auto">{u.text}</div>
          </div>
          <MessageActions kind="user" itemId={u.id} text={u.text} at={u.at} canRetry={isLast && !chat.running && !text} />
          {u.queued && <span className="rec queued-note">queued, sends when the current turn ends</span>}
        </Entry>
      )}
      {turn.parts.map((p) => {
        const i = Math.min(n++, 6);
        if (p.kind === "activity") {
          const first = p.items.find((x) => atOf(x) !== undefined);
          return <ActivityBlock key={p.id} group={p} i={i} time={stamp(first ? atOf(first) : undefined)} />;
        }
        const actions = !turn.live && text && p.item.id === lastId ? <MessageActions kind="assistant" text={text} canRegenerate={isLast && !chat.running} at={atOf(p.item)} /> : null;
        return <ItemEntry key={p.item.id} item={p.item} time={stamp(atOf(p.item))} i={i} actions={actions} first={p.item.id === firstAnswer} hideThinking={turn.live && !liveOpen} />;
      })}
    </article>
    </SourcesCtx.Provider>
  );
}
