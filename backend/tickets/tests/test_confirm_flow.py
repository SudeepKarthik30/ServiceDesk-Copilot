import pytest
from rest_framework import status

from conftest import auth
from tickets.models import Notification, Ticket, TicketStatus


@pytest.fixture
def ai_answered_ticket(db, employee, category):
    return Ticket.objects.create(
        employee=employee,
        title="VPN drops",
        description="...",
        category=category,
        team=category.team,
        status=TicketStatus.AI_ANSWERED,
    )


@pytest.mark.django_db
def test_confirm_resolved_marks_ticket_resolved(api_client, ai_answered_ticket, employee):
    client = auth(api_client, employee)
    response = client.post(
        f"/api/tickets/{ai_answered_ticket.id}/confirm/", {"resolved": True}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    ai_answered_ticket.refresh_from_db()
    assert ai_answered_ticket.status == TicketStatus.RESOLVED


@pytest.mark.django_db
def test_confirm_not_resolved_routes_to_agent_and_notifies(api_client, ai_answered_ticket, employee, agent):
    client = auth(api_client, employee)
    response = client.post(
        f"/api/tickets/{ai_answered_ticket.id}/confirm/", {"resolved": False}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    ai_answered_ticket.refresh_from_db()
    assert ai_answered_ticket.status == TicketStatus.ASSIGNED
    assert ai_answered_ticket.assigned_agent == agent
    assert Notification.objects.filter(recipient=agent, ticket=ai_answered_ticket).exists()


@pytest.mark.django_db
def test_only_ticket_owner_can_confirm(api_client, ai_answered_ticket, other_employee):
    client = auth(api_client, other_employee)
    response = client.post(f"/api/tickets/{ai_answered_ticket.id}/confirm/", {"resolved": True})
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_agent_cannot_confirm(api_client, ai_answered_ticket, agent):
    client = auth(api_client, agent)
    response = client.post(f"/api/tickets/{ai_answered_ticket.id}/confirm/", {"resolved": True})
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_cannot_confirm_ticket_not_awaiting_confirmation(api_client, employee):
    ticket = Ticket.objects.create(employee=employee, title="x", description="y", status=TicketStatus.NEW)
    client = auth(api_client, employee)
    response = client.post(f"/api/tickets/{ticket.id}/confirm/", {"resolved": True})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
