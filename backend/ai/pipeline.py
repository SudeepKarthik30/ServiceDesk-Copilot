"""Single entry point: triage(ticket). See CLAUDE.md "How triage works" for the step-by-step spec.

Expects `ticket` to already be in TRIAGING status (tickets/views.py does this on create). Mutates
the ticket (category, urgency, team, status) and returns the saved AIResult row.
"""

import math
import time

from django.conf import settings
from qdrant_client import models as qm

from ai.decide import decide
from ai.embeddings import get_dense_model, get_sparse_model
from ai.llm import chat_json
from ai.qdrant_client import get_client
from ai.reranker import get_reranker
from tickets.models import AIDecision, AIResult, Category, TicketStatus
from tickets.services.notifications import notify_team
from tickets.services.routing import route_ticket
from tickets.services.workflow import transition

RETRIEVE_TOP_K = 10
RERANK_TOP_K = 5

RETRIEVE_FILTER = qm.Filter(
    must=[
        qm.FieldCondition(key="resolved", match=qm.MatchValue(value=True)),
        qm.FieldCondition(key="restricted", match=qm.MatchValue(value=False)),
        qm.FieldCondition(key="language", match=qm.MatchValue(value="en")),
    ]
)


def classify(ticket_text, category_names):
    system = (
        "You are an IT helpdesk ticket classifier. Choose exactly one category from the given "
        "list and an urgency level. P1 = critical outage blocking many people or all work, "
        "P2 = high-impact single-user blocker, P3 = normal issue, P4 = low priority/cosmetic/request. "
        'Respond with JSON only: {"category": "<one of the given categories>", '
        '"urgency": "P1"|"P2"|"P3"|"P4"}.'
    )
    user = f"Categories: {', '.join(category_names)}\n\nTicket:\n{ticket_text}"
    result = chat_json(settings.LLM_MODEL_FAST, system, user)

    if result.get("category") not in category_names:
        raise ValueError(f"unknown category from LLM: {result.get('category')!r}")
    if result.get("urgency") not in {"P1", "P2", "P3", "P4"}:
        raise ValueError(f"unknown urgency from LLM: {result.get('urgency')!r}")
    return {"category": result["category"], "urgency": result["urgency"]}


def rewrite_query(ticket_text):
    system = (
        "Rewrite the following IT helpdesk ticket into a short, clean search query capturing the "
        "core technical problem, stripped of pleasantries and personal details. "
        'Respond with JSON only: {"query": "<rewritten query>"}.'
    )
    result = chat_json(settings.LLM_MODEL_FAST, system, ticket_text)
    return result.get("query") or ticket_text


def retrieve(original_text, rewritten_query, top_k=RETRIEVE_TOP_K):
    """Dense(original) + dense(rewritten) + BM25(original), merged and deduped by point id.
    No category filter - see CLAUDE.md, retrieval casts a wide net and reranking narrows it."""
    client = get_client()
    dense_model = get_dense_model()
    sparse_model = get_sparse_model()

    dense_original = next(dense_model.query_embed(original_text))
    dense_rewritten = next(dense_model.query_embed(rewritten_query))
    sparse_original = next(sparse_model.query_embed(original_text))

    def search(vector_name, vector):
        return client.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=vector,
            using=vector_name,
            query_filter=RETRIEVE_FILTER,
            limit=top_k,
            with_payload=True,
        ).points

    hits = [
        *search("dense", dense_original.tolist()),
        *search("dense", dense_rewritten.tolist()),
        *search(
            "sparse",
            qm.SparseVector(indices=sparse_original.indices.tolist(), values=sparse_original.values.tolist()),
        ),
    ]

    deduped = {}
    for hit in hits:
        deduped.setdefault(hit.id, hit)
    return list(deduped.values())


def rerank(query, candidates, top_k=RERANK_TOP_K):
    """Cross-encoder over (query, candidate problem text). The model returns raw logits, not
    probabilities, so we sigmoid them to land in [0, 1] and compare against RERANK_THRESHOLD."""
    if not candidates:
        return []

    texts = [f"{c.payload['subject']}\n{c.payload['body']}" for c in candidates]
    raw_scores = list(get_reranker().rerank(query, texts))

    scored = [
        {
            "id": candidate.id,
            "score": 1 / (1 + math.exp(-raw)),
            "subject": candidate.payload["subject"],
            "body": candidate.payload["body"],
            "resolution": candidate.payload["resolution"],
        }
        for candidate, raw in zip(candidates, raw_scores)
    ]
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_k]


def solve(ticket_text, top5):
    if not top5:
        return {"can_solve": False, "confidence": "low", "steps": []}

    context = "\n\n".join(
        f"[{c['id']}] Problem: {c['subject']}\n{c['body']}\nResolution: {c['resolution']}" for c in top5
    )
    system = (
        "You are an IT helpdesk assistant. You are given a new ticket and up to 5 similar past "
        "resolved tickets with their resolutions. Using ONLY the information in those past tickets, "
        "decide whether you can solve the new ticket and, if so, write clear steps. Every step must "
        "cite the id of the past ticket it is based on. Do not invent information that isn't in the "
        "provided past tickets. "
        'Respond with JSON only: {"can_solve": true|false, "confidence": "high"|"medium"|"low", '
        '"steps": [{"text": "<step>", "source": "<id>"}]}.'
    )
    user = f"New ticket:\n{ticket_text}\n\nSimilar past tickets:\n{context}"
    return chat_json(settings.LLM_MODEL, system, user)


def triage(ticket):
    start = time.monotonic()
    ticket_text = f"{ticket.title}\n\n{ticket.description}"
    category_names = list(Category.objects.values_list("name", flat=True))

    classification = None
    rewritten = None
    candidates = []
    reranked = []
    answer = None
    ai_error = None

    try:
        classification = classify(ticket_text, category_names)
        rewritten = rewrite_query(ticket_text)
        candidates = retrieve(ticket_text, rewritten)
        reranked = rerank(rewritten, candidates)
        answer = solve(ticket_text, reranked)
    except Exception as exc:  # any AI/retrieval error -> escalate, never crash the caller
        ai_error = str(exc)

    category = None
    if classification is not None:
        category = Category.objects.filter(name=classification["category"]).first()
        ticket.category = category
        ticket.urgency = classification["urgency"]
        ticket.save(update_fields=["category", "urgency", "updated_at"])

    decision, reasons = decide(
        ai_error=ai_error,
        top5=reranked,
        answer=answer,
        category=category,
        urgency=ticket.urgency,
        threshold=settings.RERANK_THRESHOLD,
    )

    if decision == AIDecision.AUTO_ANSWER:
        ticket.team = category.team
        ticket.save(update_fields=["team", "updated_at"])
        transition(ticket, TicketStatus.AI_ANSWERED)
        notify_team(category.team, ticket, f'Ticket #{ticket.id} "{ticket.title}" was auto-answered by AI.')
    else:
        route_ticket(ticket)

    latency_ms = int((time.monotonic() - start) * 1000)

    return AIResult.objects.create(
        ticket=ticket,
        classify_input={"ticket_text": ticket_text, "rewritten_query": rewritten},
        candidates=[{"id": hit.id, "subject": hit.payload.get("subject")} for hit in candidates],
        scores=[{"id": c["id"], "score": c["score"]} for c in reranked],
        answer=answer or {},
        decision=decision,
        reasons=reasons,
        latency_ms=latency_ms,
    )
