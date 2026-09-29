"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ChevronDown, Loader2 } from "lucide-react";
import { Notice } from "@/components/notice";
import { PageHeader } from "@/components/page-header";
import { BriefingMarkdown, CitationChip, type CitationContext } from "@/components/citations";
import { auditApi, type AuditEntry } from "@/lib/api";
import { cn, formatDateTime } from "@/lib/utils";

function AuditDetail({ entry }: { entry: AuditEntry }) {
  const ctx = useMemo<CitationContext>(
    () => ({
      verified: new Set(entry.cited_decision_ids),
      unverified: new Set(entry.unverified_citation_ids),
      titles: {},
    }),
    [entry]
  );

  return (
    <div className="space-y-6 border-t px-4 py-5">
      <section className="space-y-1">
        <h3 className="text-sm font-semibold">Proposal</h3>
        <p className="max-w-[72ch] whitespace-pre-line text-sm leading-relaxed text-muted-foreground">{entry.proposal_excerpt}</p>
      </section>

      {entry.filters && (entry.filters.domain || (entry.filters.services && entry.filters.services.length > 0)) && (
        <section className="space-y-1">
          <h3 className="text-sm font-semibold">Recall filters</h3>
          <p className="text-sm text-muted-foreground">
            {entry.filters.domain ? `Domain: ${entry.filters.domain}. ` : ""}
            {entry.filters.services && entry.filters.services.length > 0 ? `Services: ${entry.filters.services.join(", ")}.` : ""}
          </p>
        </section>
      )}

      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Decisions recalled ({entry.recalled_decision_ids.length})</h3>
        {entry.recalled_decision_ids.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing citable was recalled, so the model was not called.</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {entry.recalled_decision_ids.map((id) => (
              <li key={id} className="flex items-center gap-1.5">
                <CitationChip id={id} />
                <span className="text-xs text-muted-foreground">{entry.cited_decision_ids.includes(id) ? "cited" : "not cited"}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {entry.unverified_citation_ids.length > 0 && (
        <Notice tone="warning" title="Unverified citations rejected">
          The model cited {entry.unverified_citation_ids.join(", ")}, which {entry.unverified_citation_ids.length === 1 ? "was" : "were"} not in the
          recalled memory.
        </Notice>
      )}

      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Memories recalled ({entry.recalled_memories.length})</h3>
        {entry.recalled_memories.length === 0 ? (
          <p className="text-sm text-muted-foreground">None.</p>
        ) : (
          <ul className="divide-y rounded-md border bg-background">
            {entry.recalled_memories.map((m, i) => (
              <li key={`${m.memory_id}-${i}`} className="space-y-1.5 px-3 py-2.5">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  {m.decision_id ? <CitationChip id={m.decision_id} /> : <span className="rounded bg-warning-soft px-1.5 py-0.5 text-warning">Unattributed</span>}
                  <span className="rounded bg-secondary px-1.5 py-0.5 text-secondary-foreground">{m.kind}</span>
                  <span>relevance {m.score.toFixed(2)}</span>
                </div>
                <p className="text-sm leading-relaxed">{m.text}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Briefing returned</h3>
        <div className="rounded-md border bg-background p-4">
          <BriefingMarkdown markdown={entry.briefing_text} ctx={ctx} />
        </div>
      </section>
    </div>
  );
}

function AuditList() {
  const searchParams = useSearchParams();
  const openParam = Number(searchParams.get("open"));
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(Number.isInteger(openParam) && openParam > 0 ? openParam : null);

  useEffect(() => {
    auditApi
      .list()
      .then(setEntries)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Scroll a deep-linked entry (from a briefing) into view once the list has loaded.
  useEffect(() => {
    if (!loading && openId !== null) {
      document.getElementById(`audit-${openId}`)?.scrollIntoView({ block: "start" });
    }
    // Only on first load; later toggles should not jump the page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit log"
        description="Every briefing, with the memories the agent was given, the decisions it cited, and any citation it made that memory could not support."
      />

      {loading && (
        <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Loading audit log
        </div>
      )}
      {error && <Notice tone="error" title="Could not load the audit log">{error}</Notice>}
      {!loading && !error && entries.length === 0 && (
        <Notice tone="info" title="No briefings yet">
          Generate a briefing and it will be recorded here.
        </Notice>
      )}

      <ul className="space-y-3">
        {entries.map((entry) => {
          const open = openId === entry.id;
          const panelId = `audit-panel-${entry.id}`;
          return (
            <li key={entry.id} id={`audit-${entry.id}`} className="scroll-mt-24 rounded-md border bg-card">
              <button
                type="button"
                aria-expanded={open}
                aria-controls={panelId}
                onClick={() => setOpenId(open ? null : entry.id)}
                className="flex w-full items-start gap-4 px-4 py-3.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span className="font-mono">#{entry.id}</span>
                    <span>{formatDateTime(entry.requested_at)}</span>
                    {entry.requested_by && <span>{entry.requested_by}</span>}
                  </div>
                  <p className="line-clamp-2 text-sm">{entry.proposal_excerpt}</p>
                  <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
                    <span className="rounded bg-secondary px-1.5 py-0.5 text-secondary-foreground">
                      {entry.recalled_memory_count} {entry.recalled_memory_count === 1 ? "memory" : "memories"} from {entry.recalled_decision_ids.length}{" "}
                      {entry.recalled_decision_ids.length === 1 ? "decision" : "decisions"}
                    </span>
                    <span className="rounded bg-accent px-1.5 py-0.5 text-accent-foreground">{entry.cited_decision_ids.length} cited</span>
                    {entry.unverified_citation_ids.length > 0 && (
                      <span className="rounded bg-warning-soft px-1.5 py-0.5 font-medium text-warning">
                        {entry.unverified_citation_ids.length} unverified
                      </span>
                    )}
                  </div>
                </div>
                <ChevronDown className={cn("mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} aria-hidden />
              </button>
              {open && (
                <div id={panelId}>
                  <AuditDetail entry={entry} />
                  <p className="border-t px-4 py-2.5 text-xs text-muted-foreground">
                    {entry.model_used}
                    {entry.latency_ms !== null ? `, ${(entry.latency_ms / 1000).toFixed(1)}s` : ""}
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function AuditPage() {
  // useSearchParams needs a Suspense boundary for static rendering.
  return (
    <Suspense fallback={null}>
      <AuditList />
    </Suspense>
  );
}
