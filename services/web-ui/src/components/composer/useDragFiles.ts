"use client";
import { useEffect, useRef, useState } from "react";

/** True while files are dragged over the window; drop hands them to `onFiles`. */
export function useDragFiles(onFiles: (f: File[]) => void): boolean {
  const [over, setOver] = useState(false);
  const cb = useRef(onFiles);
  useEffect(() => {
    cb.current = onFiles;
  });
  useEffect(() => {
    let n = 0;
    const has = (e: DragEvent) => !!e.dataTransfer?.types.includes("Files");
    const enter = (e: DragEvent) => { if (has(e)) { n++; setOver(true); } };
    const leave = (e: DragEvent) => { if (has(e) && --n <= 0) { n = 0; setOver(false); } };
    const dragover = (e: DragEvent) => { if (has(e)) e.preventDefault(); };
    const drop = (e: DragEvent) => {
      if (!has(e)) return;
      e.preventDefault();
      n = 0;
      setOver(false);
      cb.current([...(e.dataTransfer?.files ?? [])]);
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", dragover);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", dragover);
      window.removeEventListener("drop", drop);
    };
  }, []);
  return over;
}
