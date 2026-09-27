import pytest

from tickets.models import Ticket, TicketStatus
from tickets.services.workflow import InvalidTransition, transition


@pytest.fixture
def ticket(db, employee):
    return Ticket.objects.create(employee=employee, title="Can't connect to VPN", description="...")


@pytest.mark.django_db
def test_new_ticket_can_move_to_triaging(ticket):
    transition(ticket, TicketStatus.TRIAGING)
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.TRIAGING


@pytest.mark.django_db
def test_illegal_transition_is_rejected(ticket):
    with pytest.raises(InvalidTransition):
        transition(ticket, TicketStatus.RESOLVED)
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.NEW


@pytest.mark.django_db
def test_resolved_sets_resolved_at(ticket):
    transition(ticket, TicketStatus.TRIAGING)
    transition(ticket, TicketStatus.ASSIGNED)
    transition(ticket, TicketStatus.IN_PROGRESS)
    transition(ticket, TicketStatus.RESOLVED)
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.RESOLVED
    assert ticket.resolved_at is not None


@pytest.mark.django_db
def test_reopened_clears_resolved_and_closed_at(ticket):
    transition(ticket, TicketStatus.TRIAGING)
    transition(ticket, TicketStatus.ASSIGNED)
    transition(ticket, TicketStatus.IN_PROGRESS)
    transition(ticket, TicketStatus.RESOLVED)
    transition(ticket, TicketStatus.CLOSED)
    transition(ticket, TicketStatus.REOPENED)
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.REOPENED
    assert ticket.resolved_at is None
    assert ticket.closed_at is None


@pytest.mark.django_db
def test_transition_writes_audit_log(ticket):
    transition(ticket, TicketStatus.TRIAGING, actor=ticket.employee)
    log = ticket.audit_logs.latest("created_at")
    assert log.action == "status_changed"
    assert log.metadata == {"from": TicketStatus.NEW, "to": TicketStatus.TRIAGING}
    assert log.actor == ticket.employee
