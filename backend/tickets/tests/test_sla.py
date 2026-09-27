import pytest
from django.utils import timezone

from tickets.models import Urgency
from tickets.services.sla import compute_sla_due_at


@pytest.mark.django_db
def test_no_category_means_no_sla():
    assert compute_sla_due_at(None, Urgency.P1) is None


@pytest.mark.django_db
def test_no_matching_policy_means_no_sla(category):
    assert compute_sla_due_at(category, Urgency.P1) is None


@pytest.mark.django_db
def test_due_at_is_created_time_plus_policy_minutes(category, sla_policy):
    now = timezone.now()
    due = compute_sla_due_at(category, Urgency.P2, from_time=now)
    assert due == now + timezone.timedelta(minutes=sla_policy.resolve_minutes)
