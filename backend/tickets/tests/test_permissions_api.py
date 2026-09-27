import pytest
from rest_framework import status

from conftest import auth
from tickets.models import Ticket, TicketStatus


@pytest.mark.django_db
def test_unauthenticated_request_is_rejected(api_client):
    response = api_client.get("/api/tickets/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_employee_can_create_and_see_own_ticket(api_client, employee, category):
    client = auth(api_client, employee)
    response = client.post(
        "/api/tickets/",
        {"title": "VPN down", "description": "Can't connect", "category": category.id, "urgency": "P2"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    ticket_id = response.data["id"]

    ticket = Ticket.objects.get(pk=ticket_id)
    assert ticket.status == TicketStatus.ASSIGNED
    assert ticket.team == category.team

    detail = client.get(f"/api/tickets/{ticket_id}/")
    assert detail.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_other_employee_cannot_see_ticket(api_client, employee, other_employee, category):
    owner_client = auth(api_client, employee)
    created = owner_client.post(
        "/api/tickets/",
        {"title": "VPN down", "description": "...", "category": category.id, "urgency": "P2"},
    )
    ticket_id = created.data["id"]

    other_client = auth(api_client, other_employee)
    list_response = other_client.get("/api/tickets/")
    assert all(t["id"] != ticket_id for t in list_response.data["results"])

    detail_response = other_client.get(f"/api/tickets/{ticket_id}/")
    assert detail_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_matching_team_agent_can_see_ticket_but_other_team_agent_cannot(
    api_client, employee, category, agent, other_team_agent
):
    owner_client = auth(api_client, employee)
    created = owner_client.post(
        "/api/tickets/",
        {"title": "VPN down", "description": "...", "category": category.id, "urgency": "P2"},
    )
    ticket_id = created.data["id"]

    agent_client = auth(api_client, agent)
    assert agent_client.get(f"/api/tickets/{ticket_id}/").status_code == status.HTTP_200_OK

    other_agent_client = auth(api_client, other_team_agent)
    assert other_agent_client.get(f"/api/tickets/{ticket_id}/").status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_admin_sees_every_ticket(api_client, employee, category, admin_user):
    owner_client = auth(api_client, employee)
    created = owner_client.post(
        "/api/tickets/",
        {"title": "VPN down", "description": "...", "category": category.id, "urgency": "P2"},
    )
    ticket_id = created.data["id"]

    admin_client = auth(api_client, admin_user)
    assert admin_client.get(f"/api/tickets/{ticket_id}/").status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_only_admin_can_create_category(api_client, employee, admin_user, team):
    employee_client = auth(api_client, employee)
    response = employee_client.post("/api/categories/", {"name": "New Cat", "team": team.id})
    assert response.status_code == status.HTTP_403_FORBIDDEN

    admin_client = auth(api_client, admin_user)
    response = admin_client.post("/api/categories/", {"name": "New Cat", "team": team.id})
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_employee_cannot_advance_ticket_to_in_progress(api_client, employee, category, agent):
    owner_client = auth(api_client, employee)
    created = owner_client.post(
        "/api/tickets/",
        {"title": "VPN down", "description": "...", "category": category.id, "urgency": "P2"},
    )
    ticket_id = created.data["id"]

    response = owner_client.post(f"/api/tickets/{ticket_id}/transition/", {"status": "IN_PROGRESS"})
    assert response.status_code == status.HTTP_403_FORBIDDEN

    agent_client = auth(api_client, agent)
    response = agent_client.post(f"/api/tickets/{ticket_id}/transition/", {"status": "IN_PROGRESS"})
    assert response.status_code == status.HTTP_200_OK
