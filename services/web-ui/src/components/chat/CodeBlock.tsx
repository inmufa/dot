"use client";
import { Check, Copy } from "lucide-react";
import { memo, useEffect, useState } from "react";

const MAX_HIGHLIGHT = 30_000;

export const CodeBlock = memo(function CodeBlock({ lang, code, settled }: { lang: string; code: string; settled: boolean }) {
  const [html, setHtml] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!settled || !code || code.length > MAX_HIGHLIGHT) return;
    let live = true;
    import("@/lib/highlight")
      .then((m) => m.highlightCode(code, lang))
      .then((h) => {
        if (live) setHtml(h);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [code, lang, settled]);

  const copy = () => {
    navigator.clipboard
      .writeText(code)
      .then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => undefined);
  };

  return (
    <figure className="code">
      <figcaption className="code-head">
        <span className="code-lang">{lang || "text"}</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={copy} aria-label="Copy code">
          {copied ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />}
          <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
        </button>
      </figcaption>
      {/* shiki escapes all source text; the string is generated, never user HTML */}
      {html ? (
        <div className="code-body" tabIndex={0} dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <div className="code-body" tabIndex={0}>
          <pre>
            <code>{code}</code>
          </pre>
        </div>
      )}
    </figure>
  );
});
