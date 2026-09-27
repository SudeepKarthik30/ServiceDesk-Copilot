import pytest
from rest_framework import status

from conftest import auth


@pytest.mark.django_db
def test_ticket_without_category_dispatches_triage_task(api_client, employee, monkeypatch):
    called = {}
    monkeypatch.setattr(
        "tickets.views.run_triage_task.delay", lambda ticket_id: called.update(ticket_id=ticket_id)
    )

    client = auth(api_client, employee)
    response = client.post(
        "/api/tickets/", {"title": "Something's wrong", "description": "Help", "urgency": "P3"}
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert called["ticket_id"] == response.data["id"]


@pytest.mark.django_db
def test_ticket_with_category_does_not_dispatch_triage_task(api_client, employee, category, monkeypatch):
    called = {}
    monkeypatch.setattr(
        "tickets.views.run_triage_task.delay", lambda ticket_id: called.update(ticket_id=ticket_id)
    )

    client = auth(api_client, employee)
    response = client.post(
        "/api/tickets/",
        {"title": "VPN down", "description": "...", "category": category.id, "urgency": "P2"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert called == {}
