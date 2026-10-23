import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ModeSwitch } from "./ModeSwitch";
import { ApiStatusModal } from "./ApiStatusModal";

export function AuthForm({ kind }: { kind: "login" | "register" }) {
  const { signIn, user, ready, mode } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (ready && user) nav({ to: "/" }); }, [ready, user, nav]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const token = kind === "login" ? await api.login(email, password) : await api.register(email, password);
      await signIn(token);
      toast.success(kind === "login" ? "Welcome back" : "Account created");
      nav({ to: "/" });
    } catch (err) {
      toast.error((err as Error).message);
    } finally { setBusy(false); }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm animate-in fade-in slide-in-from-bottom-2 duration-500">
        <div className="mb-8 flex items-center gap-2">
          <div className="flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground"><Layers className="size-5" /></div>
          <span className="font-display text-xl">Groundwork</span>
        </div>
        <h1 className="font-display text-3xl">{kind === "login" ? "Sign in" : "Create account"}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Ask questions grounded in your own documents.</p>
        <form onSubmit={submit} className="mt-6 space-y-4 rounded-lg border bg-card p-5">
          <div className="space-y-1.5"><Label htmlFor="email">Email</Label><Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <div className="space-y-1.5"><Label htmlFor="pw">Password</Label><Input id="pw" type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} /></div>
          <Button type="submit" className="w-full" disabled={busy}>{busy ? "Please wait…" : kind === "login" ? "Sign in" : "Register"}</Button>
        </form>
        <div className="mt-4 flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <ModeSwitch />
            <ApiStatusModal />
          </div>
          {kind === "login"
            ? <Link to="/register" className="text-primary hover:underline">Create account</Link>
            : <Link to="/login" className="text-primary hover:underline">Have an account?</Link>}
        </div>
      </div>
    </div>
  );
}
