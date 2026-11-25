// Multipart upload parsed by hand: limits 5 files per session, 20 MB each, mime allowlist (415 / 4020).
import { st, nid, json, readRaw } from "./core.mjs";

const MAX_BYTES = 20 * 1024 * 1024;
const MAX_FILES = 5;
const ALLOWED = /^(image\/(png|jpeg|gif|webp)|application\/(pdf|json|vnd\.openxmlformats-officedocument\.wordprocessingml\.document)|text\/[\w.+-]+)$/;

/** @returns {{name:string, filename:string, mime:string, data:Buffer}[]} */
export function parseMultipart(buf, contentType) {
  const boundary = /boundary=(?:"([^"]+)"|([^;]+))/i.exec(contentType ?? "");
  if (!boundary) return [];
  const delim = Buffer.from(`--${boundary[1] ?? boundary[2]}`);
  const parts = [];
  let pos = buf.indexOf(delim);
  while (pos !== -1) {
    const start = pos + delim.length;
    if (buf.slice(start, start + 2).toString() === "--") break;
    const next = buf.indexOf(delim, start);
    if (next === -1) break;
    const part = buf.slice(start + 2, next - 2); // strip CRLF around the part
    const split = part.indexOf("\r\n\r\n");
    if (split !== -1) {
      const head = part.slice(0, split).toString("utf8");
      parts.push({
        name: /name="([^"]*)"/i.exec(head)?.[1] ?? "",
        filename: /filename="([^"]*)"/i.exec(head)?.[1] ?? "",
        mime: /content-type:\s*([^\r\n;]+)/i.exec(head)?.[1]?.trim().toLowerCase() ?? "application/octet-stream",
        data: part.slice(split + 4),
      });
    }
    pos = next;
  }
  return parts;
}

const kindOfMime = (m) => (m.startsWith("image/") ? "image" : m.startsWith("text/") || m === "application/json" ? "text" : "doc");

export async function attachmentRoutes(req, res, s, fail) {
  if (req.method !== "POST") return fail(1002, "Not found", 404), true;
  const raw = await readRaw(req, MAX_BYTES + 1024 * 1024);
  if (!raw) return fail(4021, "File is larger than 20 MB", 413), true;
  const file = parseMultipart(raw, req.headers["content-type"]).find((p) => (p.name === "files" || p.name === "file") && p.filename);
  if (!file) return fail(4023, "Multipart field `file` is required", 400), true;
  if (!ALLOWED.test(file.mime)) return fail(4020, `File type ${file.mime} is not allowed`, 415), true;
  if (file.data.length > MAX_BYTES) return fail(4021, "File is larger than 20 MB", 413), true;
  if (!st.uploads.has(s.id)) st.uploads.set(s.id, new Map());
  const store = st.uploads.get(s.id);
  if (store.size >= MAX_FILES) return fail(4022, "At most 5 attachments per session", 409), true;
  const meta = { id: `AT${String(nid()).padStart(8, "0")}`, name: file.filename, mime: file.mime, size: file.data.length, kind: kindOfMime(file.mime) };
  store.set(meta.id, { ...meta, buf: file.data });
  return json(res, 201, [meta]), true;
}
