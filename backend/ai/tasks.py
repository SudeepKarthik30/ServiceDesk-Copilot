from celery import shared_task


@shared_task
def run_triage_task(ticket_id):
    from ai.pipeline import triage
    from tickets.models import Ticket

    triage(Ticket.objects.get(pk=ticket_id))
