from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from tickets.models import Category, SLAPolicy, Team, Urgency

TEAMS_AND_CATEGORIES = {
    "Networking": [
        ("VPN Access", True),
        ("Wifi Connectivity", True),
        ("Network Outage", False),
    ],
    "Hardware": [
        ("Laptop Issue", False),
        ("Peripheral Request", True),
        ("Monitor Issue", True),
    ],
    "Software & Access": [
        ("Password Reset", True),
        ("Software Installation", True),
        ("Account Access", False),
    ],
}

# minutes to resolve, by urgency
SLA_MINUTES = {
    Urgency.P1: 60,
    Urgency.P2: 4 * 60,
    Urgency.P3: 24 * 60,
    Urgency.P4: 72 * 60,
}

DEMO_AGENTS = {
    "Networking": ["net.agent1@example.com", "net.agent2@example.com"],
    "Hardware": ["hw.agent1@example.com"],
    "Software & Access": ["access.agent1@example.com", "access.agent2@example.com"],
}

DEMO_EMPLOYEES = ["alice@example.com", "bob@example.com", "carol@example.com"]

DEFAULT_PASSWORD = "password123"


class Command(BaseCommand):
    help = "Seed core reference data: teams, categories, SLA policies, and demo users."

    @transaction.atomic
    def handle(self, *args, **options):
        for team_name, categories in TEAMS_AND_CATEGORIES.items():
            team, _ = Team.objects.get_or_create(name=team_name)
            for category_name, safe in categories:
                category, _ = Category.objects.get_or_create(
                    name=category_name, defaults={"team": team, "safe_to_auto_solve": safe}
                )
                for urgency, minutes in SLA_MINUTES.items():
                    SLAPolicy.objects.get_or_create(
                        category=category, urgency=urgency, defaults={"resolve_minutes": minutes}
                    )
            self.stdout.write(f"Team '{team_name}': {len(categories)} categories seeded.")

        if not User.objects.filter(email="admin@example.com").exists():
            User.objects.create_superuser(email="admin@example.com", password=DEFAULT_PASSWORD)
            self.stdout.write("Created admin@example.com / " + DEFAULT_PASSWORD)

        for team_name, emails in DEMO_AGENTS.items():
            team = Team.objects.get(name=team_name)
            for email in emails:
                if not User.objects.filter(email=email).exists():
                    User.objects.create_user(
                        email=email, password=DEFAULT_PASSWORD, role=User.Role.AGENT, team=team
                    )
        self.stdout.write(f"Seeded {sum(len(v) for v in DEMO_AGENTS.values())} demo agents.")

        for email in DEMO_EMPLOYEES:
            if not User.objects.filter(email=email).exists():
                User.objects.create_user(email=email, password=DEFAULT_PASSWORD, role=User.Role.EMPLOYEE)
        self.stdout.write(f"Seeded {len(DEMO_EMPLOYEES)} demo employees.")

        self.stdout.write(self.style.SUCCESS("Seed complete. Default password for demo users: " + DEFAULT_PASSWORD))
