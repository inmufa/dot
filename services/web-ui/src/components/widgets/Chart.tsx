"use client";
import { useId, useMemo, useState } from "react";
import { useFirstView, useWidth } from "./hooks";
import { formatNum, type ChartP } from "./schema";

const H = 240, M = { t: 12, r: 12, b: 30, l: 46 };
const col = (i: number) => `var(--wc${(i % 6) + 1})`;

function niceMax(v: number): { max: number; step: number } {
  if (v <= 0) return { max: 1, step: 0.25 };
  const raw = v / 4, mag = 10 ** Math.floor(Math.log10(raw));
  const step = ([1, 2, 2.5, 5, 10].find((m) => m * mag >= raw) ?? 10) * mag;
  return { max: Math.ceil(v / step) * step, step };
}
const fmtTick = (n: number): string => (Math.abs(n) >= 1e6 ? `${+(n / 1e6).toFixed(1)}M` : Math.abs(n) >= 1e3 ? `${+(n / 1e3).toFixed(1)}k` : String(+n.toFixed(2)));

function Legend({ items }: { items: string[] }) {
  return (
    <ul className="wg-legend">
      {items.map((n, i) => <li key={`${n}-${i}`}><i style={{ background: col(i) }} aria-hidden />{n}</li>)}
    </ul>
  );
}

