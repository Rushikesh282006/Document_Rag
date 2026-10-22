import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/lib/auth";

export function ModeSwitch() {
  const { mode, setMode } = useAuth();
  return (
    <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
      <Switch checked={mode === "live"} onCheckedChange={(v) => setMode(v ? "live" : "mock")} />
      {mode === "live" ? <span className="text-status-completed">Live API</span> : <span>Demo mode</span>}
    </label>
  );
}
