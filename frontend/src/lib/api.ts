import { safeUUID } from "@/lib/utils";

// API client for the FastAPI RAG backend, with an in-browser mock fallback.
export type DocStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
export interface RagDocument {
  id: string;
  filename: string;
  status: DocStatus;
  created_at: string;
  error_message?: string | null;
}
export interface Source {
  document_id?: string;
  document_name: string;
  page?: number | null;
  snippet: string;
  score?: number | null;
}
export interface Me {
  id: string;
  email: string;
  tenant_id?: string;
}
export type Mode = "live" | "mock";

const KEY_TOKEN = "rag.token";
const KEY_MODE = "rag.mode";
const KEY_BASE = "rag.base";
export const DEFAULT_BASE =
  (typeof import.meta !== "undefined" && (import.meta.env?.["VITE_API_BASE_URL"] || import.meta.env?.["VITE_API_URL"])) ||
  "https://document-rag-z7e2.onrender.com/api/v1";

const ls = () => (typeof window === "undefined" ? null : window.localStorage);
export const settings = {
  get token() { return ls()?.getItem(KEY_TOKEN) ?? null; },
  set token(v: string | null) { v ? ls()?.setItem(KEY_TOKEN, v) : ls()?.removeItem(KEY_TOKEN); },
  get mode(): Mode { return (ls()?.getItem(KEY_MODE) as Mode) ?? "live"; },
  set mode(v: Mode) { ls()?.setItem(KEY_MODE, v); },
  get base() {
    return DEFAULT_BASE.replace(/\/$/, "");
  },
  set base(v: string) {
    if (v) ls()?.setItem(KEY_BASE, v);
  },
};


export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export const AUTH_EXPIRED_EVENT = "rag:auth-expired";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const t = settings.token;
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`${settings.base}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, `Cannot reach backend at ${settings.base}`);
  }
  if (res.status === 401) window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* ignore */ }
    throw new ApiError(res.status, msg || `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ---------- SSE parsing ----------
export interface SSEEvent { event: string; data: string }
/** Splits a buffer into complete SSE events; returns parsed events and the leftover tail. */
export function parseSSE(buffer: string): { events: SSEEvent[]; rest: string } {
  const norm = buffer.replace(/\r\n/g, "\n");
  const blocks = norm.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: SSEEvent[] = [];
  for (const block of blocks) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    if (data.length || event !== "message") events.push({ event, data: data.join("\n") });
  }
  return { events, rest };
}

export interface StreamHandlers {
  onSources: (s: Source[]) => void;
  onToken: (t: string) => void;
  onEnd: () => void;
  onError: (msg: string) => void;
}
export interface QueryBody { query: string; document_ids?: string[]; top_k: number; stream: true }

export function normalizeSources(raw: unknown): Source[] {
  const r = raw as Record<string, unknown> | unknown[];
  const arr = Array.isArray(r)
    ? r
    : ((r?.["citations"] ?? r?.["sources"]) as unknown[]) ?? [];
  return (arr as Record<string, unknown>[]).map((s) => ({
    document_id: (s["document_id"] as string) ?? undefined,
    document_name: (s["document_name"] ?? s["filename"] ?? s["source"] ?? "Unknown document") as string,
    page: (s["page"] ?? s["page_number"] ?? null) as number | null,
    snippet: (s["snippet"] ?? s["content_preview"] ?? s["content"] ?? s["text"] ?? "") as string,
    score: (s["score"] ?? s["fusion_score"] ?? s["relevance"] ?? null) as number | null,
  }));
}

function tokenText(data: string): string {
  try {
    const j = JSON.parse(data);
    if (typeof j === "string") return j;
    return j.token ?? j.text ?? j.content ?? "";
  } catch { return data; }
}

async function liveStream(body: QueryBody, h: StreamHandlers, signal: AbortSignal) {
  const headers: Record<string, string> = { "Content-Type": "application/json", Accept: "text/event-stream" };
  if (settings.token) headers["Authorization"] = `Bearer ${settings.token}`;
  let res: Response;
  try {
    res = await fetch(`${settings.base}/query`, { method: "POST", headers, body: JSON.stringify(body), signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") return h.onEnd();
    return h.onError(`Cannot reach backend at ${settings.base}`);
  }
  if (res.status === 401) window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  if (!res.ok || !res.body) return h.onError(`Query failed (${res.status})`);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let ended = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const { events, rest } = parseSSE(buf);
      buf = rest;
      for (const ev of events) {
        if (ev.event === "sources") { try { h.onSources(normalizeSources(JSON.parse(ev.data))); } catch { /* ignore */ } }
        else if (ev.event === "token" || ev.event === "message") h.onToken(tokenText(ev.data));
        else if (ev.event === "error") { ended = true; h.onError(tokenText(ev.data) || "Stream error"); }
        else if (ev.event === "end") { ended = true; h.onEnd(); }
      }
    }
  } catch (e) {
    if ((e as Error).name !== "AbortError") { ended = true; h.onError("Stream interrupted"); }
  }
  if (!ended) h.onEnd();
}

// ---------- Mock backend ----------
const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((r, j) => {
    const t = setTimeout(r, ms);
    signal?.addEventListener("abort", () => { clearTimeout(t); j(new DOMException("aborted", "AbortError")); });
  });
