"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/notice";
import { useAuth } from "@/components/auth-provider";
import { safeNext } from "@/lib/auth";

function SignInForm() {
  const { state, login, retry } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Covers both "already signed in" and "just signed in".
  useEffect(() => {
    if (state.status === "authenticated") router.replace(next);
  }, [state.status, next, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
      setSubmitting(false);
    }
  };

  if (state.status === "authenticated") {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Signing in
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          Use the account your administrator created for you.
        </p>
      </div>

      {state.status === "anonymous" && state.reason === "expired" && !error && (
        <Notice tone="info" title="Your session ended">
          Sign in again to continue where you left off.
        </Notice>
      )}

      {state.status === "error" && (
        <Notice tone="error" title="Could not reach the API">
          <p>{state.message}</p>
          <Button type="button" size="sm" variant="outline" onClick={retry} className="mt-2 bg-background">
            Try again
          </Button>
        </Notice>
      )}

      {error && (
        <Notice tone="error" title="Could not sign in">
          {error}
        </Notice>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="username">Username</Label>
          <Input
            id="username"
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            autoFocus
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <Button type="submit" className="w-full" disabled={submitting || !username.trim() || !password}>
          {submitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> Signing in
            </>
          ) : (
            "Sign in"
          )}
        </Button>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="mx-auto max-w-sm pt-6 sm:pt-16">
      {/* useSearchParams needs a Suspense boundary for static rendering. */}
      <Suspense fallback={null}>
        <SignInForm />
      </Suspense>
    </div>
  );
}
