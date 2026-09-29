<div align="center">

# 🧠 ArchMemory

### Architecture Decision & Outcome Memory Agent

**Turns every architectural decision and its real-world outcome into compounding institutional knowledge — so the same expensive mistakes are never repeated.**

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![Hindsight](https://img.shields.io/badge/Memory-Hindsight-6C63FF?style=for-the-badge)](https://github.com/vectorize-io/hindsight)
[![Groq](https://img.shields.io/badge/LLM-Groq-F55036?style=for-the-badge)](https://groq.com)
[![SQLite](https://img.shields.io/badge/DB-SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

<br/>

> *"The average engineering team re-discovers the same architectural failure mode **2.3 times** before it becomes a post-mortem. ArchMemory closes that loop."*

</div>

---

## The Problem It Solves

Every engineering organisation above ~15 people carries the same invisible tax:

| What happens | The real cost |
|---|---|
| An RFC is written, reviewed, and approved | 3–5 engineer-days |
| The decision gets implemented | Weeks to months |
| The outcome — success or failure — goes unrecorded | Institutional knowledge evaporates |
| A new engineer proposes the **exact same pattern** 18 months later | 3–5 more engineer-days, plus the repeat failure |
| A senior engineer leaves | Their mental model of "why we don't do X" leaves with them |

**ArchMemory is the system that closes this loop.** Record the decision. Record the real outcome. Every future proposal is briefed against that living history — with citations, regret scores, and lessons the LLM cannot make up.

---

## How It Works: The Closed Learning Loop

```mermaid
flowchart LR
    D["📋 Decision\n(ADR recorded)"] -- "retain()" --> M[("🧠 Hindsight\narchitecture_decisions")]
    O["📊 Outcome\n(metrics · regret · lessons)\nrecorded months later"] -- "retain()" --> M
    P["📄 New RFC\n/ Proposal"] -- "recall()" --> M
    M -- "decisions + real outcomes" --> B["📑 Grounded Briefing\nevery claim cites a DEC-ID"]
    B -. "informs the next decision" .-> D
```

**The agent's intelligence is not parametric.** The LLM does synthesis. Hindsight does memory. The rules are enforced in code — not just prompts:

- 🔴 **No recalled memory → LLM is never called.** A hard "no history on this topic" response is returned.
- 🟡 **Every recalled fact is labelled** with its `DEC-YYYY-NNN` ID before being handed to the LLM.
- 🟢 **Every cited ID is verified** against what was actually recalled. Hallucinated IDs are flagged `⚠ UNVERIFIED` in the UI and stored in the audit log.

---

## The Visible Learning Curve

This is what makes the system genuinely valuable over time:

| Stage | What the agent knows |
|---|---|
| **Fresh install** | Seed data: 26 realistic decisions, 15 with full measured outcomes |
| **After 5 new decisions** | Begins recognising technology patterns specific to your codebase |
| **After outcomes are attached** | Briefings shift from "here's what was decided" to "here's what actually happened" |
| **After 20+ closed loops** | Synthesises failure patterns: *"In this codebase, event-driven patterns under 10k RPM have required rework 4 out of 6 times"* |

The before/after is **visible in the UI**: every briefing's *Memory used* panel shows `has_outcome_memory: true/false` per recalled decision. Attach an outcome and re-run the same briefing — the panel flips and the briefing text changes.

---

## Demo: 60-Second Walk-through

### Flow A — Brief a new RFC

```
Engineer pastes a new proposal:
  "We want to adopt Redis Streams for async order processing..."

WITHOUT memory  →  Generic LLM advice about pub/sub pros and cons.

WITH Hindsight  →
  ┌─────────────────────────────────────────────────────────────┐
  │ 📌 DEC-2023-011 — Redis Pub/Sub for Notification Service    │
  │    Chosen: Redis Pub/Sub  |  Regret score: 4/5             │
  │    Outcome: "Message loss during Redis restart caused       │
  │    silent order drops. Migrated to Kafka 8 months later.   │
  │    Would not repeat."                                       │
  │                                                             │
  │ 📌 DEC-2024-003 — Kafka for Payment Event Bus              │
  │    Chosen: Kafka  |  Regret score: 1/5                     │
  │    Outcome: "Zero message loss over 14 months. Ops cost     │
  │    higher than expected but worth it at scale."             │
  │                                                             │
  │ ⚠  Risk: At-least-once delivery requires idempotent        │
  │    consumers — your proposal doesn't address this.          │
  │    See DEC-2023-011 for exactly what went wrong.            │
  └─────────────────────────────────────────────────────────────┘
```

### Flow B — Closing the loop

Six months later:

```
Engineer returns and attaches an outcome to DEC-2025-007:
  actual_results: "Throughput 340k msg/s, p99 latency 12ms"
  regret_score:   2
  lessons:        "Consumer group lag monitoring was the blind spot"
  would_repeat:   true

→ Next RFC on the same topic now has a measured success case in memory.
```

### Flow C — Pattern insight (after sufficient data)

```
"Across 7 decisions tagged [event-driven] in services under 10k RPM,
5 later required significant rework (avg 6 weeks). The 2 that succeeded
both had: dedicated ops runbook, consumer lag alerting, and >2 engineers
on the owning team at decision time." — DEC-2023-008, -011, -2024-002...
```

---

## Architecture

```mermaid
graph TB
    subgraph FE["Frontend — Next.js 14 App Router"]
        UI_B["Briefing Page (main screen)"]
        UI_D["Decision List + Detail + Export"]
        UI_O["Outcome Form"]
        UI_A["Audit Log"]
        UI_M["Missing Outcomes"]
        UI_L["Login"]
    end

    subgraph BE["Backend — FastAPI"]
        R_BR["POST /api/briefing"]
        R_DEC["POST/GET/PATCH /api/decisions"]
        R_OUT["POST /api/decisions/:id/outcomes"]
        R_AUD["GET /api/audit"]
        R_EXP["GET /api/decisions/:id/export"]
        R_AUTH["POST /api/auth/login"]
    end

    subgraph MEM["Memory — Hindsight"]
        HS[("architecture_decisions bank\nretain · recall\nsemantic + graph + temporal")]
    end

    subgraph DB["Storage — SQLite"]
        SQL[("Decision pointers · Outcome pointers\nBriefing audit · Users")]
    end

    LLM["Groq LLM\nqwen3-32b / gpt-oss-120b"]

    UI_B & UI_D & UI_O & UI_A & UI_M --> R_BR & R_DEC & R_OUT & R_AUD & R_EXP
    R_BR --> HS
    R_DEC & R_OUT --> HS
    R_BR --> LLM
    R_DEC & R_OUT & R_AUD --> SQL
    HS -->|recalled facts labelled by DEC-ID| R_BR
    LLM -->|grounded briefing| R_BR
```

### Why Two Stores?

| Store | What lives there | Why |
|---|---|---|
| **Hindsight** | Rich natural-language content, extracted facts, outcome narratives | Semantic recall, graph links, temporal retrieval, multi-strategy fusion |
| **SQLite** | ID pointers, metadata, timestamps, `memory_synced` flag | Fast listing, filtering, foreign-key integrity, resync after Hindsight outage |

---

## Feature Set

### 🧠 Memory (Hindsight-powered)

| Feature | Description |
|---|---|
| **Decision Retain** | Full ADR captured as rich prose + structured metadata. Every `retain()` uses a stable `document_id` — PATCH and resync upsert, never duplicate. |
| **Outcome Retain** | Metrics (JSON), incidents, regret score (1–5), lessons, `would_repeat` attached months later. Directly changes what future briefings can say. |
| **Smart Recall** | Multi-strategy: semantic + keyword + graph + temporal fusion. Optional `domain` / `services` tag filters narrow scope. |
| **Pattern Synthesis** | After sufficient data, briefings surface cross-decision failure and success patterns, cited by DEC-ID. |
| **Resync** | If Hindsight is unreachable at save time, `memory_synced=false` is set. `POST /resync` re-retains idempotently at any time. |

### 📋 Decision Management

| Feature | Description |
|---|---|
| **Structured ADR form** | Context, forces, options considered, chosen option, rationale, expected outcomes, tags, related decisions |
| **List + Search + Filter** | Filter by domain, status, technology tag, or whether an outcome exists |
| **Decision Detail** | Full ADR + every outcome + regret score timeline |
| **Markdown Export** | `GET /api/decisions/{id}/export` — full ADR + all outcomes as portable, standalone markdown |
| **Related decision links** | Decisions reference each other; briefings surface the chain |

### 📑 Briefing Engine

| Feature | Description |
|---|---|
| **Grounded citations** | Every `DEC-YYYY-NNN` in the briefing was verified against the recalled set before being returned |
| **Hallucination firewall** | IDs the LLM invented but weren't recalled are flagged `⚠ UNVERIFIED` in the UI and audit log |
| **No-memory guard** | If recall returns nothing citable, the LLM is not called. A fixed "no history" response is returned. |
| **Outcome-aware prompting** | Each evidence block is labelled with outcome count from SQL, so the model knows whether outcomes exist even if they weren't in the top recall results |

### 🔍 Audit & Observability

| Feature | Description |
|---|---|
| **Briefing Audit Log** | Every briefing stores: recalled IDs, cited IDs, rejected (unverified) IDs, model used, latency ms, proposal excerpt |
| **Missing Outcomes view** | Active decisions with no outcome, oldest first, each with a one-click link to record one |
| **`memory_synced` flag** | Per-decision and per-outcome; UI shows a "Retry sync" button when false |
| **Request IDs** | Every API error response includes a `request_id` matching the server log line |

### 🔐 Security & Auth

| Feature | Description |
|---|---|
| **JWT sessions** | HS256/384/512, required `exp`/`iat`/`sub`, algorithm fixed server-side (`alg:none` rejected) |
| **httpOnly cookie** | Page JS never sees the token. `SameSite=Lax`. `AUTH_COOKIE_SECURE=true` for HTTPS. |
| **scrypt passwords** | Per-hash salt, constant-time comparison. Unknown usernames cost the same time as wrong passwords. |
| **Login throttle** | Locks a username after `LOGIN_MAX_FAILURES` failures for `LOGIN_LOCKOUT_SECONDS` |
| **Startup refuses unsafe config** | Missing or short `JWT_SECRET_KEY` prevents the API from starting at all |
| **Audit integrity** | `requested_by` on briefing audits is taken from the verified session, never from the request body |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Memory** | [Hindsight](https://github.com/vectorize-io/hindsight) | Multi-strategy recall: semantic + keyword + graph + temporal. Stable `document_id` upserts. Self-hostable via Docker. |
| **Backend** | FastAPI 0.111 + SQLModel + aiosqlite | Async, typed, fast. Auto-generated OpenAPI docs at `/api/docs`. |
| **LLM** | Groq (`qwen/qwen3-32b` default) | Sub-second inference. Configurable to any OpenAI-compatible endpoint. |
| **Frontend** | Next.js 14 App Router + Tailwind CSS + shadcn/ui | App Router for streaming. shadcn for accessible, composable components. |
| **Database** | SQLite (dev) → PostgreSQL (prod) | Zero-config locally; one env-var swap to scale. |
| **Auth** | PyJWT + scrypt (stdlib) | No external auth service dependency. |
| **Package mgmt** | `uv` (or pip) | 10–100× faster installs than pip. |

---

## Project Structure

```
ArchMemory/
├── backend/
│   ├── app/
│   │   ├── config.py               # All settings via pydantic-settings (.env → typed attrs)
│   │   ├── db.py                   # SQLAlchemy async engine + session factory
│   │   ├── export.py               # Markdown ADR export — pure function (fully testable)
│   │   ├── llm.py                  # LLM client wrapper, configurable provider
│   │   ├── prompts.py              # Strict, citation-focused system prompts
│   │   ├── main.py                 # FastAPI app factory + router registration
│   │   ├── auth/
│   │   │   ├── security.py         # scrypt hashing · JWT sign/verify · login throttle
│   │   │   ├── service.py          # Users table · first-run admin bootstrap
│   │   │   └── deps.py             # require_user FastAPI dependency
│   │   ├── memory/
│   │   │   ├── client.py           # Hindsight wrapper: retain() · recall() · resync()
│   │   │   └── content.py          # Prose formatters: decision → text, outcome → text
│   │   ├── models/
│   │   │   ├── decision.py         # Decision · Outcome · BriefingAudit SQLModel tables
│   │   │   └── user.py             # User account table
│   │   └── routes/
│   │       ├── briefing.py         # POST /api/briefing  ← the most important endpoint
│   │       ├── decisions.py        # CRUD + export + resync
│   │       ├── outcomes.py         # Attach outcomes to decisions
│   │       ├── audit.py            # GET /api/audit
│   │       ├── missing_outcomes.py # GET /api/decisions/missing-outcomes
│   │       └── auth.py             # login · logout · /me
│   ├── scripts/
│   │   ├── seed.py                 # 26 realistic decisions, 15 with full outcomes → Hindsight + SQLite
│   │   └── create_user.py          # Add users / change passwords
│   ├── tests/
│   │   ├── conftest.py             # In-memory Hindsight fake + scripted LLM stub (no network needed)
│   │   ├── test_memory_loop.py     # Decision → outcome → briefing · grounding · citation verify · resync
│   │   ├── test_real_client.py     # MemoryClient against real SDK types (canary for SDK drift)
│   │   ├── test_auth.py            # Route protection · cookie flags · throttle · bootstrap · unsafe config
│   │   ├── test_phase4_api.py      # Export with outcomes · request IDs · missing-outcome ages
│   │   ├── test_security.py        # scrypt · JWT edge cases (alg:none, expired, wrong algo) · throttle
│   │   └── test_export.py          # Markdown rendering (pure unit, no I/O)
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── page.tsx                    # Briefing page (main screen)
│       │   ├── decisions/                  # List · search · filter
│       │   ├── decisions/new/              # Record a new ADR
│       │   ├── decisions/[id]/             # Decision detail + export button
│       │   ├── decisions/[id]/outcome/     # Attach outcome form
│       │   ├── audit/                      # Audit log: recalled / cited / rejected IDs
│       │   ├── missing/                    # Decisions lacking outcomes
│       │   └── login/                      # Sign-in page
│       └── components/
│           ├── auth-provider.tsx           # Session state + AuthGate (redirects to /login)
│           ├── citations.tsx               # DEC-IDs rendered as clickable chips in briefings
│           ├── notice.tsx                  # Warning banner for unverified citations
│           └── token-input.tsx             # Tag / service multi-input component
└── README.md
```

---

## Getting Started

### Prerequisites

- **Python 3.11+** and **Node.js 20+**
- A running **Hindsight** instance — self-hosted via Docker (~60 seconds) or [Hindsight Cloud](https://hindsight.vectorize.io)
- A **Groq API key** — free tier available at [console.groq.com](https://console.groq.com)

> **Note:** Hindsight uses an LLM internally for fact extraction. That LLM key is configured on the Hindsight server (Step 1), and is entirely separate from the briefing LLM configured in ArchMemory (Step 2).

---

### Step 1 — Start Hindsight

```bash
# Self-hosted (recommended). Named volume keeps memory across restarts.
export OPENAI_API_KEY=sk-your-key-here

docker run -it --pull always \
  --name hindsight --restart unless-stopped \
  -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
  -v hindsight-data:/home/hindsight/.pg0 \
  ghcr.io/vectorize-io/hindsight:latest

# API available at:   http://localhost:8888
# Control plane UI:   http://localhost:9999

# Use Groq for Hindsight's internal fact extraction instead of OpenAI:
#   -e HINDSIGHT_API_LLM_PROVIDER=groq -e HINDSIGHT_API_LLM_API_KEY=$GROQ_API_KEY

# Use Hindsight Cloud instead:
#   Set HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io in backend/.env
#   Set HINDSIGHT_API_KEY=your-cloud-key in backend/.env
```

---

### Step 2 — Backend Setup

```bash
cd backend

# Install dependencies (uv recommended — ~10× faster than pip)
pip install uv
uv pip install -e .
# or the classic way: pip install -e .

# Configure environment
cp .env.example .env
# Edit .env — minimum required values shown below
```

**Minimum `.env` values:**

```env
HINDSIGHT_BASE_URL=http://localhost:8888
HINDSIGHT_API_KEY=                          # empty for self-hosted; set for Cloud

LLM_API_KEY=your-groq-api-key
LLM_MODEL=qwen/qwen3-32b                   # or: openai/gpt-oss-120b

JWT_SECRET_KEY=                            # python -c "import secrets; print(secrets.token_urlsafe(48))"
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-strong-password        # 10+ characters; creates the first account on startup
```

```bash
# Start the API server
uvicorn app.main:app --reload --port 8000

# Interactive API docs: http://localhost:8000/api/docs
```

---

### Step 3 — Load Seed Data

```bash
cd backend

# Loads 26 realistic decisions + 15 full outcomes into Hindsight AND SQLite.
# Takes ~2 minutes (one retain() call per record).
python scripts/seed.py
```

The seed data spans: event-driven messaging (Kafka, Redis Streams), caching strategies, database choices, service mesh adoption, API gateway decisions, monolith splits, and auth architecture — each with realistic context, rationale, and measured outcomes including failures and regret scores.

**The agent is immediately useful on first run.**

---

### Step 4 — Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local    # defaults to http://localhost:8000; edit if needed
npm run dev

# Open: http://localhost:3000
# Sign in with the ADMIN_USERNAME / ADMIN_PASSWORD you set in backend/.env
```

Additional accounts:

```bash
cd backend
python scripts/create_user.py alice
python scripts/create_user.py bob --update    # reset an existing password
```

---

## API Reference

All endpoints except `login`, `logout`, and `health` require authentication:
- **Browser:** session cookie set automatically by `/api/auth/login`
- **Scripts / CLI:** `Authorization: Bearer <token>` using the token from the login response body

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Exchange credentials for session cookie + bearer token |
| `POST` | `/api/auth/logout` | Clear session cookie |
| `GET` | `/api/auth/me` | Current user info + auth status |
| `GET` | `/api/health` | Liveness check |
| `POST` | `/api/decisions` | **Create ADR** — retains to Hindsight |
| `GET` | `/api/decisions` | List decisions (filter: `domain`, `status`, `tag`, `has_outcome`) |
| `GET` | `/api/decisions/{id}` | Full decision detail |
| `PATCH` | `/api/decisions/{id}` | Update metadata — re-retains to Hindsight |
| `POST` | `/api/decisions/{id}/resync` | Re-retain after Hindsight outage (idempotent) |
| `GET` | `/api/decisions/{id}/export` | **Export ADR + all outcomes as Markdown** |
| `POST` | `/api/decisions/{id}/outcomes` | **Attach outcome** — retains to Hindsight |
| `GET` | `/api/decisions/{id}/outcomes` | List all outcomes for a decision |
| `POST` | `/api/briefing` | **Generate grounded briefing** — the core endpoint |
| `GET` | `/api/audit` | Briefing audit log: recalled / cited / rejected IDs per request |
| `GET` | `/api/decisions/missing-outcomes` | Decisions with no outcome, oldest first |

📖 **Interactive docs:** `http://localhost:8000/api/docs`

---

## How Memory Works (The Technical Core)

### Retaining a Decision or Outcome

`app/memory/content.py` converts each record into dense natural language.  
`app/memory/client.py` sends it to Hindsight with three critical arguments:

| Argument | Example value | Purpose |
|---|---|---|
| `document_id` | `DEC-2024-001` / `DEC-2024-001:outcome:7` | Stable key — re-retaining **upserts**, so PATCH and resync never create duplicate memories |
| `tags` | `kind:decision`, `domain:platform`, `service:payments`, `tag:kafka`, `year:2024`, `outcome_severity:high`, `would_repeat:false` | Filterable metadata used at recall time |
| `metadata` | `{decision_id, kind, domain, ...}` | Attributes every recalled fact back to its source decision |
| `timestamp` | decision date / outcome `recorded_at` | Enables temporal retrieval ("decisions from the last 18 months") |

Hindsight extracts *facts* from the prose. Because a fact can lose its source ID during extraction, attribution uses a cascade: `metadata` → `document_id` → `tags` → single unambiguous ID in text → **uncitable**.

### The Briefing Recall Flow

```mermaid
sequenceDiagram
    actor TL as Tech Lead
    participant UI as Next.js
    participant API as FastAPI
    participant H as Hindsight
    participant L as Groq LLM

    TL->>UI: Paste RFC / proposal text
    UI->>API: POST /api/briefing {proposal, domain?, services?}
    API->>API: require_user — 401 if not signed in
    API->>H: recall(proposal, tag_filters?)
    H-->>API: facts, attributed to DEC-IDs

    alt Nothing citable recalled
        API-->>UI: Fixed no-memory response
        note over API: LLM is NOT called
    else Memories recalled
        API->>API: Build evidence blocks labelled by DEC-ID
        API->>L: strict system prompt + evidence + proposal
        L-->>API: Briefing with DEC-ID citations
        API->>API: Verify every cited ID was in the recalled set
        API->>API: Flag unverified citations as UNVERIFIED
    end

    API->>API: Write audit row (recalled · cited · rejected · user · latency)
    API-->>UI: briefing + cited_ids + recalled_decisions + unverified_citations
```

### The System Prompt (Citation-Strict)

Rules are enforced **in both the prompt and in code**:

```
RULES (enforced — do not deviate):
1. You may ONLY cite decisions from the EVIDENCE section below.
2. Every factual claim about a past decision MUST include its DEC-YYYY-NNN ID.
3. If you are uncertain, say so — do not invent details.
4. Distinguish clearly between "expected outcome" and "actual recorded outcome".
5. If no outcome is recorded for a decision, say "outcome not yet recorded".
6. Do not use your general knowledge about technology as evidence.
   Only recalled decisions count as evidence.
```

Any ID the model cites that was not in the recalled set is:
- Flagged `⚠ UNVERIFIED` inline in the briefing text
- Added to `unverified_citations` in the API response
- Stored in the audit row
- Shown with a warning banner in the UI — never silently accepted as evidence

### The Before / After Story (Verifiable in Tests)

```python
# tests/test_memory_loop.py
def test_before_after_outcome_changes_what_the_agent_can_say():
    # 1. Retain a decision (no outcome yet)
    # 2. Run briefing → response contains "outcome not yet recorded"
    # 3. Retain an outcome (regret_score=4, lessons="X caused Y")
    # 4. Run same briefing → response now contains outcome metrics and lessons
    # recalled_decisions[0]["has_outcome_memory"] flips to True
```

Run it yourself:

```bash
cd backend && pip install -e ".[dev]" && pytest tests/test_memory_loop.py -v
```

---

## Data Model

```mermaid
erDiagram
    DECISION {
        string decision_id PK
        string title
        date date
        string authors
        string domain
        json services
        string status
        text context
        text forces
        json options
        string chosen_option
        text rationale
        text expected_outcomes
        json tags
        json related_decisions
        bool memory_synced
    }

    OUTCOME {
        int id PK
        string decision_id FK
        json metrics
        text incidents
        text actual_results
        int regret_score
        text lessons
        bool would_repeat
        datetime recorded_at
        string recorded_by
        bool memory_synced
    }

    BRIEFING_AUDIT {
        int id PK
        string proposal_excerpt
        json recalled_decision_ids
        json recalled_memories
        json cited_decision_ids
        json unverified_citation_ids
        int recalled_memory_count
        text briefing_text
        string model_used
        string requested_by
        datetime requested_at
        int latency_ms
    }

    USER {
        int id PK
        string username UK
        string password_hash
        bool is_active
        datetime created_at
    }

    DECISION ||--o{ OUTCOME : "has outcomes"
    DECISION ||--o{ BRIEFING_AUDIT : "recalled in"
```

---

## Test Coverage

```bash
cd backend
pip install -e ".[dev]"
pytest -v
```

Tests use an **in-memory Hindsight fake** and a **scripted LLM stub** — no network, no API keys needed.

| Test file | What it covers |
|---|---|
| `test_memory_loop.py` | Decision → outcome → briefing loop · grounding enforcement · citation verification · Hindsight outage and resync |
| `test_real_client.py` | `MemoryClient` against real SDK types — canary that catches SDK drift before it breaks production |
| `test_auth.py` | Route protection · JWT cookie flags · login throttle · disabled user enforcement · admin bootstrap · unsafe-config startup refusal |
| `test_phase4_api.py` | Markdown export with outcomes · request ID propagation · missing-outcome age calculation |
| `test_security.py` | scrypt hashing · JWT edge cases (`alg:none`, expired, wrong algo) · throttle state |
| `test_export.py` | Markdown rendering correctness — pure function, no I/O |

---

## Frontend Pages

| Route | Purpose |
|---|---|
| `/` | **Briefing** — paste RFC, optionally filter by domain/services, see cited DEC-ID links, Memory Used panel |
| `/decisions` | List with search, domain/status/has-outcome filters, `memory_synced` warning badges |
| `/decisions/new` | Structured ADR form |
| `/decisions/[id]` | Full ADR + outcomes + regret timeline + **Markdown export** + **Retry sync** |
| `/decisions/[id]/outcome` | Attach outcome: named metrics, regret score, lessons, `would_repeat` |
| `/audit` | Briefing audit log — expand any entry to see recalled / cited / rejected IDs |
| `/missing` | Decisions without outcomes, oldest first, one-click to record outcome |
| `/login` | Username + password. Redirects back to original destination after signing in. |

**Citation rendering:** IDs the model cited that were recalled become clickable links to the decision detail page. IDs invented by the model that were *not* recalled show a `⚠` marker and trigger a warning banner — they are never silently presented as evidence.

**Resilience:** API unreachable → pages say so clearly. Unexpected server error → shows a `request_id` matching the log. Render error in one page → contained by error boundary, does not blank the app. Hindsight down at save time → form explains the record was saved but not retained, and links to **Retry sync**.

---

## Environment Variables

Full list with explanations in `backend/.env.example`.

```env
# Hindsight
HINDSIGHT_BASE_URL=http://localhost:8888   # self-hosted default
HINDSIGHT_API_KEY=                         # required for Hindsight Cloud; empty for self-hosted

# LLM  (Groq default; any OpenAI-compatible endpoint works)
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=your-groq-api-key
LLM_MODEL=qwen/qwen3-32b                  # or: openai/gpt-oss-120b

# Auth
AUTH_ENABLED=true
JWT_SECRET_KEY=                           # python -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480
ADMIN_USERNAME=admin
ADMIN_PASSWORD=                           # 10+ characters; bootstrapped on first start
AUTH_COOKIE_SECURE=false                  # set true when serving over HTTPS

# Login throttle
LOGIN_MAX_FAILURES=5
LOGIN_LOCKOUT_SECONDS=300

# Database
DATABASE_URL=sqlite+aiosqlite:///./archmemory.db
# PostgreSQL: postgresql+asyncpg://user:pass@host/dbname
```

---

## Access Control & Security

- **Enforcement is in the API.** Every data route depends on `require_user`. The frontend redirect is only UX — a valid token is still required for every API call, and the account must be active.
- **Session cookie.** Login sets an `httpOnly`, `SameSite=Lax` cookie. Page JavaScript never sees the token. Set `AUTH_COOKIE_SECURE=true` when serving over HTTPS.
- **Passwords** use `scrypt` with a per-hash salt. Unknown usernames and wrong passwords cost the same verification time.
- **Tokens** are HS256/384/512 JWTs with required `exp`, `iat`, and `sub`. `alg:none` and algorithm-swap attacks are rejected by design.
- **Login throttle** is in-process: resets on server restart, not shared across workers. A known limitation for the current scope.
- **Audit integrity.** `requested_by` on briefing audits is taken from the verified session, not from the request body.
- **Startup refuses unsafe config.** A missing, placeholder, or short `JWT_SECRET_KEY` stops the API from starting when `AUTH_ENABLED=true`.

---

## Key Design Principles

**1. Memory is the product, not a feature.**  
Without Hindsight, this is a generic LLM wrapper. With it, quality compounds as outcomes are recorded. The LLM contributes synthesis and structure; all factual claims come from retained history.

**2. Grounding is enforced in code, not only in prompts.**  
The hallucination firewall — no recall → no LLM call; citation verification; unverified ID flagging — is Python logic. Prompts can be ignored; code cannot.

**3. The closed loop is the core metric.**  
A decision with no outcome is incomplete. The *Missing Outcomes* view and the before/after briefing delta exist to make the cost of not closing the loop visible, and to make closing it as easy as one click.

**4. Two stores, one source of truth.**  
SQLite holds cheap-to-query pointers. Hindsight holds the meaning. Nothing in SQLite is the authoritative answer to "what was this decision about" — Hindsight is.

---

## Contributing

Follow these patterns when extending ArchMemory:

- All Hindsight interactions go through `app/memory/client.py` — never call the SDK directly from a route handler.
- Content formatting (decision / outcome → prose) lives in `app/memory/content.py` — keep it pure and unit-testable.
- Route handlers stay thin. Business logic belongs in helper functions.
- Every new LLM call must be grounded in Hindsight recall. Free-form generation is not permitted.
- New routers must be mounted with `dependencies=[Depends(require_user)]` in `app/main.py`.
- Re-retaining on PATCH is the correct pattern — never delete and re-insert a Hindsight document.

---

<div align="center">

**ArchMemory** — Because institutional knowledge shouldn't live only in people's heads.

*Built with [Hindsight](https://github.com/vectorize-io/hindsight) · [FastAPI](https://fastapi.tiangolo.com) · [Next.js](https://nextjs.org) · [Groq](https://groq.com)*

</div>

