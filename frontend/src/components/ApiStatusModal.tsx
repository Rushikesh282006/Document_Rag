import { useEffect, useState } from "react";
import { CheckCircle2, AlertCircle, RefreshCw, Server, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { settings, DEFAULT_BASE } from "@/lib/api";
import { toast } from "sonner";

export function ApiStatusModal() {
  const [open, setOpen] = useState(false);
  const [baseInput, setBaseInput] = useState(settings.base);
  const [checking, setChecking] = useState(false);
  const [status, setStatus] = useState<"connected" | "connecting" | "offline">("connecting");
  const [latency, setLatency] = useState<number | null>(null);

  const checkConnection = async (targetBase?: string) => {
    const url = (targetBase || settings.base).replace(/\/$/, "");
    setChecking(true);
    const start = performance.now();
    try {
      const res = await fetch(`${url}/health`, { method: "GET" });
      const elapsed = Math.round(performance.now() - start);
      if (res.ok) {
        setStatus("connected");
        setLatency(elapsed);
      } else {
        setStatus("offline");
        setLatency(null);
      }
    } catch {
      setStatus("offline");
      setLatency(null);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    checkConnection();
    const interval = setInterval(() => checkConnection(), 45000);
    return () => clearInterval(interval);
  }, []);

  const handleSave = async () => {
    settings.base = baseInput;
    toast.info("Testing new API endpoint...");
    await checkConnection(settings.base);
    if (status === "connected") {
      toast.success("Connected to backend successfully!");
    } else {
      toast.warning("Saved, but endpoint is currently unreachable or waking up.");
    }
    setOpen(false);
  };

  const handleReset = () => {
    setBaseInput(DEFAULT_BASE);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          onClick={() => {
            setBaseInput(settings.base);
            checkConnection();
          }}
          className="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors hover:bg-accent"
          title="Click to check or configure API backend"
        >
          <span
            className={`size-2 rounded-full ${
              status === "connected"
                ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"
                : status === "connecting"
                ? "bg-amber-500 animate-pulse"
                : "bg-red-500"
            }`}
          />
          <span className="hidden sm:inline">
            {status === "connected" ? (
              latency !== null ? `API: Online (${latency}ms)` : "API: Online"
            ) : status === "connecting" ? (
              "API: Connecting…"
            ) : (
              "API: Offline"
            )}
          </span>
          <Settings2 className="size-3 text-muted-foreground ml-0.5" />
        </button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Server className="size-5 text-primary" /> Backend API Status
          </DialogTitle>
          <DialogDescription>
            Verify connectivity to your FastAPI backend or update the connection URL.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="flex items-center justify-between rounded-lg border p-3 bg-muted/40">
            <div className="flex items-center gap-2.5">
              {status === "connected" ? (
                <CheckCircle2 className="size-5 text-emerald-500" />
              ) : (
                <AlertCircle className="size-5 text-amber-500" />
              )}
              <div>
                <p className="text-sm font-semibold capitalize">
                  {status === "connected" ? "Backend Connected" : "Backend Not Reachable"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {status === "connected"
                    ? `Responding normally (${latency ?? 0}ms round-trip)`
                    : "Server is cold-starting, sleeping, or URL is unreachable."}
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={checking}
              onClick={() => checkConnection(baseInput)}
            >
              <RefreshCw className={`size-3.5 mr-1.5 ${checking ? "animate-spin" : ""}`} />
              {checking ? "Checking…" : "Ping API"}
            </Button>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="api-base-input" className="text-xs font-semibold">
                API Base URL
              </Label>
              <button
                type="button"
                onClick={handleReset}
                className="text-xs text-primary underline hover:opacity-80"
              >
                Reset to default
              </button>
            </div>
            <Input
              id="api-base-input"
              value={baseInput}
              onChange={(e) => setBaseInput(e.target.value)}
              placeholder="https://your-api.onrender.com/api/v1"
              className="font-mono text-xs"
            />
            <p className="text-[11px] text-muted-foreground">
              Free-tier Render backends automatically spin down after 15 min of inactivity and take ~30-50s to wake up on the first request.
            </p>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Close
          </Button>
          <Button onClick={handleSave} disabled={checking}>
            Save & Connect
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