function Pie({ p, play }: { p: ChartP; play: boolean }) {
  const pts = p.series[0]?.points.filter((q) => q.y > 0) ?? [];
  const total = pts.reduce((a, q) => a + q.y, 0);
  const [hot, setHot] = useState<number | null>(null);
  const R = 84, r = 52, c = 100;
  const arcs = pts.map((q, i) => {
    const sweep = total ? (q.y / total) * Math.PI * 2 : 0;
    const a0 = -Math.PI / 2 + (total ? (pts.slice(0, i).reduce((s, x) => s + x.y, 0) / total) * Math.PI * 2 : 0);
    const a1 = a0 + Math.min(sweep, Math.PI * 2 - 1e-4);
    const big = sweep > Math.PI ? 1 : 0;
    const pt = (rad: number, a: number) => `${(c + rad * Math.cos(a)).toFixed(2)} ${(c + rad * Math.sin(a)).toFixed(2)}`;
    const d = `M${pt(R, a0)}A${R} ${R} 0 ${big} 1 ${pt(R, a1)}L${pt(r, a1)}A${r} ${r} 0 ${big} 0 ${pt(r, a0)}Z`;
    return { d, q, i };
  });
  const sel = hot === null ? null : pts[hot];
  return (
    <div className="wg-pie">
      <svg viewBox="0 0 200 200" role="img" aria-label={`Pie chart, ${pts.length} slices`} className="wg-pie-svg" data-play={play}>
        <g className="wg-pie-g">
          {arcs.map(({ d, i }) => (
            <path key={i} d={d} fill={col(i)} stroke="var(--bg)" strokeWidth={2} data-dim={hot !== null && hot !== i} onPointerEnter={() => setHot(i)} onPointerLeave={() => setHot(null)} />
          ))}
        </g>
        <text x={c} y={c - 2} textAnchor="middle" className="wg-pie-v">{sel ? formatNum(sel.y, p.unit) : formatNum(total, p.unit)}</text>
        <text x={c} y={c + 16} textAnchor="middle" className="wg-pie-l">{sel ? sel.x : "total"}</text>
      </svg>
      <ul className="wg-legend wg-legend-col">
        {pts.map((q, i) => (
          <li key={i} onPointerEnter={() => setHot(i)} onPointerLeave={() => setHot(null)}>
            <i style={{ background: col(i) }} aria-hidden />
            <span className="wg-leg-name">{q.x}</span>
            <span className="wg-leg-val">{formatNum(q.y, p.unit)} <span className="muted">{total ? Math.round((q.y / total) * 100) : 0}%</span></span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Cartesian({ p, play }: { p: ChartP; play: boolean }) {
  const [box, w] = useWidth<HTMLDivElement>();
  const [hot, setHot] = useState<number | null>(null);
  const uid = useId();
  const xs = p.series[0]?.points.map((q) => q.x) ?? [];
  const n = xs.length;
  const bar = p.type === "bar";
  const all = p.series.flatMap((s) => s.points.map((q) => q.y));
  const lo = Math.min(0, ...all), { max, step } = niceMax(Math.max(0, ...all));
  const span = max - lo || 1;
  const iw = Math.max(40, w - M.l - M.r), ih = H - M.t - M.b;
  const sx = (i: number) => M.l + (bar ? ((i + 0.5) / n) * iw : n < 2 ? iw / 2 : (i / (n - 1)) * iw);
  const sy = (v: number) => M.t + ih - ((v - lo) / span) * ih;
  const ticks = useMemo(() => { const t: number[] = []; for (let v = Math.ceil(lo / step) * step; v <= max + 1e-9; v += step) t.push(v); return t; }, [lo, max, step]);
  const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(iw / 64))));
  const slot = iw / Math.max(n, 1), bw = Math.min(40, (slot * 0.72) / p.series.length);

  const at = (clientX: number, el: Element) => {
    const x = clientX - el.getBoundingClientRect().left - M.l;
    const i = bar ? Math.floor(x / slot) : Math.round((x / iw) * (n - 1));
    setHot(Math.max(0, Math.min(n - 1, i)));
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); setHot((h) => Math.max(0, Math.min(n - 1, (h ?? (e.key === "ArrowRight" ? -1 : n)) + (e.key === "ArrowRight" ? 1 : -1)))); }
    else if (e.key === "Escape") setHot(null);
  };
  const path = (s: ChartP["series"][number]) => s.points.map((q, i) => `${i ? "L" : "M"}${sx(i).toFixed(1)} ${sy(q.y).toFixed(1)}`).join("");
  const tipRight = hot !== null && sx(hot) > w / 2;

  return (
    <div className="wg-plot" ref={box} data-play={play}>
      <svg width={w} height={H} role="group" tabIndex={0} aria-label={`${p.type} chart, ${p.series.length} series, ${n} points. Arrow keys move between points.`}
        onPointerMove={(e) => at(e.clientX, e.currentTarget)} onPointerLeave={() => setHot(null)} onKeyDown={onKey} onBlur={() => setHot(null)}>
        <defs><clipPath id={`${uid}c`}><rect className="wg-reveal" x={0} y={0} width={w} height={H} /></clipPath></defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.l} x2={w - M.r} y1={sy(t)} y2={sy(t)} className="wg-grid" data-zero={t === 0} />
            <text x={M.l - 8} y={sy(t) + 4} textAnchor="end" className="wg-tick">{fmtTick(t)}</text>
          </g>
        ))}
        {xs.map((x, i) => (i % every === 0 ? <text key={i} x={sx(i)} y={H - 10} textAnchor="middle" className="wg-tick">{x.length > 9 ? `${x.slice(0, 8)}...` : x}</text> : null))}
        {hot !== null && <line x1={sx(hot)} x2={sx(hot)} y1={M.t} y2={M.t + ih} className="wg-cursor" />}
        {bar ? (
          <g>
            {p.series.map((s, si) => s.points.map((q, i) => {
              const x = sx(i) - (p.series.length * bw) / 2 + si * bw, y0 = sy(0), y1 = sy(q.y);
              return <rect key={`${si}-${i}`} x={x} y={Math.min(y0, y1)} width={Math.max(1, bw - 2)} height={Math.max(1, Math.abs(y0 - y1))} rx={3} fill={col(si)} className="wg-bar" data-dim={hot !== null && hot !== i} style={{ transformOrigin: `${x}px ${y0}px`, animationDelay: `${Math.min(i, 24) * 22}ms` }} />;
            }))}
          </g>
        ) : (
          <g clipPath={`url(#${uid}c)`}>
            {p.type === "area" && p.series.map((s, si) => <path key={`a${si}`} d={`${path(s)}L${sx(n - 1)} ${sy(0)}L${sx(0)} ${sy(0)}Z`} fill={col(si)} opacity={0.16} />)}
            {p.series.map((s, si) => <path key={si} d={path(s)} fill="none" stroke={col(si)} strokeWidth={2.25} strokeLinejoin="round" strokeLinecap="round" />)}
            {hot !== null && p.series.map((s, si) => { const q = s.points[hot]; return q ? <circle key={si} cx={sx(hot)} cy={sy(q.y)} r={4} fill={col(si)} stroke="var(--bg)" strokeWidth={2} /> : null; })}
          </g>
        )}
      </svg>
      {hot !== null && (
        <div className="wg-tip" style={{ left: sx(hot), transform: `translateX(${tipRight ? "calc(-100% - 10px)" : "10px"})` }} aria-hidden>
          <strong>{xs[hot]}</strong>
          {p.series.map((s, si) => <span key={si}><i style={{ background: col(si) }} />{p.series.length > 1 ? `${s.name} ` : ""}<b>{formatNum(s.points[hot]?.y ?? 0, p.unit)}</b></span>)}
        </div>
      )}
    </div>
  );
}

export default function Chart({ p, title }: { p: ChartP; title: string | null }) {
  const [ref, seen] = useFirstView<HTMLDivElement>();
  const first = p.series[0];
  return (
    <div className="wg-chart" ref={ref}>
      {p.type === "pie" ? <Pie p={p} play={seen} /> : <Cartesian p={p} play={seen} />}
      {p.type !== "pie" && p.series.length > 1 && <Legend items={p.series.map((s) => s.name)} />}
      {(p.xLabel || p.yLabel) && p.type !== "pie" && <p className="muted wg-axes">{[p.yLabel, p.xLabel].filter(Boolean).join(" by ")}</p>}
      <table className="sr-only">
        <caption>{title ?? "Chart data"}</caption>
        <thead><tr><th>{p.xLabel ?? "x"}</th>{p.series.map((s, i) => <th key={i}>{s.name}</th>)}</tr></thead>
        <tbody>{first?.points.map((q, i) => <tr key={i}><td>{q.x}</td>{p.series.map((s, si) => <td key={si}>{s.points[i]?.y ?? ""}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}
