"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/notice";
import { ApiError, authApi, setUnauthorizedHandler, type SessionInfo } from "@/lib/api";

/**
 * Session state for the whole app.
 *
 * The session itself is an httpOnly cookie the browser manages; this provider only
 * asks the API "who am I?" and keeps the answer. Real enforcement is in the API
 * (every data route returns 401 without a session), so this is about showing the
 * right screen, not about security.
 */
export type AuthState =
  | { status: "loading" }
  | { status: "authenticated"; user: SessionInfo }
  /** `reason` lets the sign-in screen say why the person is back there. */
  | { status: "anonymous"; reason?: "signed-out" | "expired" }
  /** The API could not be reached or failed: not the same as being signed out. */
  | { status: "error"; message: string };

interface AuthContextValue {
  state: AuthState;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  retry: () => void;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<AuthState>({ status: "loading" });

  const refresh = React.useCallback(async () => {
    setState({ status: "loading" });
    try {
      setState({ status: "authenticated", user: await authApi.me() });
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setState({ status: "anonymous" });
      } else {
        setState({
          status: "error",
          message: e instanceof Error ? e.message : "Could not check your session.",
        });
      }
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  // Any data request that comes back 401 means the session ended mid-use.
  React.useEffect(() => {
    setUnauthorizedHandler(() => setState({ status: "anonymous", reason: "expired" }));
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = React.useCallback(async (username: string, password: string) => {
    const user = await authApi.login(username, password);
    setState({ status: "authenticated", user });
  }, []);

  const logout = React.useCallback(async () => {
    // If this fails the cookie is still valid, so surface the error instead of
    // pretending the person is signed out.
    await authApi.logout();
    setState({ status: "anonymous", reason: "signed-out" });
  }, []);

  const value = React.useMemo(
    () => ({ state, login, logout, retry: () => void refresh() }),
    [state, login, logout, refresh]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Wraps page content: shows it once signed in, otherwise sends the person to /login. */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { state, retry } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const onLoginPage = pathname === "/login";

  React.useEffect(() => {
    if (state.status !== "anonymous" || onLoginPage) return;
    // Remember where they were, unless they chose to sign out.
    const here = window.location.pathname + window.location.search;
    router.replace(
      state.reason === "signed-out" ? "/login" : `/login?next=${encodeURIComponent(here)}`
    );
  }, [state, onLoginPage, router]);

  // The sign-in page handles every state itself.
  if (onLoginPage || state.status === "authenticated") return <>{children}</>;

  if (state.status === "error") {
    return (
      <div className="mx-auto max-w-xl space-y-4 py-12">
        <Notice tone="error" title="Could not check your session">
          {state.message}
        </Notice>
        <Button variant="outline" onClick={retry}>
          Try again
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {state.status === "loading" ? "Checking your session" : "Redirecting to sign in"}
    </div>
  );
}
