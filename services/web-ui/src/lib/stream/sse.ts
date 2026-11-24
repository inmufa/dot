/** Incremental SSE parser: feed text chunks, get the data payload of each completed frame. */
export class SseParser {
  private buf = "";
  private data: string[] = [];

  feed(chunk: string): string[] {
    this.buf += chunk;
    const out: string[] = [];
    let idx: number;
    // Lines end with \n, \r\n or \r; hold a trailing \r until we know what follows.
    while ((idx = this.nextBreak()) >= 0) {
      const line = this.buf.slice(0, idx);
      const skip = this.buf.startsWith("\r\n", idx) ? 2 : 1;
      this.buf = this.buf.slice(idx + skip);
      const frame = this.line(line);
      if (frame !== null) out.push(frame);
    }
    return out;
  }

  /** Flush a final unterminated frame at end of stream. */
  end(): string[] {
    const out = this.feed("\n");
    if (this.data.length) {
      out.push(this.data.join("\n"));
      this.data = [];
    }
    return out;
  }

  private nextBreak(): number {
    for (let i = 0; i < this.buf.length; i++) {
      const c = this.buf[i];
      if (c === "\n") return i;
      if (c === "\r") return i + 1 < this.buf.length || this.buf.length === 0 ? i : -1;
    }
    return -1;
  }

  private line(line: string): string | null {
    if (line === "") {
      if (!this.data.length) return null;
      const frame = this.data.join("\n");
      this.data = [];
      return frame;
    }
    if (line.startsWith(":")) return null;
    const colon = line.indexOf(":");
    const field = colon < 0 ? line : line.slice(0, colon);
    if (field !== "data") return null;
    let value = colon < 0 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    this.data.push(value);
    return null;
  }
}

/** Async iterate data payloads of an SSE response body. */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = body.getReader();
  const dec = new TextDecoder();
  const parser = new SseParser();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      yield* parser.feed(dec.decode(value, { stream: true }));
    }
    yield* parser.feed(dec.decode());
    yield* parser.end();
  } finally {
    reader.releaseLock();
  }
}
