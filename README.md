# ServiceDesk Copilot

An IT helpdesk where a retrieval-augmented pipeline triages every incoming ticket: it classifies
the problem, searches past resolved tickets with hybrid dense+sparse search, reranks the results
with a cross-encoder, and either answers the ticket directly or routes it to the right team with a
draft fix attached. The decision to auto-answer is a plain, testable rule (not an LLM's own
judgment), and any AI error or low-confidence result escalates to a human instead of guessing.

Phases 0 through 5 are implemented and working end to end against a live Groq model and a real
Qdrant index: an employee can log in, raise a ticket, have it classified and either resolved or
escalated by the pipeline, and an agent can pick it up, resolve it, and add it back to the
knowledge base. Phase 6 (seeded demo data, SQL-level analytics, deployment) and Phase 7
(quantitative evaluation) are not started; see [Status](#status).

## How a ticket moves through the system

```
Employee raises ticket
        |
        v
  Ticket saved (NEW) --> Celery job --> triage(ticket)  (TRIAGING)
                                              |
                    +-------------------------+-------------------------+
                    v                                                   v
          safe + confident                                    not safe / not sure / error
          AUTO-ANSWER (AI_ANSWERED)                            ESCALATE (ASSIGNED)
                    |                                                   |
     employee sees the fix, confirms                     agent is notified, sees the AI
     fixed or not fixed; team notified                   attempt and the similar tickets
                    |
          +---------+---------+
          v                   v
     fixed -> RESOLVED   not fixed -> ASSIGNED to an agent, AI attempt attached
```

```
NEW -> TRIAGING -> AI_ANSWERED | ASSIGNED -> IN_PROGRESS -> RESOLVED -> CLOSED   (+ REOPENED)
```

Every status change writes an audit log row. Routing is `category -> team -> least-loaded agent`.
Each ticket gets an SLA due time from `category x urgency`.

## The triage pipeline

Single entry point: `backend/ai/pipeline.py: triage(ticket)`. The live app and the `triage_demo`
CLI command both call this function; the Phase 7 evaluation will too.

| Step | What happens |
|---|---|
| 1. Classify | LLM returns `{category, urgency}` as JSON, which decides the team and agent. |
| 2. Rewrite | LLM rewrites the ticket text into a clean search query. |
| 3. Retrieve | Qdrant hybrid search: dense(original) + dense(rewritten) + BM25(original), top 10 each, merged and deduped by ticket id. No hard category filter, so a wrong classification can't hide the right answer. |
| 4. Rerank | A cross-encoder scores each candidate against the ticket; keep the top 5. |
| 5. Solve | LLM writes a fix using only those top 5 -> `{can_solve, confidence, steps: [{text, source}]}`. Every step must cite a source ticket id. |
| 6. Decide | A pure function (`decide.py`) applies the rules below. No LLM judgment call at this stage. |
| 7. Save | An `AIResult` row records the inputs, candidates, scores, answer, decision, reasons, and latency. |

Auto-answer only if all of the following hold: rerank score at or above `RERANK_THRESHOLD`,
`can_solve` is true, confidence is `high`, every step cites one of the top 5, the category is
marked `safe_to_auto_solve`, and urgency is not P1. Any AI error (timeout, malformed JSON,
API failure) escalates instead of failing the request.

The knowledge base only grows through human review: an agent or admin edits and confirms the text
of a resolved ticket before it's masked for PII, embedded, and upserted into Qdrant. A ticket the
AI auto-answered is only eligible if the employee confirmed the fix worked; if they said it didn't
and an agent fixed it manually afterward, it doesn't qualify. There's a matching remove-from-KB
action, and nothing is added automatically.

## Stack

| Layer | Choice |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind v4, TanStack Query, React Router, axios, Recharts |
| Backend | Django 5, DRF, SimpleJWT, Python 3.12, dependencies via `uv` |
| Database | PostgreSQL 16 |
| Background jobs | Celery + Redis |
| Vector search | Qdrant, one collection with named vectors `dense` (bge-small, 384d) and `sparse` (BM25) |
| Embeddings / rerank | `fastembed` (ONNX, no PyTorch): `BAAI/bge-small-en-v1.5`, `Qdrant/bm25`, cross-encoder `Xenova/ms-marco-MiniLM-L-6-v2` |
| LLM | Open-weight models via Groq (`openai/gpt-oss-120b` / `-20b`) through the OpenAI-compatible SDK, so switching providers is a config change |
| Containers | Docker Compose for Postgres, Redis, and Qdrant; application containers are part of the deploy phase |

No LangChain or LangGraph. The pipeline is plain Python modules.

## Running it locally

Requires Docker Desktop, Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node 18+.

```bash
# infrastructure
docker compose up -d

# backend
cd backend
cp .env.example .env              # fill in LLM_API_KEY - a free key from console.groq.com works
uv sync
uv run python manage.py migrate
uv run python manage.py seed
uv run python manage.py download_dataset
uv run python manage.py clean_dataset
uv run python manage.py index_dataset
uv run python manage.py seed_kb
uv run python manage.py runserver       # http://localhost:8000/api/health/

# celery worker, separate terminal - required
# creating a ticket only enqueues a job on Redis; nothing runs it until a worker is up,
# so without this every ticket sits in TRIAGING indefinitely
cd backend
uv run celery -A config worker -P solo -l info   # -P solo is required on Windows

# frontend
cd frontend
npm install
npm run dev                             # http://localhost:5173
```

`seed` creates demo accounts, password `password123` for all: `admin@example.com`; employees
`alice@example.com`, `bob@example.com`, `carol@example.com`; agents such as
`net.agent1@example.com`, `hw.agent1@example.com`, `access.agent1@example.com`.

To run the pipeline against arbitrary text without the UI or a stored ticket:

```bash
uv run python manage.py triage_demo "My VPN keeps disconnecting every few minutes"
```

## Layout

```
backend/
  config/      settings (all values from .env), urls, health check, Celery app
  accounts/    custom User model - email login, role, team
  tickets/     Team, Category, SLAPolicy, Ticket, Comment, AuditLog, Notification, AIResult;
               views, permissions, services/ (routing, sla, workflow, notifications)
  ai/          pipeline.py (triage), decide.py, embedding/rerank/LLM clients,
               dataset download/clean/index commands, KB seed/add/remove
frontend/src/  api/ (client, types, query hooks), components/, pages/
data/          raw/, processed/ - gitignored, produced by the ai management commands
docker-compose.yml
```

## Testing

```bash
cd backend && uv run pytest      # role isolation, SLA, routing, workflow, confirm flow,
                                  # KB eligibility, triage() decision logic - 72 tests
cd frontend && npm run build     # type-check plus production build
cd frontend && npm run lint      # oxlint
```

## Status

| Phase | Scope | State |
|---|---|---|
| 0 | Setup: Docker Compose, Django and Vite skeletons | Done |
| 1 | Backend core: models, JWT, roles/permissions, routing, SLA, status workflow, audit log, seed command | Done |
| 2 | Data: download, clean, mask PII, index roughly 23,600 tickets into Qdrant | Done |
| 3 | AI pipeline: `triage()` end to end, `triage_demo` CLI | Done |
| 4 | Wiring: Celery task on ticket creation, confirm flow, notifications, add/remove KB | Done |
| 5 | Frontend: login, new ticket, my tickets, agent queue, ticket detail, analytics | Built and verified against the live API; not yet checked in a browser |
| 6 | Analytics and deploy: seeded demo volume, SQL-level aggregates, Dockerfiles, CI, app containers | Not started |
| 7 | Evaluation: RAGAS and scikit-learn metrics on a held-out set, tune `RERANK_THRESHOLD`, CI quality gate | Not started |

Two defects were found and fixed during development, both covered by regression tests now: a
boolean read from a form-encoded request body that made `{"resolved": false}` evaluate as true,
and a serializer that returned internal, agent-only comments to the ticket's own employee.

## Out of scope for v1

Groundedness checking beyond the citation check, comparing TF-IDF against the LLM classifier,
local models through Ollama, asking the employee follow-up questions when information is missing,
satisfaction ratings, detecting incidents from clusters of similar tickets, multi-tenancy, billing.
