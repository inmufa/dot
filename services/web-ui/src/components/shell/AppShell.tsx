"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useConnection } from "@/hooks/useConnection";
import { useDotFavicon } from "@/hooks/useDotState";
import { useSessions } from "@/hooks/useSessions";
import { useSettings } from "@/hooks/useSettings";
import { api, type SkillInfo } from "@/lib/api/client";
import { toErrorInfo, type DotErrorInfo } from "@/lib/api/errors";
import { parseBuiltin } from "@/lib/slash";
import { chatStore, useChat, usePhases } from "@/lib/store";
import { MODES, type PermissionMode } from "@/lib/stream/events";
import { phaseOf, type DotPhase } from "@/lib/stream/reducer";
import { QuestionCard } from "../chat/QuestionCard";
import { ApprovalCard, type Decision } from "../approval/ApprovalCard";
import { Composer, type ComposerHandle } from "../chat/Composer";
import { EmptyState } from "../chat/EmptyState";
import { Transcript } from "../chat/Transcript";
import { PanelHost } from "./PanelHost";
import { ErrorBox } from "../ui/StateBox";
import { Banner } from "./Banner";
import { Rail, type PanelId } from "./Rail";
import { TopBar } from "./TopBar";

interface Cfg {
  backend: string | null;
  configured: boolean;
}

function mostUrgent(phases: Record<string, DotPhase>): DotPhase {
  const all = Object.values(phases);
  return all.includes("waiting") ? "waiting" : all.includes("thinking") ? "thinking" : "idle";
}

export function AppShell() {
  const [settings, setSettings] = useSettings();
  const conn = useConnection();
  const S = useSessions();
  const phases = usePhases();
  const chat = useChat(S.activeId);
  const [panel, setPanel] = useState<PanelId | null>(null);
  const [railOpen, setRailOpen] = useState(false);
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [skills, setSkills] = useState<SkillInfo[] | null>(null);
  const [skillsErr, setSkillsErr] = useState<DotErrorInfo | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const composer = useRef<ComposerHandle>(null);
  const id = S.activeId;
  const phase = phaseOf(chat);
  const question = chat.question ? chat.items.find((i) => i.kind === "question" && i.id === chat.question) : undefined;

  useDotFavicon(mostUrgent(phases));

  useEffect(() => {
    fetch("/api/dot/config", { cache: "no-store" })
      .then((r) => r.json() as Promise<Cfg>)
      .then(setCfg, () => undefined);
  }, []);

  const loadSkills = useCallback(() => {
    setSkillsErr(null);
    api.skills().then(setSkills, (e: unknown) => setSkillsErr(toErrorInfo(e)));
  }, []);
  const up = conn.link === "online" || conn.link === "degraded";
  useEffect(() => {
    if (up) loadSkills();
  }, [up, loadSkills]);

  useEffect(() => {
    if (id) void chatStore.load(id);
  }, [id, conn.link]);

  useEffect(() => {
    if (!flash) return;
    const t = window.setTimeout(() => setFlash(null), 4000);
    return () => window.clearTimeout(t);
  }, [flash]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
      if ((e.target as HTMLElement).closest("input, textarea, select, dialog, [contenteditable]")) return;
      e.preventDefault();
      composer.current?.setText("/");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!railOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setRailOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [railOpen]);

  const changeMode = useCallback(
    async (m: PermissionMode) => {
      const err = await S.setMode(m);
      if (err) setFlash(`Could not change mode. ${err.title}`);
    },
    [S],
  );

  const onSend = useCallback(
    (text: string) => {
      if (!id) return;
      const cmd = parseBuiltin(text);
      if (!cmd) return void chatStore.send(id, text);
      if (cmd.type === "stop") return void chatStore.stop(id);
      if (cmd.type === "rewind") { setPanel("rewind"); return; }
      if (cmd.type === "new") return void S.create(S.active?.mode);
      const m = MODES.find((x) => x.toLowerCase() === cmd.arg.toLowerCase());
      if (m) void changeMode(m);
      else setFlash(`Usage: /mode ${MODES.join("|")}`);
    },
    [id, S, changeMode],
  );

  const onDecide = useCallback(
    (d: Decision) => {
      if (id && chat.approval) void chatStore.resolve(id, chat.approval.id, d);
    },
    [id, chat.approval],
  );

  const onAnswer = useCallback(
    (selected: string[], other: string | null) => (id && chat.question ? chatStore.answer(id, chat.question, selected, other) : Promise.resolve(null)),
    [id, chat.question],
  );
  const onExpire = useCallback(() => {
    if (id && chat.question) chatStore.expireQuestion(id, chat.question);
  }, [id, chat.question]);

  const pickSession = (sid: string) => {
    S.select(sid);
    setRailOpen(false);
  };
  const close = () => setPanel(null);

  return (
    <div className="app">
      <a className="skip" href="#composer">Skip to message box</a>
      <Rail
        open={railOpen}
        sessions={S.sessions}
        loading={S.loading}
        error={S.error}
        activeId={id}
        phases={phases}
        onSelect={pickSession}
        onNew={() => { void S.create(); setRailOpen(false); }}
        onRetry={() => { void S.reload(); conn.recheck(); }}
        onPanel={(p) => { setPanel(p); setRailOpen(false); }}
        onClose={() => setRailOpen(false)}
      />
      {railOpen && <button type="button" className="scrim" aria-label="Close sessions" onClick={() => setRailOpen(false)} />}
      <div className="main">
        <Banner link={conn.link} error={conn.error} backend={cfg?.backend ?? null} onRetry={() => { conn.recheck(); void S.reload(); }} />
        <TopBar
          session={S.active}
          phase={phase}
          usage={chat.usage}
          running={chat.running}
          onMenu={() => setRailOpen(true)}
          onMode={(m) => void changeMode(m)}
          onRewind={() => setPanel("rewind")}
        />
        {id && chat.items.length > 0 ? (
          <Transcript items={chat.items} running={chat.running} sessionId={id} />
        ) : (
          <div className="stage">
            <div className="transcript">
              <div className="column">
                {S.error && !S.active && !S.loading ? (
                  <ErrorBox error={S.error} onRetry={() => void S.reload()} />
                ) : (
                  <EmptyState hasSession={!!id} mode={S.active?.mode ?? null} onNew={() => void S.create()} />
                )}
              </div>
            </div>
          </div>
        )}
        <div className="dock" id="dock">
          <div className="column">
            {flash && <p className="flash" role="status">{flash}</p>}
            {chat.approval && <ApprovalCard key={chat.approval.id} approval={chat.approval} onDecide={onDecide} />}
            {question?.kind === "question" && <QuestionCard key={question.id} q={question} onAnswer={onAnswer} onExpire={onExpire} />}
            <Composer
              ref={composer}
              sessionId={id}
              phase={phase}
              running={chat.running}
              blocked={chat.approval !== null || chat.question !== null}
              blockedText={chat.question ? "Answer above first" : undefined}
              skills={skills ?? []}
              onSend={onSend}
              onStop={() => id && void chatStore.stop(id)}
            />
          </div>
        </div>
      </div>
      <PanelHost
        panel={panel}
        onClose={close}
        sessionId={id}
        running={chat.running}
        skills={{ list: skills, error: skillsErr, retry: loadSkills, pick: (n) => composer.current?.setText(`/${n} `) }}
        settings={{ value: settings, set: setSettings, backend: cfg?.backend ?? null, configured: cfg?.configured ?? null }}
      />
    </div>
  );
}
