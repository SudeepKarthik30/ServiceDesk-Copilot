import pytest
from rest_framework import status

from conftest import auth
from tickets.models import AIDecision, AIResult, AuditLog, Ticket, TicketStatus
from tickets.services.workflow import transition


@pytest.fixture
def resolved_ticket(db, employee, category, agent):
    return Ticket.objects.create(
        employee=employee,
        title="Printer jam",
        description="Tray 2 is jammed",
        category=category,
        team=category.team,
        assigned_agent=agent,
        status=TicketStatus.RESOLVED,
    )


@pytest.mark.django_db
def test_agent_can_add_resolved_ticket_to_kb(api_client, resolved_ticket, agent, monkeypatch):
    called = {}
    monkeypatch.setattr(
        "tickets.views.upsert_ticket_kb_entry",
        lambda ticket, subject, body, resolution: called.update(
            ticket_id=ticket.id, subject=subject, body=body, resolution=resolution
        ),
    )

    client = auth(api_client, agent)
    response = client.post(
        f"/api/tickets/{resolved_ticket.id}/add_to_kb/",
        {"resolution": "Open tray 2, remove the jammed sheet, close the tray."},
    )

    assert response.status_code == status.HTTP_200_OK
    resolved_ticket.refresh_from_db()
    assert resolved_ticket.added_to_kb is True
    assert called["ticket_id"] == resolved_ticket.id
    assert AuditLog.objects.filter(ticket=resolved_ticket, action="added_to_kb").exists()


@pytest.mark.django_db
def test_add_to_kb_requires_resolved_status(api_client, employee, category, agent, monkeypatch):
    ticket = Ticket.objects.create(
        employee=employee, title="x", description="y", category=category,
        team=category.team, assigned_agent=agent, status=TicketStatus.ASSIGNED,
    )
    monkeypatch.setattr("tickets.views.upsert_ticket_kb_entry", lambda *a, **k: None)

    client = auth(api_client, agent)
    response = client.post(f"/api/tickets/{ticket.id}/add_to_kb/", {"resolution": "fix"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_add_to_kb_requires_resolution_text(api_client, resolved_ticket, agent, monkeypatch):
    monkeypatch.setattr("tickets.views.upsert_ticket_kb_entry", lambda *a, **k: None)
    client = auth(api_client, agent)
    response = client.post(f"/api/tickets/{resolved_ticket.id}/add_to_kb/", {})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_employee_cannot_add_to_kb(api_client, resolved_ticket, employee, monkeypatch):
    monkeypatch.setattr("tickets.views.upsert_ticket_kb_entry", lambda *a, **k: None)
    client = auth(api_client, employee)
    response = client.post(f"/api/tickets/{resolved_ticket.id}/add_to_kb/", {"resolution": "fix"})
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_ai_answered_ticket_ineligible_after_a_didnt_work_click(api_client, employee, category, agent, monkeypatch):
    ticket = Ticket.objects.create(
        employee=employee, title="x", description="y", category=category,
        team=category.team, assigned_agent=agent, status=TicketStatus.AI_ANSWERED,
    )
    AIResult.objects.create(ticket=ticket, decision=AIDecision.AUTO_ANSWER)
    transition(ticket, TicketStatus.ASSIGNED)  # the employee clicked ❌
    transition(ticket, TicketStatus.RESOLVED)  # agent fixed it manually afterwards

    monkeypatch.setattr("tickets.views.upsert_ticket_kb_entry", lambda *a, **k: None)
    client = auth(api_client, agent)
    response = client.post(f"/api/tickets/{ticket.id}/add_to_kb/", {"resolution": "fix"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_ai_answered_ticket_eligible_after_a_fixed_click(api_client, employee, category, agent, monkeypatch):
    ticket = Ticket.objects.create(
        employee=employee, title="x", description="y", category=category,
        team=category.team, status=TicketStatus.AI_ANSWERED,
    )
    AIResult.objects.create(ticket=ticket, decision=AIDecision.AUTO_ANSWER)
    transition(ticket, TicketStatus.RESOLVED)  # the employee clicked ✅ directly

    monkeypatch.setattr("tickets.views.upsert_ticket_kb_entry", lambda *a, **k: None)
    client = auth(api_client, agent)
    response = client.post(f"/api/tickets/{ticket.id}/add_to_kb/", {"resolution": "fix"})
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_remove_from_kb(api_client, resolved_ticket, agent, monkeypatch):
    resolved_ticket.added_to_kb = True
    resolved_ticket.save(update_fields=["added_to_kb"])
    called = {}
    monkeypatch.setattr(
        "tickets.views.remove_ticket_kb_entry", lambda ticket: called.update(ticket_id=ticket.id)
    )

    client = auth(api_client, agent)
    response = client.post(f"/api/tickets/{resolved_ticket.id}/remove_from_kb/")

    assert response.status_code == status.HTTP_200_OK
    resolved_ticket.refresh_from_db()
    assert resolved_ticket.added_to_kb is False
    assert called["ticket_id"] == resolved_ticket.id
    assert AuditLog.objects.filter(ticket=resolved_ticket, action="removed_from_kb").exists()


@pytest.mark.django_db
def test_remove_from_kb_requires_already_added(api_client, resolved_ticket, agent):
    client = auth(api_client, agent)
    response = client.post(f"/api/tickets/{resolved_ticket.id}/remove_from_kb/")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
