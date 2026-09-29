"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Loader2, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Notice } from "@/components/notice";
import { PageHeader } from "@/components/page-header";
import { ApiError, decisionsApi, type Decision } from "@/lib/api";
import { cn, regretLabel } from "@/lib/utils";

interface MetricRow {
  key: string;
  value: string;
}

/** Store numbers and booleans as such so recalled outcomes read as real measurements. */
function parseMetricValue(raw: string): unknown {
  const v = raw.trim();
  if (v === "true") return true;
  if (v === "false") return false;
  if (v !== "" && !Number.isNaN(Number(v))) return Number(v);
  return v;
}

function Segmented<T extends string | number | boolean>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex overflow-hidden rounded-md border border-input bg-card">
      {options.map((o) => {
        const selected = o.value === value;
        return (
          <button
            key={String(o.value)}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(o.value)}
            className={cn(
              "min-w-[3rem] border-r border-input px-4 py-2 text-sm last:border-r-0 focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              selected ? "bg-primary font-medium text-primary-foreground" : "hover:bg-muted"
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export default function AddOutcomePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const [actualResults, setActualResults] = useState("");
  const [regret, setRegret] = useState(2);
  const [wouldRepeat, setWouldRepeat] = useState(true);
  const [lessons, setLessons] = useState("");
  const [incidents, setIncidents] = useState("");
  const [recordedBy, setRecordedBy] = useState("");
  const [metrics, setMetrics] = useState<MetricRow[]>([{ key: "", value: "" }]);

  useEffect(() => {
    if (!id) return;
    decisionsApi.get(id).then(setDecision).catch(() => setDecision(null));
  }, [id]);

  const updateMetric = (i: number, patch: Partial<MetricRow>) =>
    setMetrics((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const metricEntries = metrics.filter((m) => m.key.trim()).map((m) => [m.key.trim(), parseMetricValue(m.value)] as const);
    try {
      await decisionsApi.addOutcome(id, {
        actual_results: actualResults.trim(),
        regret_score: regret,
        lessons: lessons.trim(),
        would_repeat: wouldRepeat,
        metrics: metricEntries.length > 0 ? Object.fromEntries(metricEntries) : undefined,
        incidents: incidents.trim() || undefined,
        recorded_by: recordedBy.trim() || undefined,
      });
      router.push(`/decisions/${id}`);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("The outcome could not be recorded."));
    } finally {
      setLoading(false);
    }
  };

  // 503 = outcome row saved, memory unreachable. The decision page has Retry sync.
  const savedButUnsynced = error instanceof ApiError && error.status === 503;

  return (
    <div className="max-w-3xl space-y-8">
      <PageHeader
        title="Record outcome"
        description={
          <>
            For <span className="font-mono">{id}</span>
            {decision ? `: ${decision.title}` : ""}. Once retained, future briefings that recall this decision will include
            what actually happened.
          </>
        }
      />

      {decision?.expected_outcomes && (
        <div className="rounded-md border bg-card p-4 text-sm">
          <p className="mb-1 font-semibold">What was expected</p>
          <p className="max-w-[72ch] whitespace-pre-line leading-relaxed text-muted-foreground">{decision.expected_outcomes}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-8">
        <div className="space-y-1.5">
          <Label htmlFor="actual_results">What actually happened</Label>
          <Textarea
            id="actual_results"
            required
            minLength={20}
            rows={4}
            value={actualResults}
            onChange={(e) => setActualResults(e.target.value)}
            placeholder="Results against what was expected. Include numbers where you have them."
          />
          <p className="text-xs text-muted-foreground">At least 20 characters.</p>
        </div>

        <div className="space-y-2">
          <Label>Metrics (optional)</Label>
          <p className="text-xs text-muted-foreground">Named measurements, such as p99_latency_ms = 140 or infra_cost_delta_pct = -18.</p>
          <div className="space-y-2">
            {metrics.map((m, i) => (
              <div key={i} className="flex gap-2">
                <Input aria-label={`Metric ${i + 1} name`} value={m.key} onChange={(e) => updateMetric(i, { key: e.target.value })} placeholder="Metric name" />
                <Input aria-label={`Metric ${i + 1} value`} value={m.value} onChange={(e) => updateMetric(i, { value: e.target.value })} placeholder="Value" />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove metric ${i + 1}`}
                  onClick={() => setMetrics((rows) => (rows.length === 1 ? [{ key: "", value: "" }] : rows.filter((_, idx) => idx !== i)))}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => setMetrics((rows) => [...rows, { key: "", value: "" }])}>
            <Plus className="mr-1.5 h-4 w-4" aria-hidden /> Add metric
          </Button>
        </div>

        <div className="space-y-2">
          <Label>Regret</Label>
          <div>
            <Segmented
              label="Regret score"
              value={regret}
              onChange={setRegret}
              options={[1, 2, 3, 4, 5].map((n) => ({ value: n, label: String(n) }))}
            />
          </div>
          <p className="text-xs text-muted-foreground" aria-live="polite">
            {regret} of 5: {regretLabel(regret).toLowerCase()}. 1 means no regret, 5 means strong regret.
          </p>
        </div>

        <div className="space-y-2">
          <Label>Would you make this decision again?</Label>
          <div>
            <Segmented
              label="Would repeat"
              value={wouldRepeat}
              onChange={setWouldRepeat}
              options={[
                { value: true, label: "Yes" },
                { value: false, label: "No" },
              ]}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="lessons">Lessons</Label>
          <Textarea
            id="lessons"
            required
            minLength={10}
            rows={3}
            value={lessons}
            onChange={(e) => setLessons(e.target.value)}
            placeholder="What would you do differently, and what should the next team know?"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="incidents">Incidents (optional)</Label>
          <Textarea id="incidents" rows={2} value={incidents} onChange={(e) => setIncidents(e.target.value)} placeholder="Outages, rollbacks, or unexpected issues." />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="recorded_by">Recorded by (optional)</Label>
          <Input id="recorded_by" value={recordedBy} onChange={(e) => setRecordedBy(e.target.value)} placeholder="Jane Smith" />
        </div>

        {error && (
          <Notice tone={savedButUnsynced ? "warning" : "error"} title={savedButUnsynced ? "Saved, but not retained in memory" : "Could not record the outcome"}>
            <p>{error.message}</p>
            {savedButUnsynced && (
              <p>
                <Link href={`/decisions/${id}`} className="underline underline-offset-2">
                  Open {id}
                </Link>{" "}
                and use Retry sync once memory is reachable.
              </p>
            )}
          </Notice>
        )}

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> Recording outcome
              </>
            ) : (
              "Record outcome"
            )}
          </Button>
          <Button type="button" variant="ghost" asChild>
            <Link href={`/decisions/${id}`}>Cancel</Link>
          </Button>
        </div>
      </form>
    </div>
  );
}
