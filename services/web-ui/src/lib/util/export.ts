import type { Item } from "@/lib/stream/reducer";

/** Client-side markdown export, used when the backend export endpoint is not available. */
export function itemsToMarkdown(title: string, items: Item[]): string {
  const out: string[] = [`# ${title}`, ""];
  for (const i of items) {
    if (i.kind === "user") out.push(`**You**\n\n${i.text}\n`);
    else if (i.kind === "assistant" && i.text) out.push(`**Dot**\n\n${i.text}\n`);
    else if (i.kind === "tool") out.push(`> tool: ${i.name}\n`);
    else if (i.kind === "plan") out.push(`**Plan**\n\n${i.text}\n`);
  }
  return out.join("\n");
}

export function download(name: string, text: string, mime = "text/markdown"): void {
  const url = URL.createObjectURL(new Blob([text], { type: `${mime};charset=utf-8` }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}
