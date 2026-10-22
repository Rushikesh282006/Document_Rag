import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { api, AUTH_EXPIRED_EVENT, settings, type Me, type Mode } from "./api";

interface AuthCtx {
  user: Me | null;
  ready: boolean;
  mode: Mode;
  setMode: (m: Mode) => void;
  signIn: (token: string) => Promise<void>;
  signOut: () => void;
}
const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);
  const [mode, setModeState] = useState<Mode>("live");

  const signOut = useCallback(() => { settings.token = null; setUser(null); }, []);

  useEffect(() => {
    setModeState(settings.mode);
    if (!settings.token) { setReady(true); return; }
    api.me().then(setUser).catch(() => { settings.token = null; }).finally(() => setReady(true));
  }, []);

  useEffect(() => {
    const onExpired = () => { if (settings.token) toast.error("Session expired — please sign in again."); signOut(); };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, [signOut]);

  const signIn = async (token: string) => {
    settings.token = token;
    setUser(await api.me());
  };
  const setMode = (m: Mode) => { settings.mode = m; setModeState(m); signOut(); };

  return <Ctx.Provider value={{ user, ready, mode, setMode, signIn, signOut }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used inside AuthProvider");
  return c;
}
