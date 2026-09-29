import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

export function formatDateTime(iso: string): string {
  // The API returns naive UTC timestamps for some fields; treat them as UTC.
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(iso);
  const d = new Date(hasZone ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function regretLabel(score: number): string {
  const labels: Record<number, string> = {
    1: "No regret",
    2: "Minor regret",
    3: "Moderate regret",
    4: "Significant regret",
    5: "Strong regret",
  };
  return labels[score] ?? "Unknown";
}

export function regretColor(score: number): string {
  if (score <= 2) return "bg-success-soft text-success";
  if (score === 3) return "bg-warning-soft text-warning";
  return "bg-destructive/10 text-destructive";
}

export function statusColor(status: string): string {
  switch (status) {
    case "active":
      return "bg-success-soft text-success";
    case "superseded":
      return "bg-secondary text-secondary-foreground";
    case "deprecated":
      return "bg-destructive/10 text-destructive";
    default:
      return "bg-secondary text-secondary-foreground";
  }
}

/** Decision IDs look like DEC-2024-001. */
export const DECISION_ID_PATTERN = /^DEC-\d{4}-\d{3}$/;
