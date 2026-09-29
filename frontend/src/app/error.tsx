"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/notice";

/** Catches render errors in any page so one broken screen does not blank the app. */
export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto max-w-xl space-y-4 py-12">
      <Notice tone="error" title="This page hit an unexpected error">
        <p>The rest of the app is unaffected. Load the page again; if it keeps failing, check the API logs.</p>
        {error.digest && <p className="font-mono text-xs">Reference: {error.digest}</p>}
      </Notice>
      <div className="flex gap-2">
        <Button onClick={reset}>Try again</Button>
        <Button variant="outline" asChild>
          <Link href="/">Go to briefing</Link>
        </Button>
      </div>
    </div>
  );
}
