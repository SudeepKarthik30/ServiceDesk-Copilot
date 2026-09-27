from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness check: confirms the API is up and the database answers."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db = "ok"
    except Exception as exc:  # report, don't crash, so the health check itself stays up
        db = f"error: {exc.__class__.__name__}"
    return Response({"status": "ok", "database": db})
