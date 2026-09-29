"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth-provider";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Briefing" },
  { href: "/decisions", label: "Decisions" },
  { href: "/decisions/new", label: "Record decision" },
  { href: "/audit", label: "Audit log" },
  { href: "/missing", label: "Missing outcomes" },
];

function isActive(href: string, pathname: string): boolean {
  if (href === "/") return pathname === "/";
  // "/decisions" owns the list and detail pages, but not the "new" form.
  if (href === "/decisions") return pathname.startsWith("/decisions") && pathname !== "/decisions/new";
  return pathname === href;
}

export function Navigation() {
  const pathname = usePathname();
  const { state, logout } = useAuth();
  const [signOutError, setSignOutError] = useState<string | null>(null);

  // Signed-out visitors only see the brand: there is nothing to navigate to yet.
  const user = state.status === "authenticated" ? state.user : null;

  const handleSignOut = async () => {
    setSignOutError(null);
    try {
      await logout(); // AuthGate then routes to /login
    } catch (e) {
      setSignOutError(e instanceof Error ? e.message : "Could not sign out.");
    }
  };

  return (
    <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 px-4">
        <Link href="/" className="flex items-baseline gap-2 py-3 sm:py-4">
          <span className="text-base font-semibold tracking-tight">ArchMemory</span>
          <span className="hidden text-xs text-muted-foreground lg:inline">Architecture decision memory</span>
        </Link>

        {user && (
          <nav
            aria-label="Main"
            className="-mx-4 order-3 flex w-[calc(100%+2rem)] overflow-x-auto px-4 sm:order-2 sm:mx-0 sm:w-auto sm:flex-1 sm:px-0"
          >
            {navItems.map(({ href, label }) => {
              const active = isActive(href, pathname);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "whitespace-nowrap border-b-2 px-3 py-3 text-sm transition-colors sm:py-[1.125rem]",
                    active
                      ? "border-primary font-medium text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  )}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        )}

        {user && user.auth_enabled && (
          <div className="order-2 flex items-center gap-2 sm:order-3">
            {signOutError && (
              <span role="alert" className="text-xs text-destructive">
                {signOutError}
              </span>
            )}
            <span className="hidden text-sm text-muted-foreground sm:inline">{user.username}</span>
            <Button type="button" variant="ghost" size="sm" onClick={handleSignOut}>
              Sign out
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
