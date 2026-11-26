"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useConnection } from "@/hooks/useConnection";
import { useDotFavicon } from "@/hooks/useDotState";
import { useSessions } from "@/hooks/useSessions";
import { useSettings } from "@/hooks/useSettings";
import { useUiState } from "@/hooks/useUiState";
import { api, type Effort, type SkillInfo, type Telemetry } from "@/lib/api/client";
import { feature } from "@/lib/api/caps";
import { toErrorInfo, type DotErrorInfo } from "@/lib/api/errors";
import { mergeCommands, parseCommandLine } from "@/lib/commands/registry";
import { runCommand, type CommandHost } from "@/lib/commands/runner";
import { armFlight } from "@/lib/util/flight";
import { playSound, unlockSound } from "@/lib/sound/engine";
import { DEFAULT_EFFORT, effectiveEffort, isEffort } from "@/lib/effort/levels";
import { chatStore, useChat, usePhases } from "@/lib/state/store";
import type { PermissionMode } from "@/lib/stream/events";
import { phaseOf, type DotPhase, type UserAtt } from "@/lib/stream/reducer";
import { download, itemsToMarkdown } from "@/lib/util/export";
import { sessionTitle } from "@/lib/util/format";
import type { AppApi, BackendCfg, ComposerHandle, Decision } from "./types";

export type { AppApi, BackendCfg, ComposerHandle, Decision } from "./types";

const Ctx = createContext<AppApi | null>(null);
export function useApp(): AppApi {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside AppProvider");
  return v;
}

const effortKey = (id: string) => `dot.effort.${id}`;
function readEffort(id: string | null): Effort {
  try {
    const v = id ? window.localStorage.getItem(effortKey(id)) : null;
    return isEffort(v) ? v : DEFAULT_EFFORT;
  } catch {
    return DEFAULT_EFFORT;
  }
}

