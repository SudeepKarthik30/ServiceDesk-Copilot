# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: ServiceDesk Copilot

An IT helpdesk web app. An employee raises a ticket. If the AI pipeline is confident and the ticket is safe, it **solves the ticket directly**. Otherwise it **routes the ticket to the right IT team with a suggested fix**. IT can see every ticket.

Builder context: final-year B.Tech CS student targeting AI/GenAI roles (Cognizant, HCLTech, Accenture + startups). The project exists to prove **production full-stack skills** (Django, Postgres, React, async jobs, Docker, deployment) around an AI core. Keep it simple: the user explicitly asked not to over-complicate. Anything not in this file is out of scope for v1.

## Current status

**Phases 0-4 are done. Phase 5 is built but not yet visually verified in a browser** (see note below). What exists today:
- `docker-compose.yml`: Postgres 16, Redis 7, Qdrant (infra only; app containers come in Phase 6).
- `backend/config/`: settings, Celery app, `/api/health/` view, JWT auth endpoints (`/api/auth/token/`, `/api/auth/token/refresh/`), `/api/` wired to the `tickets` app router.
- `backend/accounts/`: custom `User` model — email login, no username, `role` (`employee`\|`agent`\|`admin`), and `team` (FK to `tickets.Team`, nullable — set on agents, null for employees/admins).
- `backend/tickets/`: models `Team`, `Category` (with `safe_to_auto_solve`), `SLAPolicy` (category × urgency → `resolve_minutes`), `Ticket`, `Comment` (with `is_internal` for agent-only notes), `AuditLog`, `Notification`, `AIResult`. DRF viewsets for all of them behind role-based permissions (`tickets/permissions.py`); `tickets/services/`: `routing.py` (category → team → least-loaded agent), `sla.py` (SLA due-date calc), `workflow.py` (status state machine + `AuditLog` writes on every transition). `manage.py seed` creates demo teams/categories/SLA policies/users.
- Ticket visibility: employees see only their own tickets, agents see tickets on their team or assigned to them, admins see everything. Status/role transition rules are enforced in `tickets/views.py`. `perform_create` transitions a new ticket straight to `TRIAGING`, then either routes it immediately (category already set) or dispatches `ai.tasks.run_triage_task.delay(ticket.id)` (category not set - the normal employee path). `tickets/services/notifications.py` (`notify_agent`, `notify_team`) is called from `routing.route_ticket()` (whoever gets assigned) and from `pipeline.py`'s auto-answer branch (the whole team, since no one agent owns it). The employee-facing ✅/❌ flow is `POST /api/tickets/{id}/confirm/` (`{"resolved": true|false}`) - not the generic `transition` action, which deliberately no longer allows `AI_ANSWERED` transitions for employees, since ❌ needs `route_ticket()` (pick an agent, set SLA), not a bare status flip. `POST /api/tickets/{id}/add_to_kb/` (agent/admin, `RESOLVED` tickets only, blocked for AI-answered tickets unless the employee's ✅ produced the direct `AI_ANSWERED`→`RESOLVED` transition - checked via `AuditLog`) and `remove_from_kb/` upsert/delete a single Qdrant point via `ai/kb.py` (ids `1,000,000 + ticket.id`, namespaced above the dataset and `seed_kb.py` ranges). `TicketDetailSerializer` now includes `ai_results` so the UI can show the AI's answer/citations.
- `backend/ai/`: dataset pipeline (`download_dataset`, `clean_dataset`, `index_dataset` management commands; `category_map.py`, `pii.py`) — `data/processed/tickets.jsonl` is cleaned/deduped/masked and indexed into Qdrant's `resolved_tickets` collection (dense + BM25), `data/processed/eval_holdout.jsonl` is held out for Phase 7. `embeddings.py`/`reranker.py` wrap fastembed via `model_download.py` (see gotcha below — fixed to handle nested `model_file` paths like the cross-encoder's `onnx/model.onnx`). `llm.py` wraps the Groq-compatible OpenAI SDK client. `pipeline.py` implements `triage(ticket)` (classify → rewrite → retrieve → rerank → solve → decide → save `AIResult`, per "How triage works" below) and `decide.py` is the pure auto-answer/escalate decision function. `manage.py triage_demo "<text>"` runs the pipeline on a throwaway ticket (rolled back after) and prints the result. `manage.py seed_kb` upserts ~20 hand-written, genuinely actionable IT helpdesk articles into Qdrant (ids 900001+) - the HF dataset's `resolution` field is mostly generic "please share more details" customer-service replies (~65% of it, by a rough heuristic), not real fixes, so without these the auto-answer path almost never fires. Verified end-to-end with a real Groq key: a VPN-disconnect ticket now correctly `AUTO_ANSWER`s citing a seeded article, and an unsafe/P1 ticket (`Network Outage`) still correctly escalates even when the LLM is confident.
- `frontend/src/`: `api/` (axios instance with JWT access/refresh interceptor in `client.ts`, `auth.tsx` context, per-resource hooks in `tickets.ts`/`lookups.ts`/`notifications.ts`, all typed in `types.ts`), `components/` (`Layout` with the notification bell, `ProtectedRoute` for role gating, `TicketTable`, `StatusBadge`/`UrgencyBadge`), `pages/` (`LoginPage`, `NewTicketPage`, `MyTicketsPage`, `AgentQueuePage`, `TicketDetailPage`, `AnalyticsPage`). Login posts `{email, password}` (the custom `User.USERNAME_FIELD`, not `username`) to `/api/auth/token/`. `TicketDetailPage` shows the AI answer with citations, the ✅/❌ confirm buttons (only to the owning employee while `AI_ANSWERED`), role-filtered workflow transition buttons (`api/workflow.ts` mirrors the backend's per-role transition sets - UX only, the backend still enforces it), and the add/remove-KB form. `AnalyticsPage` computes its charts client-side from the paginated ticket list (walks pages via `useAllTickets`) since there's no aggregate endpoint yet - Phase 6 adds seeded volume and real SQL aggregates. Chart colors follow the dataviz skill's validated categorical/ordinal palettes (validated with `scripts/validate_palette.js`), not ad hoc hex values.
- **Bug found while wiring the frontend, fixed in the backend:** `TicketDetailSerializer` used to embed `comments` directly (a plain `CommentSerializer(many=True)`), which has no way to filter `is_internal` notes by viewer role - unlike the dedicated `GET /tickets/{id}/comments/` action, which does filter them out for employees. That meant an employee fetching the ticket detail page could see agent-only internal notes. Fixed by dropping `comments` from `TicketDetailSerializer` entirely; the frontend fetches comments via the dedicated endpoint instead (`useComments` in `api/tickets.ts`).
- Tests: `backend/conftest.py` + `tickets/tests/` cover SLA calculation, routing (incl. the agent notification), the workflow state machine, role-isolation/permissions, the confirm flow, add/remove-KB eligibility, and that ticket creation dispatches (or doesn't dispatch) the triage task. `ai/tests/` covers PII masking, the dataset cleaning command, category mapping, the `decide()` decision table, and `triage()` end-to-end with the LLM/Qdrant calls monkeypatched (checks both AUTO_ANSWER and ESCALATE notify the right people). All passing (`uv run pytest`, 72 tests). `accounts/tests/` is still empty.
- `LLM_API_KEY` is set in `backend/.env` and the whole pipeline has been verified live against Groq: ticket create → Celery task body → `AUTO_ANSWER`/`ESCALATE` → notifications → employee `confirm` (both ✅ and ❌) → agent `add_to_kb`/`remove_from_kb` against real Qdrant, all by hand (no worker process running yet - Phase 6 adds the Docker services for that; `run_triage_task(id)` called directly bypasses the broker, `.delay()` in the view actually queues to Redis with nothing consuming it until a worker is running).
- Frontend verified via `npm run build` (tsc + vite build, clean), `npm run lint` (oxlint, warnings only), and a full manual API walkthrough matching every request the pages actually send (login, create ticket, list/detail/comments, triage lifecycle, agent queue, transitions, add_to_kb, notification read, login-failure error shape) - **not** verified visually in a browser yet. The Claude in Chrome extension was mid-install this session and a fresh Claude Code session is needed for it to connect (per its own setup note), so no in-browser click-through has been done. Treat the UI as functionally wired but visually unverified until that happens - do an actual browser pass (or ask the user to) before calling Phase 5 fully done.

**Next: Phase 6 (analytics + deploy — seed data, SQL aggregates, charts, Dockerfiles, CI, README).**

## Stack (decided)

| Layer | Choice |
|---|---|
| Frontend | React 19 + TypeScript + Vite + Tailwind v4, TanStack Query, React Router, axios, Recharts; lint = oxlint |
| Backend | Python 3.12, Django 5 + DRF + SimpleJWT (access 30 min, refresh 7 days); roles: `employee`, `agent`, `admin`; deps via `uv` |
| DB | PostgreSQL 16 (via `DATABASE_URL`, parsed with `dj-database-url`) |
| Async | Celery + Redis (`CELERY_TASK_ALWAYS_EAGER=true` runs tasks inline for tests/debug) |
| Vector DB | Qdrant, collection `resolved_tickets`, with named vectors `dense` (bge-small, 384d) + `sparse` (BM25) |
| Embeddings / BM25 / reranker | `fastembed` (ONNX, no torch): `BAAI/bge-small-en-v1.5`, `Qdrant/bm25`, cross-encoder `Xenova/ms-marco-MiniLM-L-6-v2` |
| LLM | **Open-source models via Groq** (no OpenAI). Default `LLM_MODEL=openai/gpt-oss-120b`, `LLM_MODEL_FAST=openai/gpt-oss-20b`. Called through the OpenAI-compatible SDK with `LLM_BASE_URL`, so changing an env var switches provider |
| Deploy | Docker Compose → Render/Railway + Qdrant Cloud; GitHub Actions CI |

No LangChain/LangGraph. Use plain Python modules.

## How triage works (`backend/ai/pipeline.py: triage(ticket)` is the single entry point)

1. **Classify**: LLM → `{category, urgency}` JSON → route: category → team → least-loaded agent.
2. **Rewrite**: LLM rewrites the ticket into a clean search query (original + rewritten = 2 queries).
3. **Retrieve**: Qdrant: dense(original) top 10 + dense(rewritten) top 10 + BM25 top 10 → merge + dedupe by ticket id. Filter: resolved, non-restricted, English. **No hard category filter.**
4. **Rerank**: cross-encoder → top 5 with scores.
5. **Solve**: LLM uses only the top 5 → `{can_solve, confidence: high|medium|low, steps: [{text, source}]}`.
6. **Decide** (`decide.py`, pure function): auto-answer only if: rerank score ≥ `RERANK_THRESHOLD` AND `can_solve` AND `confidence == "high"` AND every step cites one of the top 5 AND category is `safe_to_auto_solve` AND urgency ≠ P1. Otherwise escalate. **Any AI error → escalate.**
7. **Save** an `AIResult` row (inputs, candidates, scores, answer, decision, reasons, latency).

Outcomes:
- **Auto-answer** → status `AI_ANSWERED`; employee sees fix with ✅ Fixed / ❌ Didn't work; IT team gets a notification. ✅ → `RESOLVED`; ❌ → `ASSIGNED` to an agent with the AI attempt attached.
- **Escalate** → `ASSIGNED`; agent is notified and sees the AI suggestion + similar tickets.

**Add to KB (manual, human-curated learning):** agent/admin button on `RESOLVED` tickets → edit text → mask PII → embed → upsert to Qdrant, set `added_to_kb`. AI-solved tickets are only eligible if the employee clicked ✅. There is a remove-from-KB action.

Ticket statuses: `NEW → TRIAGING → AI_ANSWERED | ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED` (+ `REOPENED`).

## Data

- Corpus: Hugging Face `Tobi-Bueck/customer-support-tickets`. Keep English tickets that have a real answer, dedupe them, mask emails/phones/IPs, and map queues → our categories. One ticket = one Qdrant point (vector = problem text; payload holds the resolution).
- Demo analytics: a seed command that generates a few thousand random tickets.
- `data/raw/` and `data/processed/` are gitignored, and so are the fastembed model caches.

## Models (Django)

`User` (role, team) · `Team` · `Category` (team, safe_to_auto_solve) · `SLAPolicy` (category × urgency → minutes) · `Ticket` · `Comment` · `AuditLog` · `Notification` · `AIResult`.

`User` lives in `accounts` (`AUTH_USER_MODEL = "accounts.User"`). Create users with `User.objects.create_user(email, password, role=...)`.

## Repo layout

```
backend/
  config/      settings.py (all config from .env), urls.py, views.py (health), celery.py
  accounts/    custom User model
  tickets/     Team/Category/SLAPolicy/Ticket/Comment/AuditLog/Notification/AIResult models,
               views.py, permissions.py, services/ (routing, sla, workflow), management/commands/seed.py
  ai/          (Phase 3) pipeline.py, decide.py, ...
frontend/src/  React app
data/          raw/ + processed/ (gitignored)
docker-compose.yml
```

## Conventions / gotchas

- **huggingface_hub `/api/models/...` calls are reset on this network** (`httpx.ConnectError: [WinError 10054]`), even though plain file downloads (`huggingface.co/<repo>/resolve/main/<file>`) work fine and so does the `datasets` library. This breaks fastembed's built-in model downloader, which calls `model_info()`/`list_repo_tree()` (both hit `/api/models/...`) with no fallback for that exception type. Fix used throughout `ai/`: `ai/model_download.py` fetches each required file individually with `huggingface_hub.hf_hub_download()` (which only touches `resolve/main/...` and has its own retry/backoff), then hands fastembed the resulting directory via the `specific_model_path=` kwarg, which skips fastembed's own downloader entirely. `ai/embeddings.py` (`get_dense_model()`, `get_sparse_model()`) and `ai/reranker.py` (`get_reranker()`) are the places this is wired up - reuse them rather than constructing `TextEmbedding`/`SparseTextEmbedding`/`TextCrossEncoder` directly. `fetch_model_dir()` must strip the model's *whole* relative `model_file` path (not just its last segment) to find the snapshot root - some models (the cross-encoder reranker) ship `model_file="onnx/model.onnx"` in a subfolder, and fastembed re-joins `specific_model_path / model_file` itself, so stripping only the last segment leaves a stray `onnx/` and fastembed looks for `.../onnx/onnx/model.onnx`.
- **DRF `request.data.get("bool_field")` is not safe to treat as a Python bool** - a JSON body gives you a real `True`/`False`, but a form-encoded body gives you the *string* `"True"`/`"False"`, and `bool("False")` is `True`. `tickets/views.py`'s `confirm` action learned this the hard way (a test posting `{"resolved": False}` without `format="json"` ended up resolving the ticket instead of routing it) - it now does `str(request.data.get("resolved", False)).lower() in ("true", "1")`. Apply the same pattern to any other boolean request field.
- **Cross-encoder rerank scores are raw logits, not probabilities** - `fastembed`'s `TextCrossEncoder.rerank()` (used for `RERANK_MODEL`) does not sigmoid its output. `ai/pipeline.py`'s `rerank()` applies `1 / (1 + exp(-raw))` itself so the score is comparable to `RERANK_THRESHOLD` (a 0-1 value).

- All settings come from `backend/.env` through `os.getenv` in `config/settings.py`. When you add a new variable, add it to `backend/.env.example` too.
- DRF defaults: JWT auth, `IsAuthenticated`, page size 25. Public endpoints must opt out with `@permission_classes([AllowAny])`.
- `TIME_ZONE = "Asia/Kolkata"`, `USE_TZ = True`.
- Dev: the Vite dev server proxies `/api` → `http://127.0.0.1:8000`. Use 127.0.0.1, not localhost, because Node resolves localhost to IPv6. The frontend therefore calls relative `/api/...` URLs, and CORS only matters in prod.
- Docker images for Postgres/Redis are pulled from `mirror.gcr.io` because Docker Hub was unreliable on this machine.
- Dev OS is Windows (PowerShell + Git Bash).

## Build phases

0. ✅ Setup: git, docker-compose (postgres, redis, qdrant), Django + Vite skeletons.
1. ✅ Backend core: models, JWT, roles/permissions, routing, SLA, status workflow, audit log, seed command, targeted tests (role isolation, SLA, routing, workflow).
2. ✅ Data + Qdrant: download, clean, index.
3. ✅ AI pipeline: `triage()` + `manage.py triage_demo "<text>"`.
4. ✅ Wiring: Celery task on ticket create, confirm flow, notifications, add/remove KB.
5. 🟡 Frontend: Login, New ticket, My tickets, Agent queue, Ticket detail, Analytics. Built and API-contract-verified; needs an actual browser click-through before calling it done.
6. Analytics + deploy: seed data, SQL aggregates, charts, Dockerfiles, CI, README.
7. **Evaluation (after the system is built)**: hold out ~100 dataset tickets (not indexed) and use their existing labels/answers as ground truth, plus ~20 LLM-generated "must escalate" tickets. Use RAGAS for faithfulness/relevancy/context metrics, scikit-learn for classification, and plain Python for auto-answer precision and unsafe auto-answers (target 0). Tune `RERANK_THRESHOLD` from the results and add a pytest CI gate. The eval must call the same `triage()` the app uses. Only measured numbers go in the README.

Later / out of v1: groundedness checker, TF-IDF vs LLM comparison, local Ollama, missing-info questions, KB articles, satisfaction ratings, incident detection, multi-tenant/billing.

## Commands

```bash
docker compose up -d                                  # postgres, redis, qdrant
cd backend && cp .env.example .env                    # first time; fill in LLM_API_KEY etc.
cd backend && uv sync                                 # install backend deps
cd backend && uv run python manage.py migrate
cd backend && uv run python manage.py runserver       # http://localhost:8000/api/health/
cd backend && uv run pytest                           # backend tests (pytest-django)
cd backend && uv run celery -A config worker -P solo -l info   # worker (-P solo needed on Windows)
cd frontend && npm install && npm run dev             # http://localhost:5173
cd frontend && npm run build                          # type-check + production build
cd frontend && npm run lint                           # oxlint
```

Secrets live in `backend/.env` (gitignored), and `backend/.env.example` documents every variable. Never commit keys.
