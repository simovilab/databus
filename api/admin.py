from django.contrib import admin

# Import client registry admin
from .client_admin import (
    APIClientAdmin,
    APIKeyAdmin,
    ClientQuotaAdmin,
    ClientUsageMetricsAdmin,
    ClientAuditLogAdmin,
)

# Admin classes are registered via decorators in client_admin.py

