from django.urls import path
from rest_framework.routers import DefaultRouter

from tickets.views import (
    AuditLogViewSet,
    CategoryViewSet,
    NotificationViewSet,
    SLAPolicyViewSet,
    TeamViewSet,
    TicketViewSet,
    me,
)

router = DefaultRouter()
router.register("teams", TeamViewSet)
router.register("categories", CategoryViewSet)
router.register("sla-policies", SLAPolicyViewSet)
router.register("tickets", TicketViewSet, basename="ticket")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("audit-logs", AuditLogViewSet, basename="auditlog")

urlpatterns = [
    path("auth/me/", me, name="me"),
] + router.urls