function mostUrgent(phases: Record<string, DotPhase>): DotPhase {
  const all = Object.values(phases);
  return all.includes("waiting") ? "waiting" : all.includes("thinking") ? "thinking" : "idle";
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useSettings();
  const conn = useConnection();
  const S = useSessions();
  const ui = useUiState();
  const phases = usePhases();
  const id = S.activeId;
  const chat = useChat(id);
  const phase = phaseOf(chat);
  const composer = useRef<ComposerHandle | null>(null);
  const [cfg, setCfg] = useState<BackendCfg | null>(null);
  const [skills, setSkills] = useState<SkillInfo[] | null>(null);
  const [skillsErr, setSkillsErr] = useState<DotErrorInfo | null>(null);
  const [remote, setRemote] = useState<Awaited<ReturnType<typeof api.commands>> | null>(null);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [effort, setEffortState] = useState<Effort>(DEFAULT_EFFORT);
  const [planOn, setPlan] = useState(false);
  const [researchOn, setResearch] = useState(false);
  const up = conn.link === "online" || conn.link === "degraded";

  useDotFavicon(mostUrgent(phases), S.active?.title);
  // Sound cues: approval needed, turn finished (ok or error), unlock on first gesture
  useEffect(() => {
    const unlock = () => unlockSound();
    window.addEventListener("pointerdown", unlock, { once: true });
    window.addEventListener("keydown", unlock, { once: true });
    return () => { window.removeEventListener("pointerdown", unlock); window.removeEventListener("keydown", unlock); };
  }, []);
  const approvalId = chat.approval?.id ?? null;
  useEffect(() => {
    if (approvalId) playSound("approval");
  }, [approvalId]);
  const turnMeta = useRef({ t0: 0, research: false });
  useEffect(() => chatStore.onTurnEnd((sid) => {
    const last = chatStore.get(sid).items.at(-1);
    if (last?.kind === "notice" && last.level === "error") {
      playSound("error");
      return;
    }
    const long = Date.now() - turnMeta.current.t0 >= 6000;
    if (turnMeta.current.research) playSound("research");
    else if (long || document.visibilityState !== "visible") playSound("done");
  }), []);
  const questionId = chat.question;
  useEffect(() => {
    if (questionId) playSound("approval");
  }, [questionId]);
  useEffect(() => {
    fetch("/api/dot/config", { cache: "no-store" }).then((r) => r.json() as Promise<BackendCfg>).then(setCfg, () => undefined);
  }, []);
  const loadSkills = useCallback(() => {
    setSkillsErr(null);
    api.skills().then(setSkills, (e: unknown) => setSkillsErr(toErrorInfo(e)));
  }, []);
  useEffect(() => {
    if (!up) return;
    loadSkills();
    feature("commands", api.commands).then(setRemote, () => undefined);
  }, [up, loadSkills]);
  useEffect(() => {
    if (!up) return;
    let live = true;
    const poll = () => {
      if (document.visibilityState !== "visible") return;
      feature("telemetry", api.telemetry).then((t) => live && setTelemetry(t), () => undefined);
    };
    poll();
    const t = window.setInterval(poll, 10_000);
    return () => {
      live = false;
      window.clearInterval(t);
    };
  }, [up]);
  useEffect(() => {
    if (id) void chatStore.load(id);
  }, [id, conn.link]);
  useEffect(() => setEffortState(readEffort(id)), [id]);
  useEffect(() => {
    if (!flash) return;
    const t = window.setTimeout(() => setFlash(null), 4000);
    return () => window.clearTimeout(t);
  }, [flash]);

  const commands = useMemo(() => mergeCommands(remote, skills ?? []), [remote, skills]);
  const notify = useCallback((t: string) => setFlash(t), []);

  const setEffort = useCallback((e: Effort) => {
    setEffortState(e);
    if (!id) return;
    try {
      window.localStorage.setItem(effortKey(id), e);
    } catch {
      /* storage unavailable */
    }
    void feature("effort", () => api.setEffort(id, e)).catch(() => undefined);
  }, [id]);
  const toggleDeep = useCallback(() => setEffort(effort === "max" ? DEFAULT_EFFORT : "max"), [effort, setEffort]);

  const changeMode = useCallback(async (m: PermissionMode) => {
    const err = await S.setMode(m);
    if (err) setFlash(`Could not change mode. ${err.title}`);
  }, [S]);

  const stop = useCallback(() => { if (id) void chatStore.stop(id); }, [id]);
  const lastAssistant = () => [...chat.items].reverse().find((i) => i.kind === "assistant" && i.text);
  const lastUser = () => [...chat.items].reverse().find((i) => i.kind === "user");

  const seqOfUser = useCallback(async (userItemId: string): Promise<number | null> => {
    if (!id) return null;
    const direct = chat.items.find((i) => i.id === userItemId);
    if (direct?.kind === "user" && direct.seq !== undefined) return direct.seq;
    const nth = chat.items.filter((i) => i.kind === "user").findIndex((i) => i.id === userItemId);
    const msgs = (await api.messages(id)).filter((m) => m.role === "user" && !m.rewound);
    return msgs[nth]?.seq ?? null;
  }, [id, chat.items]);

  const branchFromUser = useCallback(async (userItemId: string, edit = false) => {
    if (!id) return;
    try {
      const seq = await seqOfUser(userItemId);
      if (seq === null) { setFlash("Could not find that message."); return; }
      const text = chat.items.find((i) => i.id === userItemId);
      const s = await feature("branch", () => api.branch(id, seq - 1));
      if (!s) { setFlash("Branching is not available yet."); return; }
      await S.reload();
      S.select(s.id);
      if (edit && text?.kind === "user") window.setTimeout(() => composer.current?.setText(text.text), 150);
    } catch (e) {
      setFlash(toErrorInfo(e).title);
    }
  }, [id, seqOfUser, chat.items, S]);

  const rewindToUser = useCallback(async (userItemId: string) => {
    if (!id) return;
    try {
      const seq = await seqOfUser(userItemId);
      if (seq === null) { setFlash("Could not find that message."); return; }
      const out = await api.rewind(id, seq - 1);
      chatStore.reset(id);
      void chatStore.load(id);
      setFlash(`Rewound ${out.rewound_messages} messages.`);
    } catch (e) {
      setFlash(toErrorInfo(e).title);
    }
  }, [id, seqOfUser]);

  const regenerate = useCallback(() => {
    if (!id || chat.running) return;
    void (async () => {
      const r = await feature("regenerate", async () => {
        await chatStore.regenerate(id);
        return true;
      });
      if (r === null) {
        const u = lastUser();
        if (u?.kind === "user") void chatStore.send(id, u.text);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, chat.running, chat.items]);

  const compact = useCallback(async (focus?: string) => {
    if (!id) return;
    try {
      const out = await api.compact(id, focus || undefined);
      setFlash(out.compacted ? "Context compacted." : "Nothing to compact yet.");
      if (out.compacted && chat.usage) chatStore.noteUsage(id, out.tokens_after, chat.usage.limit);
    } catch (e) {
      setFlash(toErrorInfo(e).title);
    }
  }, [id, chat.usage]);

  const exportChat = useCallback(async (format: "md" | "json") => {
    if (!id) return;
    const title = sessionTitle(S.active?.title ?? null);
    const slug = title.replace(/[^\p{L}\p{N}]+/gu, "-").slice(0, 40) || "chat";
    try {
      const text = await feature("export", () => api.exportSession(id, format));
      if (text !== null) { download(`${slug}.${format}`, text, format === "json" ? "application/json" : "text/markdown"); return; }
    } catch (e) {
      setFlash(toErrorInfo(e).title);
      return;
    }
    download(`${slug}.md`, itemsToMarkdown(title, chat.items));
  }, [id, S.active, chat.items]);

  const send = useCallback((text: string, opts?: { attachments?: string[]; attInfo?: UserAtt[] }): boolean => {
    const line = text.trim();
    const cmd = line.startsWith("/") ? parseCommandLine(line) : null;
    if (cmd && host.current) {
      runCommand(cmd.name, cmd.arg, host.current, line);
      return true;
    }
    // only a send from home flies the greeting dot
    if (!id || chat.items.length === 0) armFlight();
    playSound("send");
    turnMeta.current = { t0: Date.now(), research: researchOn };
    if (!id) {
      // Home: open a session first, then send
      void S.create().then((nid) => { if (nid) void chatStore.send(nid, line, { effort: effectiveEffort(effort, line), ...(planOn ? { plan: true } : {}) }); setPlan(false); });
      return true;
    }
    void chatStore.send(id, line, {
      effort: effectiveEffort(effort, line),
      ...(planOn ? { plan: true } : {}),
      ...(researchOn ? { research: true } : {}),
      ...(opts?.attachments?.length ? { attachments: opts.attachments } : {}),
      ...(opts?.attInfo?.length ? { attInfo: opts.attInfo } : {}),
    });
    setPlan(false);
    setResearch(false);
    return true;
  }, [id, S, chat.items.length, effort, planOn, researchOn]);

  const host = useRef<CommandHost | null>(null);
  const hostObj = useMemo<CommandHost>(() => ({
    hasSession: !!id,
    stop,
    newChat: () => void S.create(),
    clearChat: () => void S.create(S.active?.mode, S.active?.project ?? null),
    retry: regenerate,
    branch: () => { const u = [...chat.items].reverse().find((i) => i.kind === "user"); if (u) void branchFromUser(u.id); },
    setMode: (m) => void changeMode(m),
    setEffort,
    openEffort: toggleDeep,
    openModel: () => ui.openOverlay("model"),
    openPanel: (p) => ui.setPanel(p),
    openContext: () => document.querySelector<HTMLElement>("[data-context-trigger]")?.click(),
    openPalette: (scope) => ui.openOverlay("palette", scope ?? "all"),
    openHelp: () => ui.openOverlay("help"),
    compact: (f) => void compact(f),
    rename: (t) => { if (id && t) void S.patch(id, { title: t }); else if (id) setFlash("Usage: /rename <title>"); },
    exportChat: (f) => void exportChat(f),
    togglePlan: () => setPlan((v) => !v),
    toggleResearch: () => setResearch((v) => !v),
    // clipboard is undefined on insecure origins
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
    copyLast: () => { const a = lastAssistant(); if (a?.kind === "assistant") void navigator.clipboard?.writeText(a.text).then(() => setFlash("Copied.")); },
    setTheme: (t) => setSettings({ theme: t }),
    sendText: (t) => { if (id) void chatStore.send(id, t); },
    flash: setFlash,
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [id, S, ui, stop, regenerate, setEffort, toggleDeep, changeMode, compact, exportChat, chat.items, branchFromUser, setSettings]);
  // latest-ref pattern for the runner
  // eslint-disable-next-line react-hooks/immutability
  useEffect(() => { host.current = hostObj; });

  const decide = useCallback((d: Decision) => { if (id && chat.approval) void chatStore.resolve(id, chat.approval.id, d); }, [id, chat.approval]);

  const value: AppApi = {
    settings, setSettings, conn, cfg, S, id, chat, phase, phases, skills, skillsErr, loadSkills, commands, telemetry, ui, composer,
    flash, notify, effort, setEffort, toggleDeep, planOn, researchOn, togglePlan: () => setPlan((v) => !v), toggleResearch: () => setResearch((v) => !v),
    changeMode, send, stop, decide, regenerate, branchFromUser, rewindToUser, compact, host: hostObj,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
