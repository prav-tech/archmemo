"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Check, ChevronDown, Copy, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Notice } from "@/components/notice";
import { PageHeader } from "@/components/page-header";
import { BriefingMarkdown, CitationChip, type CitationContext } from "@/components/citations";
import { briefingApi, type BriefingResponse, type RecalledDecision } from "@/lib/api";
import { cn } from "@/lib/utils";

/** The backend rejects proposals shorter than this. */
const MIN_PROPOSAL_LENGTH = 50;

const EXAMPLE_PROPOSAL = `RFC: Migrate Payment Service to GraphQL

We propose migrating our payment service API from REST to GraphQL to provide partners with flexible query capabilities and reduce over-fetching. The service currently handles 8,000 TPS peak load and has a P99 latency SLA of 150ms.

The GraphQL schema would expose payment intents, transaction history, and refund operations. We would use Strawberry Python for schema definition.

Key concerns:
- Performance impact at high TPS
- Partner migration path from existing REST
- Schema versioning and deprecation strategy

Proposed timeline: 6 months for full migration.`;

/** How much of a decision's history the agent actually had: the before/after signal. */
function outcomeStatus(d: RecalledDecision): { label: string; className: string } {
  if (d.has_outcome_memory) return { label: "Outcome recalled", className: "bg-success-soft text-success" };
  if (d.outcomes_on_record > 0)
    return { label: "Outcome on record, not recalled", className: "bg-warning-soft text-warning" };
  return { label: "No outcome recorded", className: "bg-secondary text-muted-foreground" };
}

