import pytest

from ai import pipeline
from tickets.models import AIDecision, Notification, Ticket, TicketStatus
from tickets.services.workflow import transition


@pytest.fixture
def triaging_ticket(db, employee, category):
    ticket = Ticket.objects.create(employee=employee, title="VPN drops", description="Keeps dropping.")
    transition(ticket, TicketStatus.TRIAGING)
    return ticket


def _patch_ai_steps(monkeypatch, *, category_name, urgency, can_solve, confidence, score):
    monkeypatch.setattr(pipeline, "classify", lambda text, names: {"category": category_name, "urgency": urgency})
    monkeypatch.setattr(pipeline, "rewrite_query", lambda text: text)
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(
        pipeline, "rerank", lambda *a, **k: [{"id": 1, "score": score, "subject": "s", "body": "b", "resolution": "r"}]
    )
    monkeypatch.setattr(
        pipeline,
        "solve",
        lambda text, top5: {
            "can_solve": can_solve,
            "confidence": confidence,
            "steps": [{"text": "do it", "source": "1"}],
        },
    )


@pytest.mark.django_db
def test_triage_auto_answers_and_notifies_team(monkeypatch, triaging_ticket, category, agent):
    _patch_ai_steps(monkeypatch, category_name="VPN Access", urgency="P2", can_solve=True, confidence="high", score=0.9)

    result = pipeline.triage(triaging_ticket)
    triaging_ticket.refresh_from_db()

    assert result.decision == AIDecision.AUTO_ANSWER
    assert triaging_ticket.status == TicketStatus.AI_ANSWERED
    assert triaging_ticket.category == category
    assert triaging_ticket.team == category.team
    assert Notification.objects.filter(recipient=agent, ticket=triaging_ticket).exists()


@pytest.mark.django_db
def test_triage_escalates_p1_and_notifies_agent(monkeypatch, triaging_ticket, agent):
    _patch_ai_steps(monkeypatch, category_name="VPN Access", urgency="P1", can_solve=True, confidence="high", score=0.9)

    result = pipeline.triage(triaging_ticket)
    triaging_ticket.refresh_from_db()

    assert result.decision == AIDecision.ESCALATE
    assert result.reasons == ["urgency_p1"]
    assert triaging_ticket.status == TicketStatus.ASSIGNED
    assert triaging_ticket.assigned_agent == agent
    assert Notification.objects.filter(recipient=agent, ticket=triaging_ticket).exists()


@pytest.mark.django_db
def test_triage_handles_ai_error_gracefully(monkeypatch, triaging_ticket):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(pipeline, "classify", boom)

    result = pipeline.triage(triaging_ticket)
    triaging_ticket.refresh_from_db()

    assert result.decision == AIDecision.ESCALATE
    assert result.reasons == ["ai_error: network down"]
    assert triaging_ticket.category is None
    assert triaging_ticket.status == TicketStatus.TRIAGING  # unrouted - no category to route to
