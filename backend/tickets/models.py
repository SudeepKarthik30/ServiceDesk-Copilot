from django.conf import settings
from django.db import models


class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="categories")
    safe_to_auto_solve = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Urgency(models.TextChoices):
    P1 = "P1", "P1 - Critical"
    P2 = "P2", "P2 - High"
    P3 = "P3", "P3 - Medium"
    P4 = "P4", "P4 - Low"


class SLAPolicy(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="sla_policies")
    urgency = models.CharField(max_length=2, choices=Urgency.choices)
    resolve_minutes = models.PositiveIntegerField()

    class Meta:
        verbose_name_plural = "SLA policies"
        constraints = [
            models.UniqueConstraint(fields=["category", "urgency"], name="unique_sla_per_category_urgency"),
        ]

    def __str__(self):
        return f"{self.category} / {self.urgency}: {self.resolve_minutes}m"


class TicketStatus(models.TextChoices):
    NEW = "NEW", "New"
    TRIAGING = "TRIAGING", "Triaging"
    AI_ANSWERED = "AI_ANSWERED", "AI Answered"
    ASSIGNED = "ASSIGNED", "Assigned"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    RESOLVED = "RESOLVED", "Resolved"
    CLOSED = "CLOSED", "Closed"
    REOPENED = "REOPENED", "Reopened"


class Ticket(models.Model):
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets_raised"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets"
    )
    team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets"
    )
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets_assigned",
    )

    title = models.CharField(max_length=200)
    description = models.TextField()

    status = models.CharField(max_length=16, choices=TicketStatus.choices, default=TicketStatus.NEW)
    urgency = models.CharField(max_length=2, choices=Urgency.choices, default=Urgency.P3)

    sla_due_at = models.DateTimeField(null=True, blank=True)
    added_to_kb = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} {self.title}"


class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    body = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment #{self.pk} on ticket #{self.ticket_id}"


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs"
    )
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, null=True, blank=True, related_name="audit_logs"
    )
    action = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} @ {self.created_at:%Y-%m-%d %H:%M}"


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message


class AIDecision(models.TextChoices):
    AUTO_ANSWER = "AUTO_ANSWER", "Auto-answer"
    ESCALATE = "ESCALATE", "Escalate"


class AIResult(models.Model):
    """One row per triage() run. Populated from Phase 3 onward; the table exists from Phase 1."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="ai_results")
    classify_input = models.JSONField(default=dict, blank=True)
    candidates = models.JSONField(default=list, blank=True)
    scores = models.JSONField(default=list, blank=True)
    answer = models.JSONField(default=dict, blank=True)
    decision = models.CharField(max_length=16, choices=AIDecision.choices)
    reasons = models.JSONField(default=list, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"AIResult #{self.pk} for ticket #{self.ticket_id} ({self.decision})"
