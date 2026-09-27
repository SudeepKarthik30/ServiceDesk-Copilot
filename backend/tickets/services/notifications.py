from accounts.models import User
from tickets.models import Notification


def notify_agent(agent, ticket, message):
    if agent is None:
        return
    Notification.objects.create(recipient=agent, ticket=ticket, message=message)


def notify_team(team, ticket, message):
    """Used when a ticket has no single assignee yet (e.g. AI auto-answered it) but the team
    should still see it - notifies every active agent on the team."""
    if team is None:
        return
    agents = User.objects.filter(role=User.Role.AGENT, team=team, is_active=True)
    Notification.objects.bulk_create(
        Notification(recipient=agent, ticket=ticket, message=message) for agent in agents
    )
