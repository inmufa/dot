import { useSyncExternalStore } from "react";
import { api, apiHeaders, chatUrl, regenerateUrl } from "@/lib/api/client";
import { describeError, toErrorInfo } from "@/lib/api/errors";
import { parseEventJson } from "@/lib/stream/events";
import { parseFields, summarize } from "@/components/widgets/fields";
import { itemsFromMessages } from "@/lib/stream/history";
import { chatReducer, initialChat, phaseOf, type ChatAction, type ChatState, type DotPhase, type UserAtt } from "@/lib/stream/reducer";
import { readSse } from "@/lib/stream/sse";

type Listener = () => void;

export interface SendOptions {
  /** Display-only info for the sent bubble (not sent to the backend). */
  attInfo?: UserAtt[];
  effort?: string;
  plan?: boolean;
  research?: boolean;
  attachments?: string[];
}

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

  /** Send now, or queue when a turn is running (retract with `retract`). */
  async send(id: string, text: string, opts: SendOptions = {}): Promise<void> {
    if (this.get(id).running) {
      this.dispatch(id, { type: "enqueue", id: `q${Date.now()}${Math.floor(Math.random() * 1e4)}`, text });
      // offer it to the running turn: it joins after the current tool finishes; otherwise it stays queued
      void api.inject(id, text).catch(() => undefined);
      return;
    }
    this.loaded.add(id);
    const { attInfo, ...wire } = opts;
    this.dispatch(id, { type: "send", text, now: Date.now(), ...(attInfo?.length ? { atts: attInfo } : {}) });
    await this.stream(id, chatUrl(id), { message: text, ...wire });
  }

  /** Re-run the last turn (backend `regenerate`); the last assistant output is dropped locally first. */
  async regenerate(id: string): Promise<void> {
    if (this.get(id).running) return;
    this.dispatch(id, { type: "regenerate", now: Date.now() });
    await this.stream(id, regenerateUrl(id), {});
  }

  /** Interrupt the running turn and send this queued message right away (it goes first). */
  async sendNow(id: string, qid: string): Promise<void> {
    const rest = this.get(id).queue.filter((x) => x.id !== qid);
    if (rest.length === this.get(id).queue.length) return;
    for (const x of rest) this.dispatch(id, { type: "dequeue", id: x.id });
    for (const x of rest) this.dispatch(id, { type: "enqueue", id: x.id, text: x.text });
    await this.stop(id); // the stream's end sends the first queued message
  }

  /** Interrupt the running turn and start draining the queue now; the rest follow one per turn. */
  async sendAllNow(id: string): Promise<void> {
    if (this.get(id).queue.length === 0) return;
    await this.stop(id);
  }

  retract(id: string, qid: string): string | null {
    const q = this.get(id).queue.find((x) => x.id === qid);
    if (q) {
      this.dispatch(id, { type: "dequeue", id: qid });
      void api.injectCancel(id, q.text).catch(() => undefined);
    }
    return q?.text ?? null;
  }

  private async stream(id: string, url: string, body: Record<string, unknown>): Promise<void> {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json", Accept: "text/event-stream" }),
        body: JSON.stringify(body),
        cache: "no-store",
      });
      if (!res.ok || !res.body) {
        let b: unknown = null;
        try {
          b = (await res.json()) as unknown;
        } catch {
          /* non-JSON error body */
        }
        const info = describeError(res.status, b);
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
    } finally {
      this.turnEnd.forEach((fn) => fn(id));
      const next = this.get(id).queue[0];
      if (next && !this.get(id).running) {
        this.dispatch(id, { type: "dequeue", id: next.id });
        void this.send(id, next.text);
      }
    }
  }

  async stop(id: string): Promise<void> {
    try {
      await api.stop(id);
    } catch (e) {
      this.dispatch(id, { type: "end", error: { text: toErrorInfo(e).title } });
    }
  }

  private formSummary(id: string, qid: string, a: Record<string, unknown>): string {
    const q = this.get(id).items.find((i) => i.kind === "question" && i.id === qid);
    const fs = q?.kind === "question" ? parseFields(q.fields) : null;
    return fs ? summarize(fs, a) : "Submitted";
  }

  /** Returns an error text when the answer was refused and the question stays open. */
  async answer(id: string, qid: string, selected: string[], other: string | null, fields?: Record<string, unknown>): Promise<string | null> {
    const summary = fields ? this.formSummary(id, qid, fields) : [...selected, ...(other ? [other] : [])].join(", ");
    try {
      if (fields) await api.answerForm(qid, fields);
      else await api.answer(qid, selected, other);
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

const NO_PHASES: Record<string, DotPhase> = {};
export const usePhases = (): Record<string, DotPhase> =>
  useSyncExternalStore(chatStore.subscribe, chatStore.allPhases, () => NO_PHASES);
