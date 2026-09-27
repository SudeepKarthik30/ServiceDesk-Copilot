# ServiceDesk Copilot

An AI-powered IT helpdesk web app.

An employee raises a ticket. If the AI is confident and the ticket is safe, it **solves the ticket directly**. If not, it **routes the ticket to the right IT team with a suggested fix**. The IT team can see every ticket.

---

## 1. Why this project

Most IT tickets are repeats: password resets, VPN issues, printer problems, access requests. Agents spend a lot of time answering questions that were already solved before.

ServiceDesk Copilot does three things:

1. **Solves simple, repeated problems instantly** using fixes from past resolved tickets.
2. **Routes everything else** to the right team and the least-busy agent, with a suggested fix attached.
3. **Keeps humans in control.** The AI only auto-answers when strict safety rules pass. Anything risky, urgent, or uncertain goes to a person.

The project is built to show **production full-stack skills** (Django, Postgres, React, async jobs, Docker, deployment) around an **AI core** (RAG with hybrid search, reranking, and a rule-based safety gate).

---

## 2. Users and roles

| Role | What they can do |
|---|---|
| **Employee** | Raise tickets, see their own tickets, accept or reject an AI fix (✅ Fixed / ❌ Didn't work), comment |
| **Agent** | See their team's queue, work on tickets, change status, see the AI suggestion and similar past tickets, add resolved tickets to the knowledge base |
| **Admin** | Everything an agent can do, across all teams, plus analytics and configuration |

Login is by email and password. Auth uses JWT tokens (access token: 30 min, refresh token: 7 days).

---

## 3. How it works (end to end)

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

### Ticket statuses

```
NEW → TRIAGING → AI_ANSWERED | ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED
                                                  (+ REOPENED)
```

Every status change is written to an **audit log**.

### Routing

`category → team → least-loaded agent on that team`

### SLA

Each ticket gets a due time from an **SLA policy** based on `category × urgency` (for example, P1 network issue = N minutes). This drives overdue tracking and analytics.

---

## 4. The AI pipeline

A single entry point: `backend/ai/pipeline.py → triage(ticket)`. The app, the demo command, and the evaluation all call this same function.

| Step | What happens |
|---|---|
| **1. Classify** | LLM returns `{category, urgency}` as JSON. This decides the team and the agent. |
| **2. Rewrite** | LLM rewrites the ticket into a clean search query. We search with both the original and the rewritten text. |
| **3. Retrieve** | Qdrant hybrid search: dense(original) top 10 + dense(rewritten) top 10 + BM25 keyword top 10 → merge and dedupe by ticket id. Filter: resolved, non-restricted, English. No hard category filter (so a wrong category guess doesn't hide the right answer). |
| **4. Rerank** | A cross-encoder scores each candidate against the ticket → keep the top 5 with scores. |
| **5. Solve** | LLM writes a fix using **only** those top 5 tickets → `{can_solve, confidence: high/medium/low, steps: [{text, source}]}`. Every step must cite its source ticket. |
| **6. Decide** | A pure Python function (`decide.py`) applies the safety rules below. |
| **7. Save** | An `AIResult` row stores the inputs, candidates, scores, answer, decision, reasons, and latency. |

### Auto-answer rules (all must pass)

- Top rerank score ≥ `RERANK_THRESHOLD`
- `can_solve` is true
- `confidence == "high"`
- Every step cites one of the top 5 retrieved tickets
- The category is marked `safe_to_auto_solve`
- Urgency is not P1

If any rule fails, the ticket is escalated. **Any AI error (timeout, bad JSON, API failure) also means escalate.** The system fails safe.

### Why the pipeline is built this way

- **Hybrid search (dense + BM25):** dense vectors catch meaning ("can't log in" ≈ "authentication failed"); BM25 catches exact terms (error codes, product names).
- **Query rewrite:** employee tickets are messy. A cleaned-up query improves recall.
- **Reranker:** a cross-encoder is much more precise than vector similarity for picking the final top 5.
- **Rule-based decision:** the final call is plain, testable code, not the LLM's opinion. Easy to explain and easy to tune.
- **Citations:** every step links to a real past ticket, so agents and employees can check where the fix came from.

---

## 5. Knowledge base (human-curated learning)

The system gets better over time, but **only through human review**:

- On a `RESOLVED` ticket, an agent or admin clicks **Add to KB**.
- They edit the text → PII is masked → the text is embedded → upserted into Qdrant → the ticket is marked `added_to_kb`.
- AI-solved tickets are only eligible if the employee clicked ✅.
- There is also a **Remove from KB** action.

Nothing enters the knowledge base automatically.

---

## 6. Data

### Datasets

| Dataset | Source | Used for |
|---|---|---|
| **Customer support tickets** | Hugging Face: [`Tobi-Bueck/customer-support-tickets`](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets) | Knowledge base (indexed into Qdrant) + held-out eval set |
| **Demo tickets** | Generated locally by a seed command | Analytics charts and demo data |
| **"Must escalate" tickets** | Generated with an LLM (~20) | Safety evaluation |

### How to download

Open the dataset page, check the files and license, then download it into `data/raw/` in one of these ways.

**Option A: Python (`datasets` library)**

```python
from datasets import load_dataset

ds = load_dataset("Tobi-Bueck/customer-support-tickets")
ds["train"].to_csv("data/raw/customer_support_tickets.csv")
```

**Option B: Hugging Face CLI**

```bash
pip install -U huggingface_hub
huggingface-cli download Tobi-Bueck/customer-support-tickets --repo-type dataset --local-dir data/raw/customer-support-tickets
```

**Option C: Manual.** Download the files from the dataset page's **Files and versions** tab and put them in `data/raw/`.

Models (`bge-small`, `bm25`, the reranker) are downloaded automatically by `fastembed` on first use, so there's nothing to download manually.

### Processing (Phase 2)

`data/raw/` → clean → `data/processed/` → index into Qdrant:

- Keep English tickets that have a real answer
- Remove duplicates
- Mask emails, phone numbers, and IP addresses
- Map the dataset's queues to our categories
- Hold out ~100 tickets for evaluation (these are **not** indexed)
- One ticket = one Qdrant point (the vector is the problem text; the payload holds the resolution)

`data/raw/`, `data/processed/`, and the model caches are gitignored and never committed.

---

## 7. Data model (Django)

| Model | Purpose |
|---|---|
| `User` | Email login, `role` (employee / agent / admin), `team` |
| `Team` | An IT team (e.g. Network, Access, Hardware) |
| `Category` | Ticket category, linked to a team, with a `safe_to_auto_solve` flag |
| `SLAPolicy` | `category × urgency → minutes` |
| `Ticket` | The ticket itself: text, status, category, urgency, assignee, SLA due time, `added_to_kb` |
| `Comment` | Conversation on a ticket |
| `AuditLog` | Who changed what, and when |
| `Notification` | In-app alerts for agents and employees |
| `AIResult` | Full record of each AI triage run |

---

## 8. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind v4 | Modern, fast, typed |
| Frontend libs | TanStack Query, React Router, axios, Recharts | Data fetching/caching, routing, HTTP, charts |
| Frontend lint | oxlint | Very fast linter |
| Backend | Python 3.12, Django 5, Django REST Framework | Batteries included: ORM, admin, auth, migrations |
| Auth | SimpleJWT | Stateless tokens for a React SPA |
| Package manager | `uv` | Fast, reproducible Python installs |
| Database | PostgreSQL 16 | Reliable relational DB, good for analytics with SQL aggregates |
| Background jobs | Celery + Redis | AI triage runs in the background so ticket creation stays fast |
| Vector DB | Qdrant (collection `resolved_tickets`) | Named vectors: `dense` (384d) + `sparse` (BM25) in one collection |
| Embeddings | fastembed `BAAI/bge-small-en-v1.5` | Small, accurate, runs on CPU with ONNX (no PyTorch) |
| Keyword search | fastembed `Qdrant/bm25` | Sparse vectors for exact-term matching |
| Reranker | fastembed `Xenova/ms-marco-MiniLM-L-6-v2` | Lightweight cross-encoder |
| LLM | Open-source models on **Groq**: `openai/gpt-oss-120b` (main), `openai/gpt-oss-20b` (fast) | Fast and cheap. Called through the OpenAI-compatible SDK, so switching provider is just an env var change |
| Containers | Docker Compose | Same setup locally and in deployment |
| Deploy | Render / Railway + Qdrant Cloud | Simple hosting |
| CI | GitHub Actions | Tests + eval gate on every push |

No LangChain or LangGraph. The pipeline is plain Python modules, easy to read and debug.

---

## 9. Architecture

```
┌──────────────┐      /api       ┌───────────────────┐       ┌──────────────┐
│ React (Vite) │ ──────────────► │ Django + DRF      │ ────► │ PostgreSQL   │
│  SPA         │ ◄────────────── │ (JWT auth)        │       └──────────────┘
└──────────────┘                 └─────────┬─────────┘
                                           │ enqueue triage
                                           ▼
                                 ┌───────────────────┐       ┌──────────────┐
                                 │ Redis (broker)    │ ────► │ Celery worker│
                                 └───────────────────┘       └──────┬───────┘
                                                                    │ triage()
                                              ┌─────────────────────┼─────────────────┐
                                              ▼                     ▼                 ▼
                                      ┌──────────────┐     ┌────────────────┐  ┌─────────────┐
                                      │ Qdrant       │     │ fastembed      │  │ Groq LLM    │
                                      │ dense+sparse │     │ embed / rerank │  │ (gpt-oss)   │
                                      └──────────────┘     └────────────────┘  └─────────────┘
```

---

## 10. Repo layout

```
backend/
  config/      settings (all config from .env), urls, health view, Celery app
  accounts/    custom User model
  tickets/     tickets, teams, categories, SLA, comments, audit log, notifications
  ai/          pipeline.py, decide.py, retrieval, rerank, LLM client
frontend/src/  React app
data/          raw/ + processed/ (gitignored)
docker-compose.yml
```

All settings come from `backend/.env`. Every variable is documented in `backend/.env.example`. Secrets are never committed.

---

## 11. Frontend pages

- **Login**
- **New ticket**: employee raises a ticket
- **My tickets**: employee's tickets, with the AI fix and ✅ / ❌ buttons
- **Agent queue**: team tickets, filters, SLA status
- **Ticket detail**: conversation, status changes, AI suggestion, similar tickets, Add/Remove KB
- **Analytics**: ticket volume, auto-answer rate, SLA breaches, per-team load (charts)

---

## 12. Build plan

| Phase | Goal | Main work |
|---|---|---|
| **0. Setup** | Project skeleton | Git, Docker Compose (Postgres, Redis, Qdrant), Django + Vite skeletons |
| **1. Backend core** | A working helpdesk without AI | Models, JWT, roles and permissions, routing, SLA, status workflow, audit log, seed command, tests (role isolation, SLA, routing, workflow) |
| **2. Data + Qdrant** | A searchable knowledge base | Download, clean, mask, map categories, index into Qdrant |
| **3. AI pipeline** | `triage()` works end to end | Classify, rewrite, retrieve, rerank, solve, decide, save; `manage.py triage_demo "<text>"` to try it from the terminal |
| **4. Wiring** | AI connected to the app | Celery task on ticket create, ✅ / ❌ confirm flow, notifications, add/remove KB |
| **5. Frontend** | Usable UI | All pages listed above |
| **6. Analytics + deploy** | Live and shareable | Seed data, SQL aggregates, charts, Dockerfiles, CI, README |
| **7. Evaluation** | Measured, honest numbers | See below |

---

## 13. Evaluation plan

Done after the system is built, using the **same `triage()` function the app uses**.

- **Test set:** ~100 held-out dataset tickets (not indexed), using their existing labels and answers as ground truth, plus ~20 LLM-generated "must escalate" tickets (risky, urgent, or out-of-scope).
- **Metrics:**
  - RAGAS: faithfulness, answer relevancy, context metrics
  - scikit-learn: category and urgency classification accuracy / F1
  - Plain Python: auto-answer precision and **unsafe auto-answers (target: 0)**
- **Tuning:** pick `RERANK_THRESHOLD` from the results.
- **CI gate:** a pytest check that fails the build if quality drops.
- Only real measured numbers go in the README.

---

## 14. Running locally

```bash
docker compose up -d                                  # postgres, redis, qdrant
cd backend && cp .env.example .env                    # first time; fill in LLM_API_KEY etc.
cd backend && uv sync                                 # install backend deps
cd backend && uv run python manage.py migrate
cd backend && uv run python manage.py runserver       # http://localhost:8000/api/health/
cd backend && uv run pytest                           # backend tests
cd backend && uv run celery -A config worker -P solo -l info   # worker (-P solo on Windows)
cd frontend && npm install && npm run dev             # http://localhost:5173
cd frontend && npm run build                          # type-check + production build
cd frontend && npm run lint                           # oxlint
```

---

## 15. Out of scope for v1 (later)

- Groundedness checker
- TF-IDF vs LLM classification comparison
- Local models via Ollama
- Asking the employee follow-up questions when info is missing
- Knowledge base articles
- Satisfaction ratings
- Incident detection (many similar tickets at once)
- Multi-tenant / billing
