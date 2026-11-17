from collections import Counter
import os

from django.conf import settings
from django.utils import timezone

from .models import Assignment


def workspace_assignments(request):
    """Share one snapshot between the page and its navigation."""
    if not hasattr(request, "_workspace_assignments"):
        request._workspace_assignments = list(
            Assignment.objects.all()
        )
    return request._workspace_assignments


def course_counts(assignments):
    counts = Counter(item.course_name for item in assignments)
    return [{"name": name, "count": count} for name, count in sorted(counts.items())]


def workspace_context(request):
    assignments = workspace_assignments(request)
    return {
        "sidebar_courses": course_counts(assignments),
        "sidebar_active_count": sum(not item.is_complete for item in assignments),
        "current_date": timezone.localdate(),
        "ui_demo": settings.UI_DEMO,
        "rag_configured": bool(os.environ.get("ASSIGNMENT_RAG_DIR")),
    }
