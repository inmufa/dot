"use client";
import { chatStore } from "@/lib/state/store";
import { useApp } from "@/lib/state/app";
import { ApprovalCard } from "./ApprovalCard";
import { QuestionCard } from "./QuestionCard";

/** Approval and question cards that block the turn, shown above the composer. */
export function PendingDock() {
  const { chat, id, decide } = useApp();
  const q = chat.question ? chat.items.find((i) => i.kind === "question" && i.id === chat.question) : undefined;
  return (
    <>
      {chat.approval && <ApprovalCard key={chat.approval.id} approval={chat.approval} onDecide={decide} />}
      {q?.kind === "question" && (
        <QuestionCard
          key={q.id}
          q={q}
          onAnswer={(sel, other, fields) => (id ? chatStore.answer(id, q.id, sel, other, fields) : Promise.resolve(null))}
          onExpire={() => id && chatStore.expireQuestion(id, q.id)}
        />
      )}
    </>
  );
}
