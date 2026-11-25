"use client";
import { useResource, type Resource } from "@/hooks/useResource";
import { api } from "@/lib/api/client";
import { feature, useCap } from "@/lib/api/caps";
import type { FileEntry } from "@/lib/api/types";
import { useApp } from "@/lib/state/app";

/** Session workspace files; polls while the agent runs. `available` is false once the backend answered 404. */
export function useFiles(enabled: boolean): Resource<FileEntry[]> & { available: boolean } {
  const { id, chat } = useApp();
  const available = useCap("files");
  const r = useResource<FileEntry[]>(
    async () => (id ? ((await feature("files", () => api.files(id))) ?? []) : []),
    enabled && available,
    chat.running ? 4000 : 0,
    id ?? "",
  );
  return { ...r, available };
}
