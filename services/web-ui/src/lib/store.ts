import { useSyncExternalStore } from "react";
import { api, apiHeaders, chatUrl } from "./api/client";
import { describeError, toErrorInfo } from "./api/errors";
import { parseEventJson } from "./stream/events";
import { itemsFromMessages } from "./stream/history";
import { chatReducer, initialChat, phaseOf, type ChatAction, type ChatState, type DotPhase } from "./stream/reducer";
import { readSse } from "./stream/sse";

type Listener = () => void;

/** Per-session chat state outside React so turns keep streaming while you look at another session. */
class ChatStore {
  private states = new Map<string, ChatState>();
  private loaded = new Set<string>();
  private listeners = new Set<Listener>();
  private turnEnd = new Set<(id: string) => void>();
  private version = 0;
  private scheduled = false;
  private phases: Record<string, DotPhase> = {};
  private phasesVersion = -1;

  subscribe = (fn: Listener): (() => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };
  onTurnEnd(fn: (id: string) => void): () => void {
    this.turnEnd.add(fn);
    return () => this.turnEnd.delete(fn);
  }
  get = (id: string | null): ChatState => (id ? (this.states.get(id) ?? initialChat) : initialChat);
  getVersion = (): number => this.version;

  allPhases = (): Record<string, DotPhase> => {
    if (this.phasesVersion !== this.version) {
      this.phases = {};
      for (const [id, s] of this.states) this.phases[id] = phaseOf(s);
      this.phasesVersion = this.version;
    }
    return this.phases;
  };

  private dispatch(id: string, a: ChatAction): void {
    this.states.set(id, chatReducer(this.states.get(id) ?? initialChat, a));
    this.version++;
    if (this.scheduled) return;
    this.scheduled = true;
    const run = () => {
      this.scheduled = false;
      this.listeners.forEach((l) => l());
    };
    if (typeof requestAnimationFrame === "function") requestAnimationFrame(run);
    else setTimeout(run, 16);
  }

  async load(id: string): Promise<void> {
    if (this.loaded.has(id) || this.get(id).running) return;
    this.loaded.add(id);
    try {
      const msgs = await api.messages(id);
      if (!this.get(id).running) this.dispatch(id, { type: "load", items: itemsFromMessages(msgs) });
    } catch (e) {
      this.loaded.delete(id);
      const info = toErrorInfo(e);
      this.dispatch(id, { type: "end", error: { code: info.code ?? undefined, text: info.title } });
    }
  }

  reset(id: string): void {
    this.loaded.delete(id);
    this.states.delete(id);
    this.version++;
    this.listeners.forEach((l) => l());
  }

  async send(id: string, text: string): Promise<void> {
    if (this.get(id).running) return;
    this.loaded.add(id);
    this.dispatch(id, { type: "send", text });
    try {
      const res = await fetch(chatUrl(id), {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json", Accept: "text/event-stream" }),
        body: JSON.stringify({ message: text }),
        cache: "no-store",
      });
      if (!res.ok || !res.body) {
        let body: unknown = null;
        try {
          body = (await res.json()) as unknown;
        } catch {
          /* non-JSON error body */
        }
        const info = describeError(res.status, body);
        this.dispatch(id, { type: "end", error: { code: info.code ?? undefined, text: info.title } });
        return;
      }
      let finished = false;
      for await (const data of readSse(res.body)) {
        const event = parseEventJson(data);
        if (!event) continue;
        if (event.type === "done") finished = true;
        this.dispatch(id, { type: "event", event, now: Date.now() });
      }
      if (!finished) this.dispatch(id, { type: "end", error: { text: "The stream ended before the turn finished." } });
    } catch (e) {
      const info = toErrorInfo(e);
      this.dispatch(id, { type: "end", error: { code: info.code ?? undefined, text: info.title } });
    }
    this.turnEnd.forEach((fn) => fn(id));
  }

  async stop(id: string): Promise<void> {
    try {
      await api.stop(id);
    } catch (e) {
      this.dispatch(id, { type: "end", error: { text: toErrorInfo(e).title } });
    }
  }

  /** Returns an error text when the answer was refused and the question stays open. */
  async answer(id: string, qid: string, selected: string[], other: string | null): Promise<string | null> {
    const summary = [...selected, ...(other ? [other] : [])].join(", ");
    try {
      await api.answer(qid, selected, other);
      this.dispatch(id, { type: "question_sent", id: qid, answer: summary });
      return null;
    } catch (e) {
      const info = toErrorInfo(e);
      if (info.code === 2003) this.dispatch(id, { type: "question_expired", id: qid });
      return `${info.title}${info.hint ? ` ${info.hint}` : ""}`;
    }
  }

  /** Used after a manual compaction: the next usage event would otherwise be a turn away. */
  noteUsage(id: string, tokens: number, limit: number): void {
    this.dispatch(id, { type: "event", now: Date.now(), event: { type: "usage", context_tokens: tokens, context_limit: limit } });
  }

  expireQuestion(id: string, qid: string): void {
    this.dispatch(id, { type: "question_expired", id: qid });
  }

  async resolve(id: string, approvalId: string, decision: "allow" | "always" | "reject"): Promise<void> {
    try {
      await api.resolve(approvalId, decision);
      this.dispatch(id, { type: "approval_sent" });
    } catch (e) {
      const info = toErrorInfo(e);
      this.dispatch(id, {
        type: "event",
        now: Date.now(),
        event: { type: "error", code: info.code ?? 1000, message: info.title },
      });
      if (info.code === 3003) this.dispatch(id, { type: "approval_sent" });
    }
  }
}

export const chatStore = new ChatStore();

export const useChat = (id: string | null): ChatState =>
  useSyncExternalStore(
    chatStore.subscribe,
    () => chatStore.get(id),
    () => chatStore.get(null),
  );

export const usePhases = (): Record<string, DotPhase> =>
  useSyncExternalStore(chatStore.subscribe, chatStore.allPhases, () => ({}));
