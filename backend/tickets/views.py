from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from ai.kb import remove_ticket_kb_entry, upsert_ticket_kb_entry
from ai.tasks import run_triage_task
from tickets.models import (
    AIDecision,
    AuditLog,
    Category,
    Comment,
    Notification,
    SLAPolicy,
    Team,
    Ticket,
    TicketStatus,
)
from tickets.permissions import IsAdmin, IsAdminOrReadOnly
from tickets.serializers import (
    AuditLogSerializer,
    CategorySerializer,
    CommentSerializer,
    NotificationSerializer,
    SLAPolicySerializer,
    TeamSerializer,
    TicketCreateSerializer,
    TicketDetailSerializer,
    TicketListSerializer,
    TicketTransitionSerializer,
    UserBriefSerializer,
)
from tickets.services.routing import route_ticket
from tickets.services.workflow import ALLOWED_TRANSITIONS, InvalidTransition, transition


@api_view(["GET"])
def me(request):
    return Response(UserBriefSerializer(request.user).data)


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [IsAdminOrReadOnly]


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.select_related("team").all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]


class SLAPolicyViewSet(viewsets.ModelViewSet):
    queryset = SLAPolicy.objects.select_related("category").all()
    serializer_class = SLAPolicySerializer
    permission_classes = [IsAdminOrReadOnly]


def _is_agent_for(user, ticket):
    return user.role == User.Role.AGENT and (
        ticket.assigned_agent_id == user.id or (ticket.team_id and ticket.team_id == user.team_id)
    )


def _can_view_ticket(user, ticket):
    if user.role == User.Role.ADMIN:
        return True
    if ticket.employee_id == user.id:
        return True
    return _is_agent_for(user, ticket)


# Who may drive each transition, beyond admins (who can always do any legal transition).
# AI_ANSWERED -> RESOLVED/ASSIGNED is deliberately absent here: those are only reachable through
# the dedicated `confirm` action below, which also routes the ❌ case to an actual agent.
EMPLOYEE_ALLOWED_TRANSITIONS = {
    (TicketStatus.RESOLVED, TicketStatus.REOPENED),
    (TicketStatus.CLOSED, TicketStatus.REOPENED),
}
AGENT_ALLOWED_TRANSITIONS = {
    (TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS),
    (TicketStatus.ASSIGNED, TicketStatus.RESOLVED),
    (TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED),
    (TicketStatus.IN_PROGRESS, TicketStatus.ASSIGNED),
    (TicketStatus.RESOLVED, TicketStatus.CLOSED),
    (TicketStatus.REOPENED, TicketStatus.ASSIGNED),
    (TicketStatus.REOPENED, TicketStatus.IN_PROGRESS),
}


def _can_drive_transition(user, ticket, from_status, to_status):
    if user.role == User.Role.ADMIN:
        return True
    if user.role == User.Role.EMPLOYEE and ticket.employee_id == user.id:
        return (from_status, to_status) in EMPLOYEE_ALLOWED_TRANSITIONS
    if user.role == User.Role.AGENT and _is_agent_for(user, ticket):
        return (from_status, to_status) in AGENT_ALLOWED_TRANSITIONS
    return False


def _kb_eligible(ticket):
    """AI-answered tickets are only KB-eligible if the employee confirmed the AI's fix worked
    (a direct AI_ANSWERED -> RESOLVED transition) - not if it was later fixed by an agent after a ❌."""
    was_auto_answered = ticket.ai_results.filter(decision=AIDecision.AUTO_ANSWER).exists()
    if not was_auto_answered:
        return True
    return ticket.audit_logs.filter(
        action="status_changed", metadata__from="AI_ANSWERED", metadata__to="RESOLVED"
    ).exists()


class TicketViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = Ticket.objects.select_related(
            "employee", "assigned_agent", "category", "team"
        ).prefetch_related("ai_results")
        if user.role == User.Role.ADMIN:
            return qs
        if user.role == User.Role.AGENT:
            return qs.filter(Q(assigned_agent=user) | Q(team=user.team))
        return qs.filter(employee=user)

    def get_serializer_class(self):
        if self.action == "create":
            return TicketCreateSerializer
        if self.action == "list":
            return TicketListSerializer
        return TicketDetailSerializer

    def perform_create(self, serializer):
        ticket = serializer.save(employee=self.request.user)
        transition(ticket, TicketStatus.TRIAGING, actor=self.request.user)
        if ticket.category_id:
            route_ticket(ticket, actor=self.request.user)
        else:
            run_triage_task.delay(ticket.id)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not _can_view_ticket(request.user, instance):
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        ticket = get_object_or_404(Ticket, pk=pk)
        if not _can_view_ticket(request.user, ticket):
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = TicketTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        current = ticket.status

        if new_status not in ALLOWED_TRANSITIONS.get(current, set()):
            return Response(
                {"detail": f"Cannot move ticket from {current} to {new_status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not _can_drive_transition(request.user, ticket, current, new_status):
            return Response(
                {"detail": "You are not allowed to make this transition."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            transition(ticket, new_status, actor=request.user)
        except InvalidTransition as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketDetailSerializer(ticket).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Employee confirms an AI_ANSWERED ticket: {"resolved": true} -> RESOLVED,
        {"resolved": false} -> routed to an agent (the ❌ "didn't work" case)."""
        ticket = get_object_or_404(Ticket, pk=pk)
        if not (request.user.role == User.Role.EMPLOYEE and ticket.employee_id == request.user.id):
            return Response(status=status.HTTP_404_NOT_FOUND)
        if ticket.status != TicketStatus.AI_ANSWERED:
            return Response(
                {"detail": "Ticket is not awaiting confirmation."}, status=status.HTTP_400_BAD_REQUEST
            )

        # `request.data.get("resolved")` may be a real bool (JSON body) or the string "False"
        # (form-encoded body) - str(False) is truthy, so compare against the string form too.
        resolved = str(request.data.get("resolved", False)).lower() in ("true", "1")
        if resolved:
            transition(ticket, TicketStatus.RESOLVED, actor=request.user)
        else:
            route_ticket(ticket, actor=request.user)

        return Response(TicketDetailSerializer(ticket).data)

    @action(detail=True, methods=["post"])
    def add_to_kb(self, request, pk=None):
        ticket = get_object_or_404(Ticket, pk=pk)
        if not (request.user.role == User.Role.ADMIN or _is_agent_for(request.user, ticket)):
            return Response(status=status.HTTP_404_NOT_FOUND)
        if ticket.status != TicketStatus.RESOLVED:
            return Response(
                {"detail": "Only resolved tickets can be added to the KB."}, status=status.HTTP_400_BAD_REQUEST
            )
        if ticket.added_to_kb:
            return Response({"detail": "Already added to the KB."}, status=status.HTTP_400_BAD_REQUEST)
        if not _kb_eligible(ticket):
            return Response(
                {"detail": "AI-answered tickets are only eligible after the employee confirmed the fix worked."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resolution = (request.data.get("resolution") or "").strip()
        if not resolution:
            return Response({"detail": "resolution is required."}, status=status.HTTP_400_BAD_REQUEST)
        subject = request.data.get("subject") or ticket.title
        body = request.data.get("body") or ticket.description

        upsert_ticket_kb_entry(ticket, subject, body, resolution)
        ticket.added_to_kb = True
        ticket.save(update_fields=["added_to_kb"])
        AuditLog.objects.create(actor=request.user, ticket=ticket, action="added_to_kb")
        return Response(TicketDetailSerializer(ticket).data)

    @action(detail=True, methods=["post"])
    def remove_from_kb(self, request, pk=None):
        ticket = get_object_or_404(Ticket, pk=pk)
        if not (request.user.role == User.Role.ADMIN or _is_agent_for(request.user, ticket)):
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not ticket.added_to_kb:
            return Response({"detail": "Ticket is not in the KB."}, status=status.HTTP_400_BAD_REQUEST)

        remove_ticket_kb_entry(ticket)
        ticket.added_to_kb = False
        ticket.save(update_fields=["added_to_kb"])
        AuditLog.objects.create(actor=request.user, ticket=ticket, action="removed_from_kb")
        return Response(TicketDetailSerializer(ticket).data)

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        ticket = get_object_or_404(Ticket, pk=pk)
        if not _can_view_ticket(request.user, ticket):
            return Response(status=status.HTTP_404_NOT_FOUND)

        if request.method == "GET":
            qs = ticket.comments.select_related("author")
            if request.user.role == User.Role.EMPLOYEE:
                qs = qs.filter(is_internal=False)
            return Response(CommentSerializer(qs, many=True).data)

        is_internal = bool(request.data.get("is_internal", False)) and request.user.role != User.Role.EMPLOYEE
        comment = Comment.objects.create(
            ticket=ticket,
            author=request.user,
            body=request.data.get("body", ""),
            is_internal=is_internal,
        )
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class NotificationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AuditLog.objects.select_related("actor", "ticket").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdmin]
