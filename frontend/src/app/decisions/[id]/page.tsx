"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Check, Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/notice";
import { CitationChip } from "@/components/citations";
import { decisionsApi, type Decision, type Outcome } from "@/lib/api";
import { cn, formatDate, regretColor, regretLabel, statusColor } from "@/lib/utils";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Prose({ children }: { children: React.ReactNode }) {
  return <p className="max-w-[72ch] whitespace-pre-line text-[15px] leading-[1.7]">{children}</p>;
}

function OutcomeBlock({ outcome }: { outcome: Outcome }) {
  return (
    <article className="space-y-4 rounded-md border bg-card p-5">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className={cn("rounded px-2 py-0.5 text-sm font-medium", regretColor(outcome.regret_score))}>
          Regret {outcome.regret_score} of 5: {regretLabel(outcome.regret_score).toLowerCase()}
        </span>
        <span className={cn("text-sm font-medium", outcome.would_repeat ? "text-success" : "text-destructive")}>
          {outcome.would_repeat ? "Would repeat this decision" : "Would not repeat this decision"}
        </span>
        <span className="ml-auto text-xs text-muted-foreground">
          Recorded {formatDate(outcome.recorded_at)}
          {outcome.recorded_by ? ` by ${outcome.recorded_by}` : ""}
        </span>
      </header>

      <div className="space-y-4">
        <div>
          <h3 className="mb-1 text-sm font-semibold">What happened</h3>
          <Prose>{outcome.actual_results}</Prose>
        </div>
        {outcome.incidents && (
          <div>
            <h3 className="mb-1 text-sm font-semibold">Incidents</h3>
            <Prose>{outcome.incidents}</Prose>
          </div>
        )}
        <div>
          <h3 className="mb-1 text-sm font-semibold">Lessons</h3>
          <Prose>{outcome.lessons}</Prose>
        </div>
        {outcome.metrics && Object.keys(outcome.metrics).length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-semibold">Measured</h3>
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {Object.entries(outcome.metrics).map(([k, v]) => (
                <div key={k} className="rounded-md bg-muted px-3 py-2">
                  <dt className="text-xs text-muted-foreground">{k}</dt>
                  <dd className="text-sm font-medium">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </div>
    </article>
  );
}

export default function DecisionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [outcomes, setOutcomes] = useState<Outcome[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [exported, setExported] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const [dec, outs] = await Promise.all([decisionsApi.get(id), decisionsApi.outcomes(id)]);
      setDecision(dec);
      setOutcomes(outs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load this decision.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const handleExport = async () => {
    setActionError(null);
    try {
      const data = await decisionsApi.exportMarkdown(id);
      const url = URL.createObjectURL(new Blob([data.markdown], { type: "text/markdown" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${id}.md`;
      a.click();
      URL.revokeObjectURL(url);
      setExported(true);
      window.setTimeout(() => setExported(false), 2000);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Export failed.");
    }
  };

  const handleResync = async () => {
    setSyncing(true);
    setActionError(null);
    try {
      await decisionsApi.resync(id);
      await load();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Sync failed.");
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground" role="status">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Loading decision
      </div>
    );
  }

  if (error || !decision) {
    return (
      <div className="space-y-4">
        <Notice tone="error" title="Could not load this decision">{error ?? "Decision not found."}</Notice>
        <Button variant="outline" asChild>
          <Link href="/decisions">Back to decisions</Link>
        </Button>
      </div>
    );
  }

  const unsynced = !decision.memory_synced || outcomes.some((o) => !o.memory_synced);

  return (
    <div className="space-y-8">
      <Link href="/decisions" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" aria-hidden /> All decisions
      </Link>

      {unsynced && (
        <Notice tone="warning" title="Not fully retained in memory">
          <p>Briefings cannot use this record until it is retained. This usually means memory was unreachable when it was saved.</p>
          <Button type="button" size="sm" variant="outline" onClick={handleResync} disabled={syncing} className="mt-2 bg-background">
            {syncing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
            Retry sync
          </Button>
        </Notice>
      )}
      {actionError && <Notice tone="error">{actionError}</Notice>}

      <header className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl space-y-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm text-muted-foreground">{decision.decision_id}</span>
              <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium", statusColor(decision.status))}>{decision.status}</span>
            </div>
            <h1 className="text-2xl font-semibold leading-tight tracking-tight">{decision.title}</h1>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleExport}>
              {exported ? <Check className="mr-1.5 h-4 w-4" aria-hidden /> : <Download className="mr-1.5 h-4 w-4" aria-hidden />}
              {exported ? "Exported" : "Export markdown"}
            </Button>
            <Button size="sm" asChild>
              <Link href={`/decisions/${decision.decision_id}/outcome`}>Record outcome</Link>
            </Button>
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 border-y py-4 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-muted-foreground">Date</dt>
            <dd>{formatDate(decision.date)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Authors</dt>
            <dd>{decision.authors}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Domain</dt>
            <dd>{decision.domain}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Services</dt>
            <dd>{decision.services.length > 0 ? decision.services.join(", ") : "None listed"}</dd>
          </div>
        </dl>

        {decision.tags.length > 0 && (
          <ul className="flex flex-wrap gap-1.5" aria-label="Tags">
            {decision.tags.map((t) => (
              <li key={t} className="rounded bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">{t}</li>
            ))}
          </ul>
        )}
      </header>

      <div className="max-w-3xl space-y-7">
        <Section title="Context">
          <Prose>{decision.context}</Prose>
        </Section>

        {decision.forces && (
          <Section title="Forces and constraints">
            <Prose>{decision.forces}</Prose>
          </Section>
        )}

        {decision.options.length > 0 && (
          <Section title="Options considered">
            <ul className="divide-y rounded-md border bg-card text-sm">
              {decision.options.map((opt) => {
                const chosen = opt === decision.chosen_option;
                return (
                  <li key={opt} className={cn("flex items-center gap-2 px-3 py-2", chosen ? "font-medium" : "text-muted-foreground")}>
                    <span className="flex-1">{opt}</span>
                    {chosen && <span className="rounded bg-accent px-1.5 py-0.5 text-xs text-accent-foreground">Chosen</span>}
                  </li>
                );
              })}
            </ul>
          </Section>
        )}

        {!decision.options.includes(decision.chosen_option) && (
          <Section title="Chosen option">
            <Prose>{decision.chosen_option}</Prose>
          </Section>
        )}

        <Section title="Rationale">
          <Prose>{decision.rationale}</Prose>
        </Section>

        {decision.expected_outcomes && (
          <Section title="Expected outcomes">
            <Prose>{decision.expected_outcomes}</Prose>
          </Section>
        )}

        {decision.related_decisions.length > 0 && (
          <Section title="Related decisions">
            <div className="flex flex-wrap gap-2">
              {decision.related_decisions.map((rel) => (
                <CitationChip key={rel} id={rel} />
              ))}
            </div>
          </Section>
        )}
      </div>

      <section className="space-y-4 border-t pt-8" aria-labelledby="outcomes-heading">
        <h2 id="outcomes-heading" className="text-lg font-semibold tracking-tight">
          Outcomes ({outcomes.length})
        </h2>
        {outcomes.length === 0 ? (
          <div className="rounded-md border border-dashed p-6 text-sm">
            <p className="text-muted-foreground">
              No outcome recorded yet. Until one is, briefings that cite this decision can say what was decided but not how
              it turned out.
            </p>
            <Button variant="outline" asChild className="mt-4">
              <Link href={`/decisions/${decision.decision_id}/outcome`}>Record the first outcome</Link>
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {outcomes.map((o) => (
              <OutcomeBlock key={o.id} outcome={o} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
