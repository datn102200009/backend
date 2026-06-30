from datetime import date
from typing import Optional, Tuple

from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.master_data.models import Employee


def get_user_permissions(user: User) -> list[str]:
    """Lấy danh sách permissions của user."""
    return list(user.direct_permissions.values_list("permission__code", flat=True))


def system_log_list(
    user: User,
    limit: int = 20,
    offset: int = 0,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    action: Optional[str] = None,
    search: Optional[str] = None,
) -> Tuple[QuerySet, int]:
    """
    Lấy danh sách logs theo permissions của user.
    """
    from apps.accounts.models import SystemLog

    user_permissions = get_user_permissions(user)
    is_admin = "accounts.view_system_log" in user_permissions

    queryset = SystemLog.objects.select_related("user")

    if not is_admin:
        if user_permissions:
            from django.db import connection

            if connection.vendor == "sqlite":
                q_obj = Q()
                for perm in user_permissions:
                    q_obj |= Q(allowed_permissions__icontains=perm)
                queryset = queryset.filter(q_obj)
            else:
                queryset = queryset.filter(allowed_permissions__has_any_keys=user_permissions)
        else:
            return SystemLog.objects.none(), 0

    if start_date:
        queryset = queryset.filter(timestamp__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(timestamp__date__lte=end_date)
    if action:
        queryset = queryset.filter(action=action)
    if search:
        queryset = queryset.filter(
            Q(table_name__icontains=search)
            | Q(action__icontains=search)
            | Q(record_id__icontains=search)
            | Q(record_code__icontains=search)
            | Q(user_repr__icontains=search)
            | Q(user__username__icontains=search)
        )

    total_count = queryset.count()
    queryset = queryset.order_by("-timestamp")[offset : offset + limit]

    return queryset, total_count


def user_list(*, search: str = None):
    """
    Trả về danh sách tất cả tài khoản người dùng kèm theo vai trò
    và nạp trước các quyền được gán trực tiếp.
    """
    qs = User.objects.prefetch_related("direct_permissions__permission").all().order_by("-created_at")

    if search:
        qs = qs.filter(username__icontains=search)

    return qs


def unlinked_employees_list():
    """
    Trả về danh sách các nhân viên đang hoạt động nhưng chưa được tạo tài khoản User.
    """
    # Lấy danh sách employee_id đã được liên kết với User
    linked_employee_ids = (
        User.objects.exclude(employee_id__isnull=True).exclude(employee_id="").values_list("employee_id", flat=True)
    )

    # Lấy các nhân viên đang hoạt động và không nằm trong danh sách đã liên kết
    return (
        Employee.objects.filter(employment_status="active")
        .exclude(employee_id__in=linked_employee_ids)
        .order_by("employee_id")
    )
