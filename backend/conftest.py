import pytest
from rest_framework.test import APIClient

from accounts.models import User
from tickets.models import Category, SLAPolicy, Team, Urgency


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def team(db):
    return Team.objects.create(name="Networking")


@pytest.fixture
def other_team(db):
    return Team.objects.create(name="Hardware")


@pytest.fixture
def category(db, team):
    return Category.objects.create(name="VPN Access", team=team, safe_to_auto_solve=True)


@pytest.fixture
def sla_policy(db, category):
    return SLAPolicy.objects.create(category=category, urgency=Urgency.P2, resolve_minutes=240)


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(email="admin@test.com", password="pass12345")


@pytest.fixture
def employee(db):
    return User.objects.create_user(email="employee@test.com", password="pass12345", role=User.Role.EMPLOYEE)


@pytest.fixture
def other_employee(db):
    return User.objects.create_user(
        email="employee2@test.com", password="pass12345", role=User.Role.EMPLOYEE
    )


@pytest.fixture
def agent(db, team):
    return User.objects.create_user(
        email="agent@test.com", password="pass12345", role=User.Role.AGENT, team=team
    )


@pytest.fixture
def other_team_agent(db, other_team):
    return User.objects.create_user(
        email="agent2@test.com", password="pass12345", role=User.Role.AGENT, team=other_team
    )


def auth(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client
