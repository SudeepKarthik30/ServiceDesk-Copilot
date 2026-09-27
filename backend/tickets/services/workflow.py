from django.utils import timezone

from tickets.models import AuditLog, TicketStatus

# Ticket statuses: NEW -> TRIAGING -> AI_ANSWERED | ASSIGNED -> IN_PROGRESS -> RESOLVED -> CLOSED (+ REOPENED)
ALLOWED_TRANSITIONS = {
    TicketStatus.NEW: {TicketStatus.TRIAGING},
    TicketStatus.TRIAGING: {TicketStatus.AI_ANSWERED, TicketStatus.ASSIGNED},
    TicketStatus.AI_ANSWERED: {TicketStatus.RESOLVED, TicketStatus.ASSIGNED},
    TicketStatus.ASSIGNED: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED},
    TicketStatus.IN_PROGRESS: {TicketStatus.RESOLVED, TicketStatus.ASSIGNED},
    TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.REOPENED},
    TicketStatus.CLOSED: {TicketStatus.REOPENED},
    TicketStatus.REOPENED: {TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS},
}


class InvalidTransition(Exception):
    pass


def transition(ticket, new_status, actor=None):
    current = ticket.status
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise InvalidTransition(f"Cannot move ticket from {current} to {new_status}")

    now = timezone.now()
    ticket.status = new_status

    if new_status == TicketStatus.RESOLVED:
        ticket.resolved_at = now
        ticket.closed_at = None
    elif new_status == TicketStatus.CLOSED:
        ticket.closed_at = now
    elif new_status == TicketStatus.REOPENED:
        ticket.resolved_at = None
        ticket.closed_at = None

    ticket.save(update_fields=["status", "resolved_at", "closed_at", "updated_at"])

    AuditLog.objects.create(
        actor=actor,
        ticket=ticket,
        action="status_changed",
        metadata={"from": current, "to": new_status},
    )
    return ticket
