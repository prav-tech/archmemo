/**
 * API client for the ArchMemory FastAPI backend.
 * All fetch calls go through Next.js rewrites (/api/* -> backend).
 */

export const API_BASE = "/api";

/** Error with the HTTP status, so pages can react to e.g. 503 (memory unavailable). */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Called when a data route answers 401, i.e. the session expired or was revoked.
 * The auth provider registers this so the app can drop back to the sign-in screen.
 */
let unauthorizedHandler: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  unauthorizedHandler = fn;
}

/** A 401 from these is an expected answer (wrong password, not signed in yet), not an expiry. */
const AUTH_PATHS = new Set(["/auth/login", "/auth/logout", "/auth/me"]);

/** FastAPI returns `detail` as a string, or as a list of validation errors. */
function formatDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (d && typeof d === "object") {
          const item = d as { loc?: unknown[]; msg?: string };
          const field = Array.isArray(item.loc)
            ? item.loc.filter((p) => p !== "body").join(".")
            : "";
          const msg = item.msg ?? "invalid value";
          return field ? `${field}: ${msg}` : msg;
        }
        return String(d);
      })
      .join("; ");
  }
  return fallback;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...options,
      // The session is an httpOnly cookie; it is only ever sent to our own origin.
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...options?.headers },
    });
  } catch {
    throw new ApiError("Could not reach the ArchMemory API. Check that the backend is running.", 0);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const fallback =
      res.status >= 500 && body === null
        ? "The API is not responding. Check that the backend is running."
        : res.statusText || `Request failed (${res.status})`;
    if (res.status === 401 && !AUTH_PATHS.has(path)) unauthorizedHandler?.();
    // Unexpected server errors carry a reference that matches the API log line.
    const ref = typeof body?.request_id === "string" ? ` (reference ${body.request_id})` : "";
    throw new ApiError(`${formatDetail(body?.detail, fallback)}${ref}`, res.status);
  }
  return res.json();
}

// ---- Types ----

export interface Decision {
  decision_id: string;
  title: string;
  date: string;
  authors: string;
  domain: string;
  services: string[];
  status: string;
  context: string;
  forces: string | null;
  options: string[];
  chosen_option: string;
  rationale: string;
  expected_outcomes: string | null;
  tags: string[];
  related_decisions: string[];
  created_at: string;
  updated_at: string;
  outcome_count: number;
  memory_synced: boolean;
}

/** Payload for POST /decisions. */
export interface DecisionInput {
  title: string;
  date: string;
  authors: string;
  domain: string;
  services: string[];
  context: string;
  forces?: string;
  options: string[];
  chosen_option: string;
  rationale: string;
  expected_outcomes?: string;
  tags: string[];
  related_decisions: string[];
  status: string;
}

export interface Outcome {
  id: number;
  decision_id: string;
  actual_results: string;
  regret_score: number;
  lessons: string;
  would_repeat: boolean;
  metrics: Record<string, unknown> | null;
  incidents: string | null;
  recorded_at: string;
  recorded_by: string | null;
  memory_synced: boolean;
}

/** Payload for POST /decisions/{id}/outcomes. */
export interface OutcomeInput {
  actual_results: string;
  regret_score: number;
  lessons: string;
  would_repeat: boolean;
  metrics?: Record<string, unknown>;
  incidents?: string;
  recorded_by?: string;
}

export interface CitedDecision {
  decision_id: string;
  title: string | null;
  relevance_excerpt: string;
  /** false => the model cited an ID that was NOT in recalled memory */
  verified: boolean;
}

export interface RecalledDecision {
  decision_id: string;
  title: string | null;
  /** an outcome fact was recalled and shown to the model */
  has_outcome_memory: boolean;
  /** outcomes stored in SQL (may exceed what was recalled) */
  outcomes_on_record: number;
}

export interface BriefingRequest {
  proposal: string;
  top_k?: number;
  domain?: string;
  services?: string[];
  requested_by?: string;
}

export interface BriefingResponse {
  briefing: string;
  cited_decisions: CitedDecision[];
  unverified_citations: string[];
  recalled_decisions: RecalledDecision[];
  recalled_memory_count: number;
  model_used: string;
  latency_ms: number;
  audit_id: number | null;
}

export interface AuditEntry {
  id: number;
  proposal_excerpt: string;
  recalled_decision_ids: string[];
  recalled_memory_count: number;
  recalled_memories: {
    memory_id: string;
    decision_id: string | null;
    kind: string;
    score: number;
    text: string;
  }[];
  cited_decision_ids: string[];
  unverified_citation_ids: string[];
  filters: { domain?: string | null; services?: string[] | null } | null;
  briefing_text: string;
  model_used: string;
  requested_at: string;
  requested_by: string | null;
  latency_ms: number | null;
}

export interface MissingOutcomeItem {
  decision_id: string;
  title: string;
  date: string;
  domain: string;
  authors: string;
  days_without_outcome: number;
}

export interface SessionInfo {
  username: string;
  /** false when the server runs with AUTH_ENABLED=false (no sign-in, no sign-out) */
  auth_enabled: boolean;
}

// ---- API functions ----

export const authApi = {
  /** The response also carries the token; the UI deliberately never reads it. */
  login: (username: string, password: string) =>
    apiFetch<SessionInfo>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  logout: () => apiFetch<{ ok: boolean }>("/auth/logout", { method: "POST" }),

  me: () => apiFetch<SessionInfo>("/auth/me"),
};

export const decisionsApi = {
  list: (params?: { domain?: string; status?: string; tag?: string }) => {
    const q = new URLSearchParams();
    if (params?.domain) q.set("domain", params.domain);
    if (params?.status) q.set("status", params.status);
    if (params?.tag) q.set("tag", params.tag);
    return apiFetch<Decision[]>(`/decisions${q.toString() ? `?${q}` : ""}`);
  },

  get: (id: string) => apiFetch<Decision>(`/decisions/${id}`),

  create: (data: DecisionInput) =>
    apiFetch<Decision>("/decisions", { method: "POST", body: JSON.stringify(data) }),

  outcomes: (id: string) => apiFetch<Outcome[]>(`/decisions/${id}/outcomes`),

  addOutcome: (id: string, data: OutcomeInput) =>
    apiFetch<Outcome>(`/decisions/${id}/outcomes`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  resync: (id: string) =>
    apiFetch<{ decision_id: string; decision_synced: boolean; outcomes_synced: number }>(
      `/decisions/${id}/resync`,
      { method: "POST" }
    ),

  exportMarkdown: (id: string) =>
    apiFetch<{ decision_id: string; markdown: string }>(`/decisions/${id}/export`),

  missingOutcomes: () => apiFetch<MissingOutcomeItem[]>("/decisions/missing-outcomes"),
};

export const briefingApi = {
  generate: (data: BriefingRequest) =>
    apiFetch<BriefingResponse>("/briefing", { method: "POST", body: JSON.stringify(data) }),
};

export const auditApi = {
  list: () => apiFetch<AuditEntry[]>("/audit"),
  get: (id: number) => apiFetch<AuditEntry>(`/audit/${id}`),
};
