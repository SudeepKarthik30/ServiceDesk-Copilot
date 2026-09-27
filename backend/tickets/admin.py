from django.contrib import admin

from tickets.models import AIResult, AuditLog, Category, Comment, Notification, SLAPolicy, Team, Ticket


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "team", "safe_to_auto_solve")
    list_filter = ("team", "safe_to_auto_solve")
    search_fields = ("name",)


@admin.register(SLAPolicy)
class SLAPolicyAdmin(admin.ModelAdmin):
    list_display = ("category", "urgency", "resolve_minutes")
    list_filter = ("urgency",)


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "employee", "team", "assigned_agent", "status", "urgency", "created_at")
    list_filter = ("status", "urgency", "team")
    search_fields = ("title", "description", "employee__email")
    inlines = [CommentInline]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "ticket", "created_at")
    list_filter = ("action",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "message", "is_read", "created_at")
    list_filter = ("is_read",)


@admin.register(AIResult)
class AIResultAdmin(admin.ModelAdmin):
    list_display = ("ticket", "decision", "latency_ms", "created_at")
    list_filter = ("decision",)
