"use client";

import * as React from "react";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface TokenInputProps {
  id?: string;
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  /** "chips" wraps values inline; "list" stacks them (for ordered items like options). */
  layout?: "chips" | "list";
  /** Return an error message to reject a value. */
  validate?: (value: string) => string | null;
}

/**
 * Add-and-remove list input. Enter or the add button commits a value; leaving the
 * field also commits it, so text typed but not confirmed is never silently dropped.
 */
export function TokenInput({
  id,
  label,
  values,
  onChange,
  placeholder,
  layout = "chips",
  validate,
}: TokenInputProps) {
  const [draft, setDraft] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  const commit = () => {
    const value = draft.trim();
    if (!value) return;
    const problem = validate?.(value) ?? null;
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    if (!values.includes(value)) onChange([...values, value]);
    setDraft("");
  };

  const remove = (idx: number) => onChange(values.filter((_, i) => i !== idx));

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input
          id={id}
          value={draft}
          placeholder={placeholder}
          aria-label={label}
          aria-invalid={error ? true : undefined}
          onChange={(e) => {
            setDraft(e.target.value);
            if (error) setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commit();
            }
          }}
          onBlur={commit}
        />
        <Button type="button" variant="outline" size="icon" onClick={commit} aria-label={`Add ${label.toLowerCase()}`}>
          <Plus className="h-4 w-4" />
        </Button>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}

      {values.length > 0 && layout === "chips" && (
        <ul className="flex flex-wrap gap-1.5">
          {values.map((v, i) => (
            <li
              key={v}
              className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs text-secondary-foreground"
            >
              {v}
              <button
                type="button"
                onClick={() => remove(i)}
                className="rounded-sm p-0.5 hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label={`Remove ${v}`}
              >
                <X className="h-3 w-3" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {values.length > 0 && layout === "list" && (
        <ul className="divide-y rounded-md border bg-card text-sm">
          {values.map((v, i) => (
            <li key={v} className="flex items-center gap-2 px-3 py-2">
              <span className="flex-1">{v}</span>
              <button
                type="button"
                onClick={() => remove(i)}
                className="rounded-sm p-0.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label={`Remove ${v}`}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
