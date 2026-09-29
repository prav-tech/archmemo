"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Notice } from "@/components/notice";
import { PageHeader } from "@/components/page-header";
import { TokenInput } from "@/components/token-input";
import { ApiError, decisionsApi, type DecisionInput } from "@/lib/api";
import { DECISION_ID_PATTERN } from "@/lib/utils";

function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export default function NewDecisionPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const [form, setForm] = useState<DecisionInput>({
    title: "",
    date: new Date().toISOString().split("T")[0],
    authors: "",
    domain: "",
    services: [],
    context: "",
    forces: "",
    options: [],
    chosen_option: "",
    rationale: "",
    expected_outcomes: "",
    tags: [],
    related_decisions: [],
    status: "active",
  });

  const set = <K extends keyof DecisionInput>(key: K, value: DecisionInput[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const dec = await decisionsApi.create({
        ...form,
        forces: form.forces?.trim() || undefined,
        expected_outcomes: form.expected_outcomes?.trim() || undefined,
      });
      router.push(`/decisions/${dec.decision_id}`);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("The decision could not be recorded."));
    } finally {
      setLoading(false);
    }
  };

  // A 503 means the decision row was saved but memory was unreachable; point at the repair.
  const savedId =
    error instanceof ApiError && error.status === 503 ? error.message.match(/DEC-\d{4}-\d{3}/)?.[0] : undefined;

  return (
    <div className="max-w-3xl space-y-8">
      <PageHeader
        title="Record decision"
        description="Decisions are retained in memory and recalled the next time a similar proposal is briefed. Add the outcome later to show what actually happened."
      />

      <form onSubmit={handleSubmit} className="space-y-10">
        <fieldset className="space-y-4">
          <legend className="mb-1 text-base font-semibold">Overview</legend>
          <Field id="title" label="Title">
            <Input id="title" required minLength={5} maxLength={200} value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="Adopt Kafka for inter-service event streaming" />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="date" label="Date">
              <Input id="date" type="date" required value={form.date} onChange={(e) => set("date", e.target.value)} />
            </Field>
            <Field id="status" label="Status">
              <Select id="status" className="w-full" value={form.status} onChange={(e) => set("status", e.target.value)}>
                <option value="active">Active</option>
                <option value="superseded">Superseded</option>
                <option value="deprecated">Deprecated</option>
              </Select>
            </Field>
            <Field id="domain" label="Domain" hint="Used as a recall filter, e.g. platform, data, security.">
              <Input id="domain" required minLength={2} value={form.domain} onChange={(e) => set("domain", e.target.value)} placeholder="platform" />
            </Field>
            <Field id="authors" label="Authors">
              <Input id="authors" required minLength={2} value={form.authors} onChange={(e) => set("authors", e.target.value)} placeholder="Jane Smith, Platform team" />
            </Field>
          </div>
          <Field id="services" label="Services affected" hint="Press Enter to add each one.">
            <TokenInput id="services" label="Service" values={form.services} onChange={(v) => set("services", v)} placeholder="payments-api" />
          </Field>
          <Field id="tags" label="Tags" hint="Technologies and themes, e.g. kafka, event-driven.">
            <TokenInput id="tags" label="Tag" values={form.tags} onChange={(v) => set("tags", v)} placeholder="kafka" />
          </Field>
        </fieldset>

        <fieldset className="space-y-4">
          <legend className="mb-1 text-base font-semibold">Decision</legend>
          <Field id="context" label="Context and problem" hint="At least 20 characters.">
            <Textarea id="context" required minLength={20} rows={4} value={form.context} onChange={(e) => set("context", e.target.value)} placeholder="What situation led to this decision?" />
          </Field>
          <Field id="forces" label="Forces and constraints (optional)">
            <Textarea id="forces" rows={3} value={form.forces ?? ""} onChange={(e) => set("forces", e.target.value)} placeholder="Deadlines, team skills, compliance, cost, existing systems." />
          </Field>
          <Field id="options" label="Options considered" hint="Add each alternative, including the one you chose.">
            <TokenInput id="options" label="Option" layout="list" values={form.options} onChange={(v) => set("options", v)} placeholder="Managed Kafka" />
          </Field>
          <Field id="chosen_option" label="Chosen option">
            <Input id="chosen_option" required minLength={2} list="option-suggestions" value={form.chosen_option} onChange={(e) => set("chosen_option", e.target.value)} placeholder="Pick from the options above or type one" />
            <datalist id="option-suggestions">
              {form.options.map((o) => (
                <option key={o} value={o} />
              ))}
            </datalist>
          </Field>
          <Field id="rationale" label="Rationale" hint="Why this option over the alternatives. At least 20 characters.">
            <Textarea id="rationale" required minLength={20} rows={4} value={form.rationale} onChange={(e) => set("rationale", e.target.value)} />
          </Field>
          <Field id="expected_outcomes" label="Expected outcomes (optional)" hint="What you expect to measure later. This is what the outcome gets compared against.">
            <Textarea id="expected_outcomes" rows={3} value={form.expected_outcomes ?? ""} onChange={(e) => set("expected_outcomes", e.target.value)} />
          </Field>
          <Field id="related" label="Related decisions (optional)">
            <TokenInput
              id="related"
              label="Decision ID"
              values={form.related_decisions}
              onChange={(v) => set("related_decisions", v)}
              placeholder="DEC-2024-003"
              validate={(v) => (DECISION_ID_PATTERN.test(v) ? null : "Use the format DEC-YYYY-NNN.")}
            />
          </Field>
        </fieldset>

        {error && (
          <Notice tone={savedId ? "warning" : "error"} title={savedId ? "Saved, but not retained in memory" : "Could not record the decision"}>
            <p>{error.message}</p>
            {savedId && (
              <p>
                <Link href={`/decisions/${savedId}`} className="underline underline-offset-2">
                  Open {savedId}
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
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> Recording decision
              </>
            ) : (
              "Record decision"
            )}
          </Button>
          <Button type="button" variant="ghost" asChild>
            <Link href="/decisions">Cancel</Link>
          </Button>
        </div>
      </form>
    </div>
  );
}
