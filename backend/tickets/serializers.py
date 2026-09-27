from rest_framework import serializers

from accounts.models import User
from tickets.models import AIResult, AuditLog, Category, Comment, Notification, SLAPolicy, Team, Ticket


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "team"]


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name", "created_at"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "team", "safe_to_auto_solve", "created_at"]


class SLAPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = SLAPolicy
        fields = ["id", "category", "urgency", "resolve_minutes"]


class CommentSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "ticket", "author", "body", "is_internal", "created_at"]
        read_only_fields = ["ticket", "author", "created_at"]


class TicketListSerializer(serializers.ModelSerializer):
    employee = UserBriefSerializer(read_only=True)
    assigned_agent = UserBriefSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "title",
            "employee",
            "category",
            "team",
            "assigned_agent",
            "status",
            "urgency",
            "sla_due_at",
            "created_at",
            "updated_at",
        ]


class AIResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIResult
        fields = ["id", "decision", "reasons", "answer", "candidates", "scores", "latency_ms", "created_at"]


class TicketDetailSerializer(TicketListSerializer):
    # Comments are deliberately NOT embedded here: `is_internal` notes must be hidden from
    # employees, and that filtering only happens in the dedicated GET /tickets/{id}/comments/
    # action (see views.py) - a plain ModelSerializer field here would leak them to anyone who
    # can view the ticket.
    ai_results = AIResultSerializer(many=True, read_only=True)

    class Meta(TicketListSerializer.Meta):
        fields = TicketListSerializer.Meta.fields + [
            "description",
            "added_to_kb",
            "resolved_at",
            "closed_at",
            "ai_results",
        ]


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ["id", "title", "description", "category", "urgency"]

    def create(self, validated_data):
        validated_data["employee"] = self.context["request"].user
        return super().create(validated_data)


class TicketTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[c[0] for c in Ticket._meta.get_field("status").choices])


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "ticket", "message", "is_read", "created_at"]
        read_only_fields = ["ticket", "message", "created_at"]


class AuditLogSerializer(serializers.ModelSerializer):
    actor = UserBriefSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "ticket", "action", "metadata", "created_at"]
