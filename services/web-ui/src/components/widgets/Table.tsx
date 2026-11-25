"use client";
import { ArrowDown, ArrowUp, Download, Search } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { Button } from "@/components/ui";
import { download } from "@/lib/util/export";
import { formatNum, type Cell, type TableP } from "./schema";

const csvCell = (v: Cell): string => {
  let s = v === null ? "" : String(v);
  if (/^[=+\-@\t\r]/.test(s) && typeof v === "string") s = `'${s}`; // neutralise spreadsheet formulas
  return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
};

const cmp = (a: Cell, b: Cell, numeric: boolean): number => {
  if (a === null || b === null) return a === b ? 0 : a === null ? 1 : -1; // empty cells sort last
  if (numeric && typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
};

export function TableWidget({ p, title }: { p: TableP; title: string | null }) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const capId = useId();
  const needle = q.trim().toLowerCase();

  const rows = useMemo(() => {
    let r = needle ? p.rows.filter((x) => p.columns.some((c) => String(x[c.key] ?? "").toLowerCase().includes(needle))) : p.rows;
    if (sort) {
      const col = p.columns.find((c) => c.key === sort.key);
      const d = sort.dir;
      r = [...r].sort((a, b) => d * cmp(a[sort.key] ?? null, b[sort.key] ?? null, col?.num ?? false));
    }
    return r;
  }, [p, needle, sort]);

  const onSort = (key: string) => setSort((s) => (s?.key !== key ? { key, dir: 1 } : s.dir === 1 ? { key, dir: -1 } : null));
  const exportCsv = () => {
    const head = p.columns.map((c) => csvCell(c.label)).join(",");
    download("table.csv", [head, ...rows.map((r) => p.columns.map((c) => csvCell(r[c.key] ?? null)).join(","))].join("\n"), "text/csv");
  };

  return (
    <div className="wg-table">
      <div className="wg-tools">
        {p.rows.length > 5 && (
          <label className="wg-filter">
            <Search size={14} aria-hidden />
            <input className="input" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter rows" aria-label={`Filter ${title ?? "table"}`} autoComplete="off" />
          </label>
        )}
        <span className="muted wg-count" aria-live="polite">{rows.length === p.rows.length ? `${rows.length} rows` : `${rows.length} of ${p.rows.length}`}</span>
        <Button variant="ghost" size="sm" icon={<Download size={14} />} onClick={exportCsv}>CSV</Button>
      </div>
      <div className="wg-scroll" tabIndex={0} role="region" aria-labelledby={p.caption ? capId : undefined} aria-label={p.caption ? undefined : (title ?? "Table")}>
        <table>
          {p.caption && <caption id={capId}>{p.caption}</caption>}
          <thead>
            <tr>
              {p.columns.map((c) => {
                const on = sort?.key === c.key;
                return (
                  <th key={c.key} data-num={c.num} aria-sort={on ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
                    <button type="button" onClick={() => onSort(c.key)}>
                      {c.label}
                      <span className="wg-sort" data-on={on} aria-hidden>{on && sort.dir === -1 ? <ArrowDown size={12} /> : <ArrowUp size={12} />}</span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {p.columns.map((c) => {
                  const v = r[c.key] ?? null;
                  return <td key={c.key} data-num={c.num} dir={c.num ? undefined : "auto"}>{v === null ? <span className="muted" aria-label="empty">-</span> : typeof v === "number" ? formatNum(v) : v}</td>;
                })}
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={p.columns.length} className="muted wg-none">No rows match.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
