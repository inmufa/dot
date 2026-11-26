import { useRef, type KeyboardEvent } from "react";
import type { Dictation } from "@/lib/voice/dictation";

/** Hold Space on an empty composer to dictate, release to stop. */
export function useHoldSpace(dictation: Dictation, canTalk: boolean) {
  const held = useRef(false);
  const release = () => {
    if (!held.current) return;
    held.current = false;
    dictation.stop();
  };
  /** True when the key was consumed. */
  const onKeyDown = (e: KeyboardEvent, text: string): boolean => {
    if (e.key !== " " || text) return false;
    if (!e.repeat && !e.ctrlKey && !e.metaKey && !e.altKey && dictation.phase === "idle" && canTalk) {
      e.preventDefault();
      held.current = true;
      dictation.start();
      return true;
    }
    if (e.repeat && held.current) {
      e.preventDefault();
      return true;
    }
    return false;
  };
  const onKeyUp = (e: KeyboardEvent) => {
    if (e.key === " ") release();
  };
  return { onKeyDown, onKeyUp, release };
}
