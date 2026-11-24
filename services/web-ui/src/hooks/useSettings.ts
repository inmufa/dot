"use client";
import { useCallback, useEffect, useState } from "react";
import { setApiLang } from "@/lib/api/client";

export type Theme = "system" | "light" | "dark";
export type Lang = "en" | "ru" | "uz";
export interface Settings {
  theme: Theme;
  lang: Lang;
}
const KEY = "dot.settings";
const DEFAULTS: Settings = { theme: "system", lang: "en" };

function read(): Settings {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) {
      const v = JSON.parse(raw) as Partial<Settings>;
      return {
        theme: v.theme === "light" || v.theme === "dark" ? v.theme : "system",
        lang: v.lang === "ru" || v.lang === "uz" ? v.lang : "en",
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
  setApiLang(s.lang);
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
