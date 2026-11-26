"use client";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import "./Home.css";
import { ModelChip } from "./ModelChip";
import { ErrorBox } from "@/components/ui/StateBox";
import { ListRow } from "@/components/ui/ListRow";
import { useApp } from "@/lib/state/app";
import { pickGreeting } from "@/lib/greetings";
import { lastActive } from "@/lib/util/days";
import { disarmFlight, flyDot, holdHomeDot } from "@/lib/util/flight";
import { sessionTitle } from "@/lib/util/format";
import { indexTime } from "@/lib/util/indexTime";

let lastGreeting: string | null = null;

/** Types a random greeting with the dot as caret, then glides the dot to the top bar. */
function TypedTitle() {
  const [title, setTitle] = useState("");
  const [n, setN] = useState(0);
  const dot = useRef<HTMLSpanElement>(null);
  const last = useRef<DOMRect | null>(null);
  const [gone, setGone] = useState(false);
  const goneRef = useRef(false);

  // Picked after mount so server and client markup match
  useEffect(() => {
    const t = pickGreeting(lastGreeting);
    lastGreeting = t;
    holdHomeDot(true);
    setTitle(t);
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) setN(Array.from(t).length);
  }, []);

  const chars = Array.from(title);
  useEffect(() => {
    if (!title || n >= chars.length) return;
    const t = window.setTimeout(() => setN((v) => v + 1), n === 0 ? 350 : 38 + Math.random() * 32 + (chars[n - 1] === " " ? 40 : 0));
    return () => window.clearTimeout(t);
  }, [n, title, chars.length]);

  useEffect(() => {
    if (!title || n < chars.length || goneRef.current) return;
    const t = window.setTimeout(() => {
      // hide the caret in the same frame the ghost appears, not after React commits data-gone
      if (dot.current) { const r = dot.current.getBoundingClientRect(); dot.current.style.visibility = "hidden"; flyDot(r, true); }
      goneRef.current = true;
      setGone(true);
    }, 700);
    return () => window.clearTimeout(t);
  }, [n, title, chars.length]);

  useLayoutEffect(() => {
    if (dot.current) last.current = dot.current.getBoundingClientRect();
  }, [n, title]);

  useLayoutEffect(() => {
    const keep = () => { if (dot.current) last.current = dot.current.getBoundingClientRect(); };
    window.addEventListener("resize", keep);
    return () => {
      window.removeEventListener("resize", keep);
      if (last.current && !goneRef.current) flyDot(last.current);
      else disarmFlight();
      holdHomeDot(false);
    };
  }, []);

  return (
    <h1 className="home-title typed" aria-label={title || undefined}>
      <span aria-hidden>{chars.slice(0, n).join("")}</span>
      <span ref={dot} className="dot dot-lg typed-dot" data-typing={n < chars.length} data-gone={gone} aria-hidden />
    </h1>
  );
}

/** Home: greeting, intent chips, recent chats. The shared .dock is centred by CSS on home. */
export function Home() {
  const { S } = useApp();
  const recent = useMemo(
    () => S.sessions.filter((s) => !s.archived && s.title && s.id !== S.activeId).sort((a, b) => Date.parse(lastActive(b)) - Date.parse(lastActive(a))).slice(0, 4),
    [S.sessions, S.activeId],
  );

  const failed = S.error && !S.active && !S.loading;

  return (
    <div className="home">
      <div className="home-top">
        <TypedTitle />
        <ModelChip />
      </div>
      <div className="home-below">
        {failed && S.error && <ErrorBox error={S.error} onRetry={() => void S.reload()} />}
        <nav className="home-recent" aria-label="Recent chats">
          <h2 className="rec">recent</h2>
          {recent.length === 0 ? <p className="home-empty rec">Nothing logged yet.</p> : (
            <ul>
              {recent.map((s) => (
                <li key={s.id}>
                  <ListRow title={<span dir="auto" title={sessionTitle(s.title)}>{sessionTitle(s.title)}</span>} leader time={indexTime(lastActive(s))} onSelect={() => S.select(s.id)} />
                </li>
              ))}
            </ul>
          )}
        </nav>
      </div>
    </div>
  );
}
