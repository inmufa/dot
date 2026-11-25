"use client";
import { useCallback, useEffect, useState } from "react";
import { setApiLang } from "@/lib/api/client";
import { isPalette, type Palette } from "@/lib/palettes";
import { playSound, setSoundsEnabled } from "@/lib/sound/engine";

export type Theme = "system" | "light" | "dark";
export type Lang = "en" | "ru" | "uz";
export type Density = "roomy" | "compact";
export interface Settings {
  theme: Theme;
  palette: Palette;
  lang: Lang;
  density: Density;
  /** Expand the thinking pill while the model streams (default off: collapsed). */
  showThinking: boolean;
  /** Subtle sounds for approval needed and run finished. */
  sounds: boolean;
  /** Verbose view: every activity block and thinking expanded. */
  verbose: boolean;
}
const KEY = "dot.settings";
const DEFAULTS: Settings = { theme: "system", palette: "sage", lang: "en", density: "roomy", showThinking: false, sounds: false, verbose: false };

function read(): Settings {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) {
      const v = JSON.parse(raw) as Partial<Settings>;
      return {
        theme: v.theme === "light" || v.theme === "dark" ? v.theme : "system",
        palette: isPalette(v.palette) ? v.palette : "sage",
        lang: v.lang === "ru" || v.lang === "uz" ? v.lang : "en",
        density: v.density === "compact" ? "compact" : "roomy",
        showThinking: v.showThinking === true,
        sounds: v.sounds === true,
        verbose: v.verbose === true,
      };
    }
  } catch {
    /* storage unavailable */
  }
  return DEFAULTS;
}

function apply(s: Settings): void {
  const el = document.documentElement;
  if (s.theme === "system") el.removeAttribute("data-theme");
  else el.setAttribute("data-theme", s.theme);
  if (s.palette === "sage") el.removeAttribute("data-palette");
  else el.setAttribute("data-palette", s.palette);
  if (s.density === "compact") el.setAttribute("data-density", "compact");
  else el.removeAttribute("data-density");
  setApiLang(s.lang);
  setSoundsEnabled(s.sounds);
}

export function useSettings(): [Settings, (patch: Partial<Settings>) => void] {
  const [settings, setSettings] = useState<Settings>(DEFAULTS);
  useEffect(() => {
    const s = read();
    setSettings(s);
    apply(s);
  }, []);
  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      apply(next);
      if (patch.sounds === true && !prev.sounds) setTimeout(() => playSound("done"), 0); // preview
      try {
        window.localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);
  return [settings, update];
}
