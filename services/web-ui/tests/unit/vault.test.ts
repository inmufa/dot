import { afterEach, describe, expect, it, vi } from "vitest";
import { DotApiError } from "@/lib/api/errors";
import { createBody, draftOf, draftProblem, EMPTY_DRAFT, fieldForCode, patchBody, splitOrigins, vaultApi, type Credential } from "@/lib/api/vault";

const CRED: Credential = {
  id: "VA1B2C3D41", label: "GitHub", origins: ["https://github.com"], username: "me", notes: "", has_password: true, has_totp: true,
  has_session: true, session_saved_at: null, session_expires_at: null, last_used: null, created_at: "", updated_at: "",
};

describe("vault drafts", () => {
  it("splits origins on lines, commas and spaces, dropping repeats", () => {
    expect(splitOrigins("https://a.com\n https://b.com, https://a.com  \n")).toEqual(["https://a.com", "https://b.com"]);
  });
  it("create sends only filled fields", () => {
    expect(createBody({ ...EMPTY_DRAFT, label: " Site ", origins: "https://s.io" })).toEqual({ label: "Site", origins: ["https://s.io"] });
    const full = createBody({ ...EMPTY_DRAFT, label: "S", origins: "https://s.io", username: "u", password: " p w ", totp: "JBSW Y3DP", notes: "n" });
    expect(full).toEqual({ label: "S", origins: ["https://s.io"], username: "u", password: " p w ", totp_secret: "JBSWY3DP", notes: "n" });
  });
  it("an untouched edit form sends nothing, secrets are never prefilled", () => {
    const d = draftOf(CRED);
    expect(d.password).toBe("");
    expect(d.totp).toBe("");
    expect(patchBody(CRED, d)).toEqual({});
  });
  it("edit sends only changed fields and typed secrets", () => {
    const d = { ...draftOf(CRED), username: "you", password: "new" };
    expect(patchBody(CRED, d)).toEqual({ username: "you", password: "new" });
    expect(patchBody(CRED, { ...draftOf(CRED), origins: "https://github.com\nhttps://api.github.com" })).toEqual({ origins: ["https://github.com", "https://api.github.com"] });
  });
  it("removing TOTP sends an empty secret, only when one is stored", () => {
    expect(patchBody(CRED, { ...draftOf(CRED), dropTotp: true })).toEqual({ totp_secret: "" });
    expect(patchBody({ ...CRED, has_totp: false }, { ...draftOf(CRED), dropTotp: true })).toEqual({});
  });
  it("validates locally", () => {
    expect(draftProblem(EMPTY_DRAFT)?.field).toBe("label");
    expect(draftProblem({ ...EMPTY_DRAFT, label: "x" })?.field).toBe("origins");
    expect(draftProblem({ ...EMPTY_DRAFT, label: "x", origins: Array.from({ length: 11 }, (_, i) => `https://h${i}.io`).join("\n") })?.field).toBe("origins");
    expect(draftProblem({ ...EMPTY_DRAFT, label: "x", origins: "https://a.io", totp: "not base32!" })?.field).toBe("totp");
    expect(draftProblem({ ...EMPTY_DRAFT, label: "x", origins: "https://a.io", totp: "jbsw y3dp" })).toBeNull();
  });
  it("maps 4142 and 4149 to their fields", () => {
    expect(fieldForCode(4142)).toBe("label");
    expect(fieldForCode(4149)).toBe("origins");
    expect(fieldForCode(4146)).toBeNull();
    expect(fieldForCode(null)).toBeNull();
  });
});

describe("vaultApi", () => {
  afterEach(() => vi.unstubAllGlobals());
  const stub = (status: number, body: unknown) => {
    const f = vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })));
    vi.stubGlobal("fetch", f);
    return f;
  };
  const call = (f: ReturnType<typeof stub>, i = 0) => f.mock.calls[i] as unknown as [string, RequestInit];

  it("deletes with the matching confirm id", async () => {
    const f = stub(200, { ok: true });
    await vaultApi.remove("VA1/x");
    expect(call(f)[0]).toBe("/api/dot/v1/vault/VA1%2Fx?confirm=VA1%2Fx");
    expect(call(f)[1].method).toBe("DELETE");
  });
  it("clears all sessions with confirm=all", async () => {
    const f = stub(200, { cleared: 2 });
    expect(await vaultApi.clearAllSessions()).toEqual({ cleared: 2 });
    expect(call(f)[0]).toBe("/api/dot/v1/vault/sessions?confirm=all");
  });
  it("save-session sends either a credential or a label", async () => {
    const f = stub(200, CRED);
    await vaultApi.saveSession("S1", { credential: "VA1" });
    await vaultApi.saveSession("S1", { label: "New" });
    expect(JSON.parse(call(f, 0)[1].body as string)).toEqual({ session_id: "S1", credential: "VA1" });
    expect(JSON.parse(call(f, 1)[1].body as string)).toEqual({ session_id: "S1", label: "New" });
  });
  it("patch posts only the given body", async () => {
    const f = stub(200, CRED);
    await vaultApi.update("VA1", { password: "x" });
    expect(call(f)[1].method).toBe("PATCH");
    expect(JSON.parse(call(f)[1].body as string)).toEqual({ password: "x" });
  });
  it("surfaces the envelope code", async () => {
    stub(409, [{ key: null, code: 4142, show: true, type: "domain_error", messages: ["A login named 'GitHub' already exists"] }]);
    const e = await vaultApi.create({ label: "GitHub", origins: ["https://github.com"] }).catch((x: unknown) => x);
    expect(e).toBeInstanceOf(DotApiError);
    expect((e as DotApiError).info.code).toBe(4142);
    expect((e as DotApiError).info.title).toContain("already exists");
  });
});
