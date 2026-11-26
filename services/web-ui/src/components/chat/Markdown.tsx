import { Fragment, memo, useMemo, type ReactNode } from "react";
import { parseBlocks, type Block, type Inline } from "@/lib/util/markdown";
import { CitedText } from "./Cite";
import { CodeBlock } from "./CodeBlock";

function inline(nodes: Inline[]): ReactNode {
  return nodes.map((n, i) => {
    switch (n.t) {
      case "text":
        return n.v.split("\n").map((part, j) => (
          <Fragment key={`${i}-${j}`}>
            {j > 0 && <br />}
            <CitedText text={part} />
          </Fragment>
        ));
      case "code":
        return <code key={i} className="ic">{n.v}</code>;
      case "strong":
        return <strong key={i}>{inline(n.c)}</strong>;
      case "em":
        return <em key={i}>{inline(n.c)}</em>;
      case "del":
        return <del key={i}>{inline(n.c)}</del>;
      case "link":
        return (
          <a key={i} href={n.href} target="_blank" rel="noreferrer noopener">
            {inline(n.c)}
          </a>
        );
    }
  });
}

function block(b: Block, i: number, settled: boolean): ReactNode {
  switch (b.t) {
    case "p":
      return <p key={i} dir="auto">{inline(b.c)}</p>;
    case "h": {
      const Tag = (`h${Math.min(6, b.level + 2)}`) as "h3";
      return <Tag key={i} dir="auto">{inline(b.c)}</Tag>;
    }
    case "code":
      return <CodeBlock key={i} lang={b.lang} code={b.v} settled={settled || b.closed} />;
    case "quote":
      return <blockquote key={i}>{b.c.map((c, j) => block(c, j, settled))}</blockquote>;
    case "hr":
      return <hr key={i} />;
    case "list": {
      const Tag = b.ordered ? "ol" : "ul";
      return (
        <Tag key={i} start={b.ordered && b.start !== 1 ? b.start : undefined}>
          {b.items.map((it, j) => (
            <li key={j} dir="auto">{it.map((c, k) => block(c, k, settled))}</li>
          ))}
        </Tag>
      );
    }
    case "table":
      return (
        <div key={i} className="table-wrap" tabIndex={0}>
          <table>
            <thead>
              <tr>
                {b.head.map((c, j) => (
                  <th key={j} style={{ textAlign: b.align[j] ?? undefined }}>{inline(c)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {b.rows.map((r, j) => (
                <tr key={j}>
                  {r.map((c, k) => (
                    <td key={k} style={{ textAlign: b.align[k] ?? undefined }}>{inline(c)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
  }
}

export const Markdown = memo(function Markdown({ text, settled }: { text: string; settled: boolean }) {
  const blocks = useMemo(() => parseBlocks(text), [text]);
  return <div className="prose">{blocks.map((b, i) => block(b, i, settled))}</div>;
});
