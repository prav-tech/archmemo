"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Notice } from "@/components/notice";
import { PageHeader } from "@/components/page-header";
import { decisionsApi, type Decision } from "@/lib/api";
import { cn, formatDate, statusColor } from "@/lib/utils";

export default function DecisionsPage() {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [domain, setDomain] = useState("");
  const [status, setStatus] = useState("");
  const [outcome, setOutcome] = useState("");

  useEffect(() => {
    decisionsApi
      .list()
      .then(setDecisions)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const domains = useMemo(() => Array.from(new Set(decisions.map((d) => d.domain))).sort(), [decisions]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return decisions.filter((d) => {
      if (domain && d.domain !== domain) return false;
      if (status && d.status !== status) return false;
      if (outcome === "with" && d.outcome_count === 0) return false;
      if (outcome === "without" && d.outcome_count > 0) return false;
      if (!q) return true;
      return (
        d.title.toLowerCase().includes(q) ||
        d.decision_id.toLowerCase().includes(q) ||
        d.domain.toLowerCase().includes(q) ||
        d.services.some((s) => s.toLowerCase().includes(q)) ||
        d.tags.some((t) => t.toLowerCase().includes(q))
      );
    });
  }, [decisions, search, domain, status, outcome]);

  const filtersActive = Boolean(search || domain || status || outcome);
  const clearFilters = () => {
    setSearch("");
    setDomain("");
    setStatus("");
    setOutcome("");
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Decisions"
        description={
          loading || error
            ? "Every architecture decision in memory."
            : `${decisions.length} ${decisions.length === 1 ? "decision" : "decisions"} in memory, ${
                decisions.filter((d) => d.outcome_count > 0).length
              } with a recorded outcome.`
        }
        actions={
          <Button asChild>
            <Link href="/decisions/new">Record decision</Link>
          </Button>
        }
      />

      <div className="flex flex-wrap gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            aria-label="Search decisions"
            placeholder="Search title, ID, service, or tag"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-card pl-9"
          />
        </div>
        <Select aria-label="Filter by domain" value={domain} onChange={(e) => setDomain(e.target.value)}>
          <option value="">All domains</option>
          {domains.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </Select>
        <Select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>
          <option value="active">Active</option>
          <option value="superseded">Superseded</option>
          <option value="deprecated">Deprecated</option>
        </Select>
        <Select aria-label="Filter by outcome" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
          <option value="">With or without outcome</option>
          <option value="with">Has an outcome</option>
          <option value="without">No outcome yet</option>
        </Select>
      </div>

      {loading && (
        <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Loading decisions
        </div>
      )}

      {error && <Notice tone="error" title="Could not load decisions">{error}</Notice>}

      {!loading && !error && decisions.length === 0 && (
        <Notice tone="info" title="Memory is empty">
          Record the first decision, or load sample history by running <code className="font-mono">python scripts/seed.py</code> in
          the backend folder.
        </Notice>
      )}

      {!loading && !error && decisions.length > 0 && filtered.length === 0 && (
        <div className="py-10 text-center text-sm text-muted-foreground">
          No decisions match these filters.{" "}
          {filtersActive && (
            <button type="button" onClick={clearFilters} className="text-primary underline underline-offset-2">
              Clear filters
            </button>
          )}
        </div>
      )}

      {filtered.length > 0 && (
        <ul className="divide-y rounded-md border bg-card">
          {filtered.map((d) => (
            <li key={d.decision_id}>
              <Link
                href={`/decisions/${d.decision_id}`}
                className="grid gap-x-6 gap-y-1 px-4 py-3.5 transition-colors hover:bg-muted/60 sm:grid-cols-[minmax(0,1fr)_auto]"
              >
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-muted-foreground">{d.decision_id}</span>
                    <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium", statusColor(d.status))}>{d.status}</span>
                    <span className="text-xs text-muted-foreground">{d.domain}</span>
                    {!d.memory_synced && (
                      <span
                        className="inline-flex items-center gap-1 text-xs text-warning"
                        title="Not retained in memory. Open the decision to retry."
                      >
                        <AlertTriangle className="h-3.5 w-3.5" aria-hidden /> Not in memory
                      </span>
                    )}
                  </div>
                  <p className="font-medium leading-snug">{d.title}</p>
                  <p className="line-clamp-1 text-sm text-muted-foreground">{d.context}</p>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground sm:flex-col sm:items-end sm:justify-center sm:gap-1">
                  <span>{formatDate(d.date)}</span>
                  {d.outcome_count > 0 ? (
                    <span className="rounded bg-success-soft px-1.5 py-0.5 font-medium text-success">
                      {d.outcome_count} {d.outcome_count === 1 ? "outcome" : "outcomes"}
                    </span>
                  ) : (
                    <span>No outcome yet</span>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
