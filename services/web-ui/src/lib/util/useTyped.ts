import { useEffect, useRef, useState } from "react";

/**
 * Show `text`; type it out only when the same item (`key`) goes from no text to its
 * first text (the AI naming a chat). Loading, switching or renaming shows it at once.
 */
export function useTyped(text: string, key: string | null | undefined, msPerChar = 22): string {
  const prev = useRef({ text, key });
  const [shown, setShown] = useState(text);
  useEffect(() => {
    const p = prev.current;
    prev.current = { text, key };
    if (p.text === text && p.key === key) return;
    const named = p.key === key && !p.text && !!text;
    if (!named || window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setShown(text); return; }
    const chars = Array.from(text);
    let i = 0;
    setShown("");
    const t = window.setInterval(() => {
      i += 1;
      setShown(chars.slice(0, i).join(""));
      if (i >= chars.length) window.clearInterval(t);
    }, msPerChar);
    return () => window.clearInterval(t);
  }, [text, key, msPerChar]);
  return shown;
}
