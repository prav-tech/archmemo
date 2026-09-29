"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/notice";
import { PageHeader } from "@/components/page-header";
import { decisionsApi, type MissingOutcomeItem } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

function ageStyle(days: number): string {
  if (days > 180) return "bg-destructive/10 text-destructive";
  if (days > 90) return "bg-warning-soft text-warning";
  return "bg-secondary text-secondary-foreground";
}

export default function MissingOutcomesPage() {
  const [items, setItems] = useState<MissingOutcomeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    decisionsApi
      .missingOutcomes()
      .then(setItems)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Missing outcomes"
        description="Active decisions that have no recorded outcome, oldest first. Until an outcome is recorded, briefings can only say what was decided, not how it turned out."
      />

      {loading && (
        <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Loading decisions
        </div>
      )}
      {error && <Notice tone="error" title="Could not load this list">{error}</Notice>}

      {!loading && !error && items.length === 0 && (
        <Notice tone="success" title="Every active decision has an outcome">
          Nothing to record right now.
        </Notice>
      )}

      {items.length > 0 && (
        <>
          <p className="text-sm text-muted-foreground">
            {items.length} {items.length === 1 ? "decision needs" : "decisions need"} an outcome.
          </p>
          <ul className="divide-y rounded-md border bg-card">
            {items.map((item) => (
              <li key={item.decision_id} className="flex flex-wrap items-center justify-between gap-4 px-4 py-3.5">
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link href={`/decisions/${item.decision_id}`} className="font-mono text-xs text-primary underline underline-offset-2">
                      {item.decision_id}
                    </Link>
                    <span className="text-xs text-muted-foreground">{item.domain}</span>
                    <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium", ageStyle(item.days_without_outcome))}>
                      {item.days_without_outcome} days old
                    </span>
                  </div>
                  <p className="font-medium leading-snug">{item.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {item.authors}, decided {formatDate(item.date)}
                  </p>
                </div>
                <Button size="sm" variant="outline" asChild>
                  <Link href={`/decisions/${item.decision_id}/outcome`}>Record outcome</Link>
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
