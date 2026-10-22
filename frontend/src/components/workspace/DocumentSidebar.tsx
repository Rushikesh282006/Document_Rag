import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileText, Trash2, UploadCloud } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api, type DocStatus, type RagDocument } from "@/lib/api";
import { cn } from "@/lib/utils";

export const docsKey = ["documents"] as const;
const ACTIVE: DocStatus[] = ["PENDING", "PROCESSING"];

const STATUS: Record<DocStatus, { label: string; cls: string }> = {
  PENDING: { label: "Queued", cls: "text-status-pending bg-status-pending/10" },
  PROCESSING: { label: "Embedding", cls: "text-status-processing bg-status-processing/10 animate-pulse" },
  COMPLETED: { label: "Ready", cls: "text-status-completed bg-status-completed/10" },
  FAILED: { label: "Failed", cls: "text-status-failed bg-status-failed/10" },
};

function StatusBadge({ doc }: { doc: RagDocument }) {
  const s = STATUS[doc.status] ?? STATUS.PENDING;
  const badge = <span className={cn("rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide", s.cls)}>{s.label}</span>;
  if (doc.status !== "FAILED") return badge;
  return <Tooltip><TooltipTrigger asChild>{badge}</TooltipTrigger><TooltipContent>{doc.error_message || "Ingestion failed"}</TooltipContent></Tooltip>;
}

/** Polls a single in-flight document every 2.5s and writes it into the list cache. */
function Poller({ id }: { id: string }) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["document", id],
    queryFn: () => api.getDocument(id),
    refetchInterval: (q) => (q.state.data && !ACTIVE.includes(q.state.data.status) ? false : 2500),
  });
  const last = useRef<DocStatus | null>(null);
  useEffect(() => {
    if (!data || data.status === last.current) return;
    last.current = data.status;
    qc.setQueryData<RagDocument[]>(docsKey, (old) => old?.map((d) => (d.id === id ? { ...d, ...data } : d)));
    if (data.status === "COMPLETED") toast.success(`${data.filename} is ready to query`);
    if (data.status === "FAILED") toast.error(`${data.filename} failed: ${data.error_message ?? "unknown error"}`);
  }, [data, id, qc]);
  return null;
}

export function DocumentSidebar({ selected, onSelectedChange }: { selected: string[]; onSelectedChange: (ids: string[]) => void }) {
  const qc = useQueryClient();
  const { data: docs, isLoading, error } = useQuery({ queryKey: docsKey, queryFn: api.listDocuments });
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const upload = useMutation({
    mutationFn: api.upload,
    onSuccess: (r) => {
      toast.success(`Uploaded ${r.filename} — processing started`);
      qc.setQueryData<RagDocument[]>(docsKey, (old) => [{ id: r.document_id, filename: r.filename, status: r.status, created_at: new Date().toISOString() }, ...(old ?? [])]);
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const remove = useMutation({
    mutationFn: api.deleteDocument,
    onSuccess: (_, id) => {
      qc.setQueryData<RagDocument[]>(docsKey, (old) => old?.filter((d) => d.id !== id));
      onSelectedChange(selected.filter((s) => s !== id));
      toast.success("Document deleted");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const handleFiles = (files: FileList | null) => {
    for (const f of Array.from(files ?? [])) {
      if (f.type !== "application/pdf" && !f.name.toLowerCase().endsWith(".pdf")) { toast.error(`${f.name} is not a PDF`); continue; }
      upload.mutate(f);
    }
  };
  const toggle = (id: string) => onSelectedChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]);

  return (
    <div className="flex h-full flex-col">
      <div className="p-4">
        <h2 className="mb-3 font-display text-lg">Knowledge base</h2>
        <button
          type="button"
          onClick={() => input.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); handleFiles(e.dataTransfer.files); }}
          className={cn("flex w-full flex-col items-center gap-1 rounded-lg border border-dashed px-3 py-5 text-center text-xs text-muted-foreground transition-colors hover:border-primary hover:text-foreground", drag && "border-primary bg-primary/5 text-foreground")}
        >
          <UploadCloud className={cn("size-5", upload.isPending && "animate-bounce text-primary")} />
          {upload.isPending ? "Uploading…" : "Drop PDFs or click to upload"}
        </button>
        <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden onChange={(e) => { handleFiles(e.target.files); e.target.value = ""; }} />
      </div>

      <div className="flex items-center justify-between px-4 pb-2 text-xs text-muted-foreground">
        <span>{selected.length ? `${selected.length} selected for queries` : "Querying all documents"}</span>
        {selected.length > 0 && <button className="text-primary hover:underline" onClick={() => onSelectedChange([])}>Clear</button>}
      </div>

      <div className="flex-1 space-y-1 overflow-y-auto px-2 pb-4">
        {isLoading && Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="mx-2 h-12" />)}
        {error && <p className="px-2 text-xs text-destructive">{(error as Error).message}</p>}
        {docs && docs.length === 0 && (
          <div className="px-4 py-10 text-center text-sm text-muted-foreground">
            <FileText className="mx-auto mb-2 size-6 opacity-50" />
            Upload your first PDF to begin querying your knowledge base.
          </div>
        )}
        {docs?.map((d) => (
          <div key={d.id} className="group flex items-start gap-2 rounded-md px-2 py-2 hover:bg-sidebar-accent">
            {ACTIVE.includes(d.status) && <Poller id={d.id} />}
            <Checkbox className="mt-0.5" checked={selected.includes(d.id)} disabled={d.status !== "COMPLETED"} onCheckedChange={() => toggle(d.id)} aria-label={`Filter by ${d.filename}`} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm" title={d.filename}>{d.filename}</p>
              <div className="mt-1 flex items-center gap-2">
                <StatusBadge doc={d} />
                <span className="text-[11px] text-muted-foreground">{new Date(d.created_at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })}</span>
              </div>
            </div>
            <button
              aria-label={`Delete ${d.filename}`}
              className="opacity-0 transition-opacity group-hover:opacity-100 text-muted-foreground hover:text-destructive"
              onClick={() => { if (confirm(`Delete ${d.filename}?`)) remove.mutate(d.id); }}
            ><Trash2 className="size-4" /></button>
          </div>
        ))}
      </div>
    </div>
  );
}
