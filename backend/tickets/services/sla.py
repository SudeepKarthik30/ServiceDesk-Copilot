from datetime import timedelta

from django.utils import timezone

from tickets.models import SLAPolicy


def compute_sla_due_at(category, urgency, from_time=None):
    """Look up the SLAPolicy for (category, urgency) and return the resolve-by datetime.

    Returns None if there's no category yet or no policy configured for it -
    the ticket simply has no SLA until one is set.
    """
    if category is None:
        return None
    policy = SLAPolicy.objects.filter(category=category, urgency=urgency).first()
    if policy is None:
        return None
    base = from_time or timezone.now()
    return base + timedelta(minutes=policy.resolve_minutes)
