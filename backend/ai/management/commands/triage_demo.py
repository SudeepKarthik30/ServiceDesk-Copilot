import json

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from ai.pipeline import triage
from tickets.models import Ticket, TicketStatus
from tickets.services.workflow import transition


class Command(BaseCommand):
    help = (
        "Run the AI triage pipeline on an ad-hoc ticket text and print the result. "
        "Creates a throwaway ticket to run triage() against, then rolls back the transaction - "
        "nothing is left in the database."
    )

    def add_arguments(self, parser):
        parser.add_argument("text", help="Ticket text. First line is used as the title.")

    def handle(self, *args, **options):
        title, _, description = options["text"].partition("\n")
        description = description.strip() or title

        with transaction.atomic():
            employee = User.objects.filter(role=User.Role.EMPLOYEE).first()
            if employee is None:
                employee = User.objects.create_user(
                    email="triage-demo@example.com", password="unused", role=User.Role.EMPLOYEE
                )

            ticket = Ticket.objects.create(employee=employee, title=title[:200], description=description)
            transition(ticket, TicketStatus.TRIAGING)

            result = triage(ticket)
            ticket.refresh_from_db()

            self.stdout.write(self.style.SUCCESS(f"Decision: {result.decision}"))
            self.stdout.write(f"Reasons: {result.reasons}")
            self.stdout.write(
                f"Category: {ticket.category} | Urgency: {ticket.urgency} | Status: {ticket.status}"
            )
            self.stdout.write(f"Top candidates: {result.scores}")
            if result.answer:
                self.stdout.write("Answer:")
                self.stdout.write(json.dumps(result.answer, indent=2))
            self.stdout.write(f"Latency: {result.latency_ms}ms")

            transaction.set_rollback(True)
