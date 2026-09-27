import pytest

from accounts.models import User
from tickets.models import Notification, Ticket, TicketStatus
from tickets.services.routing import pick_least_loaded_agent, route_ticket
from tickets.services.workflow import transition


@pytest.fixture
def busy_agent(db, team):
    return User.objects.create_user(
        email="busy-agent@test.com", password="pass12345", role=User.Role.AGENT, team=team
    )


@pytest.mark.django_db
def test_route_ticket_is_a_noop_without_category(employee):
    ticket = Ticket.objects.create(employee=employee, title="No category yet", description="...")
    route_ticket(ticket)
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.NEW
    assert ticket.team is None
    assert ticket.assigned_agent is None


@pytest.mark.django_db
def test_route_ticket_assigns_team_and_computes_sla(employee, category, sla_policy):
    ticket = Ticket.objects.create(
        employee=employee, title="VPN down", description="...", category=category, urgency=sla_policy.urgency
    )
    transition(ticket, TicketStatus.TRIAGING)
    route_ticket(ticket)
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.ASSIGNED
    assert ticket.team == category.team
    assert ticket.sla_due_at is not None


@pytest.mark.django_db
def test_route_ticket_picks_least_loaded_agent(employee, category, agent, busy_agent):
    # Give `agent` two open tickets and `busy_agent` none - the new ticket should go to `busy_agent`... wait,
    # naming: `agent` becomes the busy one here since it already has open tickets.
    for _ in range(2):
        existing = Ticket.objects.create(
            employee=employee, title="Existing", description="...", category=category,
            team=category.team, assigned_agent=agent, status=TicketStatus.ASSIGNED,
        )
        assert existing.assigned_agent == agent

    ticket = Ticket.objects.create(employee=employee, title="New ticket", description="...", category=category)
    transition(ticket, TicketStatus.TRIAGING)
    route_ticket(ticket)
    ticket.refresh_from_db()

    assert ticket.assigned_agent == busy_agent


@pytest.mark.django_db
def test_pick_least_loaded_agent_returns_none_without_team():
    assert pick_least_loaded_agent(None) is None


@pytest.mark.django_db
def test_route_ticket_logs_routing_decision(employee, category, agent):
    ticket = Ticket.objects.create(employee=employee, title="VPN down", description="...", category=category)
    transition(ticket, TicketStatus.TRIAGING)
    route_ticket(ticket, actor=agent)
    log = ticket.audit_logs.get(action="ticket_routed")
    assert log.metadata["team_id"] == category.team_id
    assert log.metadata["agent_id"] == agent.id


@pytest.mark.django_db
def test_route_ticket_notifies_the_assigned_agent(employee, category, agent):
    ticket = Ticket.objects.create(employee=employee, title="VPN down", description="...", category=category)
    transition(ticket, TicketStatus.TRIAGING)
    route_ticket(ticket)
    assert Notification.objects.filter(recipient=agent, ticket=ticket).exists()
