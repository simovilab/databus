import django_filters
from .models import EquipmentLog


class EquipmentLogFilter(django_filters.FilterSet):
    class Meta:
        model = EquipmentLog
        fields = {
            "equipment": ["exact"],
        }
