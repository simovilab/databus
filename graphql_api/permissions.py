from typing import Any
from strawberry.permission import BasePermission
from strawberry.types import Info
import strawberry


class IsAuthenticated(BasePermission):
    """Permission class to check if user is authenticated"""

    message = "User is not authenticated"

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        request = info.context.request
        return request.user.is_authenticated


class IsStaff(BasePermission):
    """Permission class to check if user is staff"""

    message = "User must be staff to perform this operation"

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        request = info.context.request
        return request.user.is_authenticated and request.user.is_staff


class HasModelPermission(BasePermission):
    """Permission class to check if user has specific model permission"""

    def __init__(self, app_label: str, model_name: str, permission: str):
        self.permission_string = f"{app_label}.{permission}_{model_name}"
        self.message = f"User does not have permission: {self.permission_string}"

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        request = info.context.request
        return request.user.is_authenticated and request.user.has_perm(
            self.permission_string
        )


@strawberry.type
class PermissionError:
    """Error type for permission denied"""

    message: str
    code: str = "PERMISSION_DENIED"
