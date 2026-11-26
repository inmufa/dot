import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

const PIN_SLACK = 80;

/** Keeps a log scrolled to its end until the user scrolls away; `away` drives the jump button. */
export function useStickToBottom(items: readonly unknown[], sessionId: string) {
  const box = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const seen = useRef(items.length);
  const lastTop = useRef(0);
  const [away, setAway] = useState(false);
  const [fresh, setFresh] = useState(0);

  const toBottom = useCallback(() => {
    const el = box.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    lastTop.current = el.scrollTop;
  }, []);

  useLayoutEffect(() => {
    pinned.current = true;
    seen.current = items.length;
    setAway(false);
    setFresh(0);
    toBottom();
    // history, markdown and widgets settle after mount: re-pin over the next frames
    const r1 = requestAnimationFrame(() => { if (pinned.current) toBottom(); requestAnimationFrame(() => { if (pinned.current) toBottom(); }); });
    return () => cancelAnimationFrame(r1);
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
    // the dock grows with approvals and attachments
    const dock = document.getElementById("dock");
    const dr = new ResizeObserver(() => requestAnimationFrame(() => { if (pinned.current) toBottom(); }));
    if (dock) dr.observe(dock);
    // unpin when the gesture starts: re-pinning can win the race against the scroll event
    const box2 = box.current;
    const scrollable = () => !!box2 && box2.scrollHeight - box2.clientHeight > PIN_SLACK;
    const unpinOnIntent = (dy: number) => { if (dy < 0 && scrollable()) pinned.current = false; };
    const onWheel = (e: WheelEvent) => unpinOnIntent(e.deltaY);
    let touchY: number | null = null;
    const onTouchStart = (e: TouchEvent) => { touchY = e.touches[0]?.clientY ?? null; };
    const onTouchMove = (e: TouchEvent) => {
      const y = e.touches[0]?.clientY;
      if (y !== undefined && touchY !== null) unpinOnIntent(touchY - y);
      touchY = y ?? null;
    };
    box2?.addEventListener("wheel", onWheel, { passive: true });
    box2?.addEventListener("touchstart", onTouchStart, { passive: true });
    box2?.addEventListener("touchmove", onTouchMove, { passive: true });
    return () => {
      ro.disconnect();
      dr.disconnect();
      box2?.removeEventListener("wheel", onWheel);
      box2?.removeEventListener("touchstart", onTouchStart);
      box2?.removeEventListener("touchmove", onTouchMove);
    };
  }, [toBottom]);

  // unpin only when scrollTop went up: growth under a programmatic scroll must not unpin
  const onScroll = () => {
    const el = box.current;
    if (!el) return;
    const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
    const near = gap < PIN_SLACK;
    const up = el.scrollTop < lastTop.current - 1;
    lastTop.current = el.scrollTop;
    if (near) { pinned.current = true; setAway(false); setFresh(0); }
    else if (up) { pinned.current = false; setAway(true); }
  };

  const jump = () => {
    pinned.current = true;
    setAway(false);
    setFresh(0);
    toBottom();
  };

  return { box, inner, away, fresh, onScroll, jump };
}