export default function BriefingPage() {
  const [proposal, setProposal] = useState("");
  const [domain, setDomain] = useState("");
  const [servicesText, setServicesText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BriefingResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);

  const trimmedLength = proposal.trim().length;
  const tooShort = trimmedLength < MIN_PROPOSAL_LENGTH;

  useEffect(() => {
    if (result) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [result]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (tooShort || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const services = servicesText.split(",").map((s) => s.trim()).filter(Boolean);
    try {
      setResult(
        await briefingApi.generate({
          proposal: proposal.trim(),
          domain: domain.trim() || undefined,
          services: services.length > 0 ? services : undefined,
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "The briefing could not be generated.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.briefing);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Could not copy to the clipboard. Select the briefing text and copy it manually.");
    }
  };

  // Lets the markdown renderer link verified IDs and flag unverified ones.
  const citationCtx = useMemo<CitationContext | undefined>(() => {
    if (!result) return undefined;
    return {
      verified: new Set(result.cited_decisions.filter((c) => c.verified).map((c) => c.decision_id)),
      unverified: new Set(result.unverified_citations),
      titles: Object.fromEntries(
        [...result.recalled_decisions, ...result.cited_decisions].map((d) => [d.decision_id, d.title])
      ),
    };
  }, [result]);

  const noMemory = result !== null && result.recalled_decisions.length === 0;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Proposal briefing"
        description="Paste an RFC or proposal. The agent recalls related past decisions and their recorded outcomes from memory, and every claim in the briefing cites a decision ID."
      />

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <div className="flex items-baseline justify-between gap-4">
            <Label htmlFor="proposal">Proposal</Label>
            <button
              type="button"
              onClick={() => setProposal(EXAMPLE_PROPOSAL)}
              className="text-xs text-primary underline underline-offset-2"
            >
              Use an example RFC
            </button>
          </div>
          <Textarea
            id="proposal"
            value={proposal}
            onChange={(e) => setProposal(e.target.value)}
            placeholder="Paste the RFC or architectural proposal here."
            className="min-h-[220px] bg-card text-sm leading-relaxed"
            aria-describedby="proposal-hint"
          />
          <p id="proposal-hint" className="text-xs text-muted-foreground">
            {tooShort
              ? `Add at least ${MIN_PROPOSAL_LENGTH - trimmedLength} more characters so there is enough to match against memory.`
              : "Ready to brief."}
          </p>
        </div>

        <details className="group rounded-md border bg-card">
          <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-2.5 text-sm font-medium">
            Narrow what is recalled
            <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
          </summary>
          <div className="grid gap-4 border-t px-4 py-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="domain">Domain</Label>
              <Input id="domain" value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="e.g. data" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="services">Services</Label>
              <Input
                id="services"
                value={servicesText}
                onChange={(e) => setServicesText(e.target.value)}
                placeholder="Comma-separated, e.g. payments, ledger"
              />
            </div>
            <p className="text-xs text-muted-foreground sm:col-span-2">
              Filters restrict recall to decisions with a matching domain or service. Leave them empty to search all
              of memory.
            </p>
          </div>
        </details>

        <Button type="submit" disabled={loading || tooShort}>
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> Generating briefing
            </>
          ) : (
            "Generate briefing"
          )}
        </Button>
      </form>

      {loading && (
        <div className="space-y-3" role="status" aria-live="polite">
          <p className="text-sm text-muted-foreground">Recalling related decisions from memory, then writing the briefing.</p>
          <div className="space-y-2" aria-hidden>
            {[92, 100, 78, 96, 64].map((w, i) => (
              <div key={i} className="h-3 animate-pulse rounded bg-muted" style={{ width: `${w}%` }} />
            ))}
          </div>
        </div>
      )}

      {error && <Notice tone="error" title="Briefing failed">{error}</Notice>}

      {result && (
        <div ref={resultRef} className="grid scroll-mt-24 gap-10 lg:grid-cols-[minmax(0,1fr)_320px]">
          <section aria-labelledby="briefing-heading" className="min-w-0 space-y-4">
            <div className="flex items-center justify-between gap-4 border-b pb-3">
              <h2 id="briefing-heading" className="text-lg font-semibold tracking-tight">
                Briefing
              </h2>
              <Button type="button" variant="outline" size="sm" onClick={handleCopy}>
                {copied ? <Check className="mr-1.5 h-4 w-4" aria-hidden /> : <Copy className="mr-1.5 h-4 w-4" aria-hidden />}
                {copied ? "Copied" : "Copy markdown"}
              </Button>
            </div>

            {noMemory && (
              <Notice tone="info" title="No related decisions in memory">
                The language model was not called, so nothing here is drawn from general knowledge. Record decisions and
                their outcomes to give future briefings something to cite.
              </Notice>
            )}

            {result.unverified_citations.length > 0 && (
              <Notice tone="warning" title="Some citations are not supported by memory">
                The model cited {result.unverified_citations.join(", ")}, which {result.unverified_citations.length === 1 ? "was" : "were"} not
                recalled. They are marked in the text below. Do not rely on them.
              </Notice>
            )}

            <BriefingMarkdown markdown={result.briefing} ctx={citationCtx} />
          </section>

          <aside aria-labelledby="memory-heading" className="space-y-6">
            <div>
              <h2 id="memory-heading" className="text-base font-semibold tracking-tight">
                Memory used
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {result.recalled_memory_count} {result.recalled_memory_count === 1 ? "memory" : "memories"} from{" "}
                {result.recalled_decisions.length} {result.recalled_decisions.length === 1 ? "decision" : "decisions"};{" "}
                {result.recalled_decisions.filter((d) => d.has_outcome_memory).length} with a recorded outcome.
              </p>
            </div>

            {result.recalled_decisions.length > 0 &&
              result.recalled_decisions.every((d) => !d.has_outcome_memory) && (
                <Notice tone="info">
                  No recalled decision includes an outcome, so this briefing says what was decided but not how it turned
                  out. Recording outcomes is what makes the next briefing stronger.
                </Notice>
              )}

            <ul className="divide-y rounded-md border bg-card">
              {result.recalled_decisions.map((d) => {
                const status = outcomeStatus(d);
                const cited = citationCtx?.verified.has(d.decision_id) ?? false;
                return (
                  <li key={d.decision_id} className="space-y-2 px-3 py-3">
                    <div className="flex items-center justify-between gap-2">
                      <CitationChip id={d.decision_id} title={d.title} />
                      {cited && <span className="text-xs text-muted-foreground">Cited</span>}
                    </div>
                    {d.title && <p className="text-sm leading-snug">{d.title}</p>}
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium", status.className)}>{status.label}</span>
                      {d.outcomes_on_record === 0 && (
                        <Link href={`/decisions/${d.decision_id}/outcome`} className="text-xs text-primary underline underline-offset-2">
                          Record outcome
                        </Link>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>

            <dl className="space-y-1.5 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Model</dt>
                <dd className="text-right">{result.model_used}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Time</dt>
                <dd>{(result.latency_ms / 1000).toFixed(1)}s</dd>
              </div>
            </dl>

            {result.audit_id !== null && (
              <Link
                href={`/audit?open=${result.audit_id}`}
                className="inline-block text-sm text-primary underline underline-offset-2"
              >
                Open audit entry #{result.audit_id}
              </Link>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