const mockDocs: (RagDocument & { _born: number })[] = [
  { id: "d-1", filename: "annual_report_2025.pdf", status: "COMPLETED", created_at: new Date(Date.now() - 864e5).toISOString(), _born: 0 },
  { id: "d-2", filename: "security_whitepaper.pdf", status: "COMPLETED", created_at: new Date(Date.now() - 36e5).toISOString(), _born: 0 },
];
function tickMock(d: (typeof mockDocs)[number]) {
  if (!d._born) return;
  const age = Date.now() - d._born;
  d.status = age < 3000 ? "PENDING" : age < 8000 ? "PROCESSING" : d.filename.includes("fail") ? "FAILED" : "COMPLETED";
  if (d.status === "FAILED") d.error_message = "Could not extract text from PDF";
}
const strip = ({ _born, ...d }: (typeof mockDocs)[number]): RagDocument => { void _born; return { ...d }; };

const mock = {
  async login(email: string): Promise<string> { await sleep(400); return `mock.${btoa(email)}`; },
  async me(): Promise<Me> { const t = settings.token ?? ""; return { id: "u-1", email: t.startsWith("mock.") ? atob(t.slice(5)) : "demo@tenant.dev", tenant_id: "tenant-demo" }; },
  async list(): Promise<RagDocument[]> { await sleep(300); mockDocs.forEach(tickMock); return mockDocs.map(strip); },
  async get(id: string): Promise<RagDocument> { const d = mockDocs.find((x) => x.id === id); if (!d) throw new ApiError(404, "Not found"); tickMock(d); return strip(d); },
  async upload(file: File) {
    await sleep(500);
    const d = { id: `d-${safeUUID().slice(0, 8)}`, filename: file.name, status: "PENDING" as DocStatus, created_at: new Date().toISOString(), _born: Date.now() };
    mockDocs.unshift(d);
    return { job_id: `job-${d.id}`, document_id: d.id, filename: d.filename, status: "PENDING" as DocStatus };
  },
  async remove(id: string) { const i = mockDocs.findIndex((x) => x.id === id); if (i >= 0) mockDocs.splice(i, 1); },
  async stream(body: QueryBody, h: StreamHandlers, signal: AbortSignal) {
    try {
      await sleep(500, signal);
      const pool = mockDocs.filter((d) => d.status === "COMPLETED" && (!body.document_ids?.length || body.document_ids.includes(d.id)));
      if (!pool.length) return h.onError("No ready documents match your filter.");
      const srcs: Source[] = pool.slice(0, Math.min(3, body.top_k)).map((d, i) => ({
        document_id: d.id, document_name: d.filename, page: 2 + i * 3, score: +(0.92 - i * 0.07).toFixed(3),
        snippet: `…the ${["operating margin rose to 18.4% driven by lower infrastructure cost", "tenant data is isolated through row-level security and per-tenant vector namespaces", "retrieval combines BM25 and dense embeddings via reciprocal rank fusion"][i % 3]}…`,
      }));
      h.onSources(srcs);
      const answer = `Here's what I found for **"${body.query}"**:\n\n1. The operating margin improved to **18.4%** [1].\n2. Tenant isolation relies on row-level security and separate vector namespaces [2].\n3. Retrieval uses hybrid search with reciprocal rank fusion:\n\n\`\`\`python\nscore = sum(1 / (60 + rank) for rank in ranks)\n\`\`\`\n\n_This is a demo answer — switch to Live mode to query your FastAPI backend._`;
      for (const tok of answer.match(/\S+\s*|\s+/g) ?? []) { await sleep(25, signal); h.onToken(tok); }
      h.onEnd();
    } catch { h.onEnd(); }
  },
};

// ---------- Public API ----------
const live = () => settings.mode === "live";
export const api = {
  async register(email: string, password: string) {
    if (!live()) return mock.login(email);
    await request("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) });
    return api.login(email, password);
  },
  async login(email: string, password: string): Promise<string> {
    if (!live()) return mock.login(email);
    const r = await request<{ access_token: string }>("/auth/login/json", { method: "POST", body: JSON.stringify({ email, password }) });
    return r.access_token;
  },
  me: () => (live() ? request<Me>("/auth/me") : mock.me()),
  listDocuments: async (): Promise<RagDocument[]> => {
    if (!live()) return mock.list();
    const r = await request<RagDocument[] | { documents?: RagDocument[]; items?: RagDocument[] }>("/documents");
    return Array.isArray(r) ? r : r.documents ?? r.items ?? [];
  },
  getDocument: (id: string) => (live() ? request<RagDocument>(`/documents/${id}`) : mock.get(id)),
  upload: (file: File) => {
    if (!live()) return mock.upload(file);
    const fd = new FormData();
    fd.append("file", file);
    return request<{ job_id: string; document_id: string; filename: string; status: DocStatus }>("/documents/upload", { method: "POST", body: fd });
  },
  deleteDocument: (id: string) => (live() ? request<void>(`/documents/${id}`, { method: "DELETE" }) : mock.remove(id)),
  streamQuery: (body: QueryBody, h: StreamHandlers, signal: AbortSignal) =>
    live() ? liveStream(body, h, signal) : mock.stream(body, h, signal),
};
