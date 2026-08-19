"""django-filter FilterSet for equipment logs.

NOTE: unused/dead code — not imported anywhere in the codebase, and its
``EquipmentLog`` import is stale (the model moved to the ``operations`` app
in migration 0003/0005; it no longer exists on ``schedule_engine.models``).
Left as-is per the zero-behavior-change constraint; see task report.
"""

import django_filters
from .models import EquipmentLog


class EquipmentLogFilter(django_filters.FilterSet):
    """django-filter FilterSet exposing exact-match filtering by equipment."""

    class Meta:
        model = EquipmentLog
        fields = {
            "equipment": ["exact"],
        }
