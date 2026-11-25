"use client";
import dynamic from "next/dynamic";
import type { ReactNode } from "react";
import { AccordionWidget, ChoicesWidget, TabsWidget } from "./Rich";
import { CalloutWidget, CardsWidget, ChecklistWidget, StatsWidget, StepsWidget } from "./Blocks";
import { PARSERS, isWidgetKind, type ChartP, type WidgetKind } from "./schema";
import { TableWidget } from "./Table";
import "./widgets.css";

const Chart = dynamic(() => import("./Chart"), { ssr: false, loading: () => <div className="wg-skel" aria-hidden /> });

function Fallback({ kind, title, props, why }: { kind: string; title: string | null; props: unknown; why: string }) {
  let json: string;
  // stringify returns undefined for undefined props despite its typing
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
  try { json = (JSON.stringify(props, null, 2) as string | undefined) ?? String(props); } catch { json = String(props); }
  return (
    <div className="wg" data-kind="fallback">
      <p className="wg-title muted" dir="auto">{title ?? kind}: {why}</p>
      <pre className="wg-raw" tabIndex={0}><code>{json.length > 1500 ? `${json.slice(0, 1500)}\n...` : json}</code></pre>
    </div>
  );
}

function render(kind: WidgetKind, p: NonNullable<ReturnType<(typeof PARSERS)[WidgetKind]>>, title: string | null): ReactNode {
  switch (kind) {
    case "table": return <TableWidget p={p as never} title={title} />;
    case "chart": return <Chart p={p as ChartP} title={title} />;
    case "stats": return <StatsWidget p={p as never} />;
    case "steps": return <StepsWidget p={p as never} />;
    case "checklist": return <ChecklistWidget p={p as never} />;
    case "cards": return <CardsWidget p={p as never} />;
    case "callout": return <CalloutWidget p={p as never} />;
    case "tabs": return <TabsWidget p={p as never} />;
    case "accordion": return <AccordionWidget p={p as never} />;
    case "choices": return <ChoicesWidget p={p as never} />;
  }
}

/** Display widget from the backend `widget` event. Invalid or unknown payloads degrade to a code block; no HTML is ever injected. */
export function Widget({ kind, title, props }: { kind: string; title: string | null; props: unknown }) {
  if (!isWidgetKind(kind)) return <Fallback kind={kind} title={title} props={props} why="unknown widget" />;
  const p = PARSERS[kind](props);
  if (!p) return <Fallback kind={kind} title={title} props={props} why="invalid or oversized data" />;
  const bare = kind === "callout" || kind === "choices";
  return (
    <figure className="wg" data-kind={kind} data-bare={bare}>
      {title && !bare && <figcaption className="wg-title" dir="auto">{title}</figcaption>}
      {render(kind, p, title)}
    </figure>
  );
}

export default Widget;
