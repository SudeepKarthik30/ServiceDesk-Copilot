# ServiceDesk Copilot

An AI-powered IT helpdesk. An employee raises a ticket in plain English. A retrieval-augmented
AI pipeline classifies it, searches past resolved tickets, and either **solves it directly** when
it's confident and the fix is safe, or **routes it to the right IT team** with a suggested fix and
similar tickets attached. IT can see every ticket, and every AI decision is logged and auditable.

**Status: built and working end to end.** Login → raise a ticket → AI classifies, searches, and
either auto-answers it or escalates it to an agent → agent resolves it → optionally added to the
knowledge base for next time. All of it is live: real JWT auth, a real Postgres-backed workflow, a
real Groq LLM call, real hybrid search over a real Qdrant index, and a real React UI on top. What's
left (seeding realistic demo volume, SQL-level analytics, Docker deploy, and a formal RAGAS/
scikit-learn evaluation) is called out explicitly in [Project status](#project-status) below — this
README doesn't round up.

## Why

Most IT tickets are repeats: password resets, VPN drops, printer problems, access requests.
Agents spend a lot of time re-answering things that were already solved before. ServiceDesk
Copilot:

1. **Solves simple, repeated problems instantly**, citing the exact past ticket the fix came from.
2. **Routes everything else** to the right team and the least-loaded agent, with the AI's attempt
   attached so the agent isn't starting cold.
3. **Keeps humans in control.** The AI only auto-answers when every one of a strict set of safety
   checks passes. Anything risky, urgent, or uncertain always goes to a person — confirmed with a
   target of **zero unsafe auto-answers**.

It's also a deliberate full-stack showcase: a typed React SPA, a Django/DRF API with real
role-based permissions, async background jobs, and an AI core (hybrid dense+sparse retrieval,
cross-encoder reranking, and a plain, testable, rule-based safety gate — no framework magic).

## How it works

```
Employee raises ticket
        │
        ▼
  Ticket saved (NEW) ──► Celery background job ──► triage(ticket)  (TRIAGING)
                                                        │
                        ┌───────────────────────────────┴───────────────────────────┐
                        ▼                                                           ▼
              Safe + confident                                             Not safe / not sure / error
              AUTO-ANSWER (AI_ANSWERED)                                    ESCALATE (ASSIGNED)
                        │                                                           │
     Employee sees the fix + ✅ / ❌                                Agent is notified, sees the AI
     IT team gets a notification                                   suggestion + similar tickets
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
     ✅ → RESOLVED            ❌ → ASSIGNED to an agent
                                  (AI attempt attached)
```

```
NEW → TRIAGING → AI_ANSWERED | ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED   (+ REOPENED)
```

Every status change writes an audit log entry. Routing is `category → team → least-loaded agent`.
Each ticket gets an SLA due time from `category × urgency`.

### The AI pipeline

One entry point, `backend/ai/pipeline.py: triage(ticket)` — the live app, the `triage_demo` CLI
command, and (later) the evaluation suite all call the exact same function.

| Step | What happens |
|---|---|
| **1. Classify** | LLM returns `{category, urgency}` as JSON, which decides the team and agent. |
| **2. Rewrite** | LLM rewrites the messy ticket text into a clean search query. |
| **3. Retrieve** | Qdrant hybrid search: dense(original) + dense(rewritten) + BM25(original), top 10 each, merged and deduped. No hard category filter, so a wrong category guess can't hide the right answer. |
| **4. Rerank** | A cross-encoder scores each candidate against the ticket → keep the top 5. |
| **5. Solve** | LLM writes a fix using **only** those top 5 → `{can_solve, confidence, steps: [{text, source}]}`. Every step must cite a real source ticket. |
| **6. Decide** | A pure Python function (`decide.py`) applies the safety rules below — no LLM judgment call. |
| **7. Save** | An `AIResult` row records the inputs, candidates, scores, answer, decision, reasons, and latency. |

**Auto-answer only if every one of these holds:** rerank score ≥ `RERANK_THRESHOLD` · `can_solve`
is true · confidence is `high` · every step cites one of the top 5 · the category is marked
`safe_to_auto_solve` · urgency isn't P1. **Any AI error escalates.** The system fails safe, never
loud.

The knowledge base only grows through **human review**: an agent/admin clicks *Add to KB* on a
`RESOLVED` ticket, edits the text, PII gets masked, it's embedded and upserted into Qdrant. An
AI-solved ticket is only eligible if the employee actually clicked ✅ — not if it was later fixed
manually after a ❌. There's a matching *Remove from KB* action. Nothing enters the KB
automatically.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 19 + TypeScript + Vite + Tailwind v4, TanStack Query, React Router, axios, Recharts |
| Backend | Django 5 + DRF + SimpleJWT, Python 3.12, deps via `uv` |
| Database | PostgreSQL 16 |
| Background jobs | Celery + Redis |
| Vector search | Qdrant — one collection, named vectors `dense` (bge-small, 384d) + `sparse` (BM25) |
| Embeddings / rerank | `fastembed` (ONNX, no PyTorch): `BAAI/bge-small-en-v1.5`, `Qdrant/bm25`, cross-encoder `Xenova/ms-marco-MiniLM-L-6-v2` |
| LLM | Open-weight models via **Groq** (`openai/gpt-oss-120b` / `-20b`), called through the OpenAI-compatible SDK — swapping providers is an env var, not a code change |
| Containers | Docker Compose (Postgres, Redis, Qdrant today; app containers land in the deploy phase) |

No LangChain/LangGraph — the pipeline is plain, readable Python modules.

## Getting started

Prerequisites: Docker Desktop, Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 18+.

```bash
# 1. Infrastructure: Postgres, Redis, Qdrant
docker compose up -d

# 2. Backend
cd backend
cp .env.example .env              # fill in LLM_API_KEY (free at console.groq.com)
uv sync
uv run python manage.py migrate
uv run python manage.py seed            # demo teams/categories/users
uv run python manage.py download_dataset && uv run python manage.py clean_dataset && uv run python manage.py index_dataset
uv run python manage.py seed_kb         # hand-written, actionable KB articles
uv run python manage.py runserver       # http://localhost:8000/api/health/

# 3. Celery worker — REQUIRED, in its own terminal.
#    Without this, tickets stay stuck in TRIAGING forever: creating a ticket only enqueues
#    a job onto Redis, nothing processes it until a worker is running.
cd backend
uv run celery -A config worker -P solo -l info   # -P solo is needed on Windows

# 4. Frontend
cd frontend
npm install
npm run dev                             # http://localhost:5173
```

`seed` creates demo accounts (password `password123` for all): `admin@example.com`, employees
(`alice@example.com`, `bob@example.com`, `carol@example.com`), and agents per team (e.g.
`net.agent1@example.com`, `hw.agent1@example.com`, `access.agent1@example.com`).

Run the AI pipeline against arbitrary text without touching the UI or the database:

```bash
uv run python manage.py triage_demo "My VPN keeps disconnecting every few minutes"
```

## Repo layout

```
backend/
  config/      settings (all config from .env), urls, health view, Celery app
  accounts/    custom User model (email login, role, team)
  tickets/     Team/Category/SLAPolicy/Ticket/Comment/AuditLog/Notification/AIResult,
               views, permissions, services/ (routing, sla, workflow, notifications)
  ai/          pipeline.py (triage), decide.py, embeddings/reranker/llm clients,
               dataset download/clean/index commands, KB seed/add/remove
frontend/src/  React app — api/ (client, types, hooks), components/, pages/
data/          raw/ + processed/ (gitignored, generated by the ai management commands)
docker-compose.yml
```

## Testing

```bash
cd backend && uv run pytest      # 72 tests: role isolation, SLA, routing, workflow,
                                  # confirm flow, KB eligibility, triage() decision logic
cd frontend && npm run build     # type-check + production build
cd frontend && npm run lint      # oxlint
```

## Project status

Built in order, each phase functionally complete and tested before moving to the next.

| Phase | Goal | Status |
|---|---|---|
| 0 | Setup: Docker Compose, Django + Vite skeletons | ✅ Done |
| 1 | Backend core: models, JWT, roles/permissions, routing, SLA, status workflow, audit log, seed command | ✅ Done |
| 2 | Data + Qdrant: download, clean, mask PII, index ~23.6k tickets into hybrid search | ✅ Done |
| 3 | AI pipeline: `triage()` end to end, `triage_demo` CLI | ✅ Done |
| 4 | Wiring: Celery task on create, ✅/❌ confirm flow, notifications, add/remove KB | ✅ Done |
| 5 | Frontend: Login, New ticket, My tickets, Agent queue, Ticket detail, Analytics | ✅ Built, verified against the live API; a full click-through pass is still pending |
| 6 | Analytics + deploy: seeded demo volume, SQL-level aggregates, Dockerfiles, CI, app containers | ⏳ Next |
| 7 | Evaluation: RAGAS + scikit-learn metrics on a held-out set, tune `RERANK_THRESHOLD`, CI quality gate | ⏳ Not started |

Two real bugs were found and fixed while building this (not staged demo issues — actual defects
caught during development): a boolean parsed from a form-encoded request body that made `{"resolved":
false}` behave as `true`, and a serializer that leaked internal, agent-only comments to employees.
Both are covered by regression tests now.

## Out of scope for v1

Groundedness checker beyond the citation check, TF-IDF vs LLM comparison, local models via Ollama,
follow-up questions when info is missing, satisfaction ratings, incident detection across many
similar tickets, multi-tenant/billing.
