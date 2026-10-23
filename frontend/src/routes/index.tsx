import { useEffect, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Layers, LogOut, PanelLeft, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { DocumentSidebar } from "@/components/workspace/DocumentSidebar";
import { Chat } from "@/components/workspace/Chat";
import { ModeSwitch } from "@/components/ModeSwitch";
import { ApiStatusModal } from "@/components/ApiStatusModal";
import { useAuth } from "@/lib/auth";
import { useIsMobile } from "@/hooks/use-mobile";
import type { Source } from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Workspace — Groundwork RAG" },
      { name: "description", content: "Chat with your PDFs: upload documents, stream grounded answers, and inspect every citation." },
      { property: "og:title", content: "Workspace — Groundwork RAG" },
      { property: "og:description", content: "Chat with your PDFs and inspect every citation." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Workspace,
});

function Workspace() {
  const { user, ready, signOut } = useAuth();
  const nav = useNavigate();
  const isMobile = useIsMobile();
  const [selected, setSelected] = useState<string[]>([]);
  const [sidebar, setSidebar] = useState(true);
  const [citation, setCitation] = useState<{ s: Source; i: number } | null>(null);

  useEffect(() => { if (ready && !user) nav({ to: "/login" }); }, [ready, user, nav]);
  useEffect(() => { setSidebar(!isMobile); }, [isMobile]);

  if (!ready || !user) return <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">Loading…</div>;

  const inspector = citation && (
    <div className="space-y-4 text-sm">
      <div><p className="text-xs text-muted-foreground">Document</p><p className="break-all font-medium">{citation.s.document_name}</p></div>
      <div className="flex gap-6">
        <div><p className="text-xs text-muted-foreground">Page</p><p className="font-mono">{citation.s.page ?? "—"}</p></div>
        <div className="flex-1"><p className="text-xs text-muted-foreground">Relevance score</p>
          {citation.s.score != null ? (
            <div className="flex items-center gap-2"><div className="h-1.5 flex-1 rounded bg-muted"><div className="h-full rounded bg-primary" style={{ width: `${Math.min(100, Math.abs(citation.s.score) * 100)}%` }} /></div><span className="font-mono text-xs">{citation.s.score.toFixed(3)}</span></div>
          ) : <p>—</p>}
        </div>
      </div>
      <div><p className="mb-1 text-xs text-muted-foreground">Snippet</p><blockquote className="rounded-md border-l-2 border-primary bg-muted p-3 font-serif leading-relaxed">{citation.s.snippet || "No snippet provided."}</blockquote></div>
    </div>
  );

  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-12 shrink-0 items-center justify-between border-b px-3">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => setSidebar((v) => !v)} aria-label="Toggle documents"><PanelLeft className="size-4" /></Button>
          <Layers className="size-4 text-primary" /><span className="font-display">Groundwork</span>
        </div>
        <div className="flex items-center gap-3">
          <ApiStatusModal />
          <ModeSwitch />
          <span className="hidden text-xs text-muted-foreground sm:inline">{user.email}</span>
          <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out"><LogOut className="size-4" /></Button>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        {isMobile ? (
          <Sheet open={sidebar} onOpenChange={setSidebar}>
            <SheetContent side="left" className="w-80 bg-sidebar p-0"><SheetHeader className="sr-only"><SheetTitle>Documents</SheetTitle><SheetDescription>Knowledge base</SheetDescription></SheetHeader><DocumentSidebar selected={selected} onSelectedChange={setSelected} /></SheetContent>
          </Sheet>
        ) : (
          <aside className={cn("shrink-0 overflow-hidden border-r bg-sidebar transition-[width] duration-300", sidebar ? "w-80" : "w-0")}>
            <div className="h-full w-80"><DocumentSidebar selected={selected} onSelectedChange={setSelected} /></div>
          </aside>
        )}
        <main className="min-w-0 flex-1"><Chat selected={selected} onCitation={(s, i) => setCitation({ s, i })} /></main>
        {!isMobile && citation && (
          <aside className="w-96 shrink-0 overflow-y-auto border-l bg-sidebar p-4 animate-in slide-in-from-right">
            <div className="mb-4 flex items-center justify-between"><h2 className="font-display text-lg">Source [{citation.i + 1}]</h2><Button variant="ghost" size="icon" onClick={() => setCitation(null)} aria-label="Close"><X className="size-4" /></Button></div>
            {inspector}
          </aside>
        )}
        {isMobile && (
          <Sheet open={!!citation} onOpenChange={(o) => !o && setCitation(null)}>
            <SheetContent side="bottom"><SheetHeader><SheetTitle>Source [{(citation?.i ?? 0) + 1}]</SheetTitle><SheetDescription>Citation details</SheetDescription></SheetHeader><div className="p-4">{inspector}</div></SheetContent>
          </Sheet>
        )}
      </div>
    </div>
  );
}
