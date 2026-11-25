import { useEffect, useRef, useState } from "react";

/** Show `text`, but when it changes after the first render, type the new text out letter by letter. */
export function useTyped(text: string, msPerChar = 22): string {
  const prev = useRef(text);
  const [shown, setShown] = useState(text);
  useEffect(() => {
    if (prev.current === text) return;
    prev.current = text;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setShown(text); return; }
    const chars = Array.from(text);
    let i = 0;
    setShown("");
    const t = window.setInterval(() => {
      i += 1;
      setShown(chars.slice(0, i).join(""));
      if (i >= chars.length) window.clearInterval(t);
    }, msPerChar);
    return () => window.clearInterval(t);
  }, [text, msPerChar]);
  return shown;
}
