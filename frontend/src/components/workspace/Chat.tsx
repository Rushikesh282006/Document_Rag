import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { toast } from "sonner";
import { AlertTriangle, ArrowDown, Copy, Lock, SendHorizontal, Square, Unlock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { api, type Source } from "@/lib/api";
import { cn, safeUUID } from "@/lib/utils";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  streaming?: boolean;
  error?: string;
  filterCount?: number;
}

export function Chat({ selected, onCitation }: { selected: string[]; onCitation: (s: Source, i: number) => void }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [topK, setTopK] = useState(5);
  const [autoScroll, setAutoScroll] = useState(true);
  const abort = useRef<AbortController | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const streaming = messages.some((m) => m.streaming);

  useEffect(() => {
    if (autoScroll && scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [messages, autoScroll]);

  const patch = (id: string, fn: (m: Message) => Message) => setMessages((ms) => ms.map((m) => (m.id === id ? fn(m) : m)));

  const send = () => {
    const q = input.trim();
    if (!q || streaming) return;
    const aid = safeUUID();
    setMessages((ms) => [...ms, { id: safeUUID(), role: "user", content: q, filterCount: selected.length }, { id: aid, role: "assistant", content: "", streaming: true }]);
    setInput("");
    setAutoScroll(true);
    const ctrl = new AbortController();
    abort.current = ctrl;
    api.streamQuery(
      { query: q, top_k: topK, stream: true, ...(selected.length ? { document_ids: selected } : {}) },
      {
        onSources: (s) => patch(aid, (m) => ({ ...m, sources: s })),
        onToken: (t) => patch(aid, (m) => ({ ...m, content: m.content + t })),
        onEnd: () => patch(aid, (m) => ({ ...m, streaming: false })),
        onError: (e) => patch(aid, (m) => ({ ...m, streaming: false, error: e })),
      },
      ctrl.signal,
    );
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={scroller} onWheel={(e) => { if (e.deltaY < 0 && streaming) setAutoScroll(false); }} className="relative flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="bg-glow flex h-full flex-col items-center justify-center px-6 text-center">
            <h1 className="font-display text-4xl">Ask your documents.</h1>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">Every answer is grounded in your knowledge base, with citations you can inspect.</p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {["What are the key findings?", "Summarize the security model", "How does retrieval rank results?"].map((s) => (
                <button key={s} onClick={() => setInput(s)} className="rounded-full border px-3 py-1.5 text-xs text-muted-foreground hover:border-primary hover:text-foreground">{s}</button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
            {messages.map((m) => <MessageView key={m.id} m={m} onCitation={onCitation} />)}
          </div>
        )}
      </div>
      {!autoScroll && streaming && (
        <div className="flex justify-center"><Button size="sm" variant="secondary" className="-mt-12 rounded-full shadow" onClick={() => setAutoScroll(true)}><ArrowDown className="size-4" /> Follow stream</Button></div>
      )}

      <div className="border-t bg-background/80 p-3 backdrop-blur">
        <div className="mx-auto max-w-3xl">
          <div className="rounded-lg border bg-card focus-within:border-primary">
            <Textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} rows={2} placeholder="Ask a question about your documents…" className="resize-none border-0 bg-transparent shadow-none focus-visible:ring-0" />
            <div className="flex items-center justify-between gap-2 px-2 pb-2">
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Popover>
                  <PopoverTrigger asChild><Button variant="ghost" size="sm" className="font-mono text-xs">top_k {topK}</Button></PopoverTrigger>
                  <PopoverContent className="w-56"><p className="mb-3 text-xs text-muted-foreground">Chunks to retrieve: {topK}</p><Slider min={1} max={20} step={1} value={[topK]} onValueChange={([v]) => { if (v !== undefined) setTopK(v); }} /></PopoverContent>
                </Popover>
                <Button variant="ghost" size="sm" onClick={() => setAutoScroll((v) => !v)} title="Toggle auto-scroll">
                  {autoScroll ? <Unlock className="size-3.5" /> : <Lock className="size-3.5" />} <span className="hidden sm:inline">{autoScroll ? "Auto-scroll" : "Scroll locked"}</span>
                </Button>
                <span className="hidden md:inline">{selected.length ? `${selected.length} doc filter` : "All docs"}</span>
              </div>
              {streaming
                ? <Button size="sm" variant="secondary" onClick={() => abort.current?.abort()}><Square className="size-3.5" /> Stop</Button>
                : <Button size="sm" onClick={send} disabled={!input.trim()}><SendHorizontal className="size-4" /> Send</Button>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MessageView({ m, onCitation }: { m: Message; onCitation: (s: Source, i: number) => void }) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end animate-in fade-in slide-in-from-bottom-1">
        <div className="max-w-[85%] rounded-lg bg-secondary px-4 py-2.5 text-sm">
          {m.content}
          {!!m.filterCount && <div className="mt-1 text-[11px] text-muted-foreground">Scoped to {m.filterCount} document{m.filterCount > 1 ? "s" : ""}</div>}
        </div>
      </div>
    );
  }
  return (
    <div className="animate-in fade-in">
      {m.sources && m.sources.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {m.sources.map((s, i) => (
            <button key={i} onClick={() => onCitation(s, i)} className="flex items-center gap-1.5 rounded-md border bg-card px-2 py-1 text-xs hover:border-primary">
              <span className="font-mono text-primary">[{i + 1}]</span>
              <span className="max-w-40 truncate">{s.document_name}</span>
              {s.page != null && <span className="text-muted-foreground">p.{s.page}</span>}
            </button>
          ))}
        </div>
      )}
      <div className={cn("prose-chat text-sm", m.streaming && "streaming-caret")}>
        {m.content ? <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>{m.content}</ReactMarkdown> : m.streaming && <span className="text-muted-foreground">Retrieving context…</span>}
      </div>
      {m.error && (
        <div className="mt-2 flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          <AlertTriangle className="size-4" /> {m.error}
        </div>
      )}
      {!m.streaming && m.content && (
        <button className="mt-1 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground" onClick={() => { navigator.clipboard.writeText(m.content); toast.success("Copied"); }}>
          <Copy className="size-3" /> Copy
        </button>
      )}
    </div>
  );
}
