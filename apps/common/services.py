"""
Services for common app.

All write operations (Create, Update, Delete) should be defined here.
Never receive request objects, only primitive types or DTOs.
Always ensure atomic transactions.
"""

from typing import Any, Dict, Optional

from django.db import transaction

from apps.accounts.models import SystemLog, User


@transaction.atomic
def create_system_log(
    *,
    user: Optional[User],
    action: str,
    table_name: str,
    record_id: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
) -> SystemLog:
    """
    Tạo một bản ghi nhật ký hệ thống (audit log).

    Args:
        user: User thực hiện hành động
        action: Loại hành động (create, update, delete, approve, etc.)
        table_name: Tên bảng được thay đổi
        record_id: ID của bản ghi được thay đổi
        old_value: Giá trị cũ (cho các hành động update)
        new_value: Giá trị mới (cho các hành động update hoặc create)

    Returns:
        SystemLog object

    Ví dụ:
        create_system_log(
            user=user,
            action="create",
            table_name="stock_entry",
            record_id=str(stock_entry.id),
            new_value={"name": "SE-001", "purpose": "receipt"}
        )
    """
    return SystemLog.objects.create(
        user=user,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_value=old_value,
        new_value=new_value,
    )
