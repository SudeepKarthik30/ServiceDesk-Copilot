from django.db.models import Count, Q

from accounts.models import User
from tickets.models import AuditLog, TicketStatus
from tickets.services.notifications import notify_agent
from tickets.services.sla import compute_sla_due_at
from tickets.services.workflow import transition


def pick_least_loaded_agent(team):
    """Among agents on `team`, return the one with the fewest open tickets (ASSIGNED/IN_PROGRESS)."""
    if team is None:
        return None
    open_statuses = (TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS)
    agents = (
        User.objects.filter(role=User.Role.AGENT, team=team, is_active=True)
        .annotate(
            open_ticket_count=Count(
                "tickets_assigned", filter=Q(tickets_assigned__status__in=open_statuses)
            )
        )
        .order_by("open_ticket_count", "id")
    )
    return agents.first()


def route_ticket(ticket, actor=None):
    """Route a ticket (in TRIAGING) to its category's team and the least-loaded agent on that team.

    Sets team, assigned_agent, sla_due_at and moves status TRIAGING -> ASSIGNED. Records an
    AuditLog entry with the routing decision. No-ops if the ticket has no category yet.
    """
    if ticket.category is None:
        return ticket

    team = ticket.category.team
    agent = pick_least_loaded_agent(team)

    ticket.team = team
    ticket.assigned_agent = agent
    ticket.sla_due_at = compute_sla_due_at(ticket.category, ticket.urgency)
    ticket.save(update_fields=["team", "assigned_agent", "sla_due_at", "updated_at"])

    transition(ticket, TicketStatus.ASSIGNED, actor=actor)
    notify_agent(agent, ticket, f'Ticket #{ticket.id} "{ticket.title}" was assigned to you.')

    AuditLog.objects.create(
        actor=actor,
        ticket=ticket,
        action="ticket_routed",
        metadata={
            "team_id": team.id if team else None,
            "agent_id": agent.id if agent else None,
            "category_id": ticket.category_id,
            "urgency": ticket.urgency,
        },
    )
    return ticket
