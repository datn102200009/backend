from decimal import Decimal
from typing import Any, Dict, Optional

from django.contrib.auth.hashers import make_password
from django.db import transaction

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import ValidationException
from apps.master_data.models import Employee


@transaction.atomic
def employee_create_with_user(
    *,
    data: Dict[str, Any],
    creator: Optional[User] = None,
) -> Employee:
    """
    Tạo mới một Employee và tùy chọn tạo tài khoản User liên kết qua employee_id.

    Args:
        data: Dict chứa thông tin nhân viên và user
        creator: User thực hiện hành động này

    Returns:
        Employee: Bản ghi nhân viên mới tạo
    """
    employee_id = data.get("employee_id")
    if not employee_id:
        raise ValidationException("Mã nhân viên (employee_id) là bắt buộc")

    if Employee.objects.filter(employee_id=employee_id).exists():
        raise ValidationException(f"Mã nhân viên {employee_id} đã tồn tại")

    # Tách dữ liệu User và Employee
    create_user = data.get("create_user", False)

    # Tạo Employee
    employee = Employee.objects.create(
        employee_id=employee_id,
        full_name=data.get("full_name"),
        department=data.get("department"),
        position_title=data.get("position_title"),
        salary_base=data.get("salary_base"),
        is_union_member=data.get("is_union_member", False),
        email=data.get("email"),
        phone=data.get("phone"),
        gender=data.get("gender"),
        date_of_birth=data.get("date_of_birth"),
        address=data.get("address"),
        emergency_contact=data.get("emergency_contact"),
        join_date=data.get("join_date"),
        leave_date=data.get("leave_date"),
        employment_status=data.get("employment_status", "active"),
    )

    # Log employee creation
    employee_data_for_log = {
        "employee_id": employee.employee_id,
        "full_name": employee.full_name,
        "department": employee.department,
        "position_title": employee.position_title,
        "salary_base": str(employee.salary_base) if employee.salary_base is not None else None,
        "email": employee.email,
        "employment_status": employee.employment_status,
    }
    create_system_log(
        user=creator,
        action="create",
        table_name="employee",
        record_id=str(employee.id),
        new_value=employee_data_for_log,
    )

    # Tạo User nếu được yêu cầu
    if create_user:
        username = data.get("username")
        password = data.get("password")
        email = data.get("email") or f"{employee_id}@example.com"
        role_id = data.get("role_id")

        if not username or not password:
            raise ValidationException("Username và password là bắt buộc khi tạo tài khoản User")

        if User.objects.filter(username=username).exists():
            raise ValidationException(f"Username {username} đã tồn tại")

        if User.objects.filter(email=email).exists():
            raise ValidationException(f"Email {email} đã tồn tại")

        user = User.objects.create(
            username=username,
            email=email,
            password_hash=make_password(password),
            role_id=role_id,
            employee_id=employee_id,
            is_active=True,
        )

        # Log user creation
        user_data_for_log = {
            "username": user.username,
            "email": user.email,
            "role_id": str(role_id) if role_id else None,
            "employee_id": employee_id,
        }
        create_system_log(
            user=creator,
            action="create",
            table_name="user",
            record_id=str(user.id),
            new_value=user_data_for_log,
        )

    return employee


@transaction.atomic
def employee_update(
    *,
    employee: Employee,
    data: Dict[str, Any],
    updater: Optional[User] = None,
) -> Employee:
    """
    Cập nhật hồ sơ nhân viên và ghi SystemLog thay đổi chi tiết.

    Args:
        employee: Bản ghi Employee cần cập nhật
        data: Dict chứa các trường cần thay đổi
        updater: User thực hiện cập nhật

    Returns:
        Employee: Bản ghi nhân viên sau khi cập nhật
    """
    fields_to_update = [
        "full_name",
        "department",
        "position_title",
        "salary_base",
        "is_union_member",
        "email",
        "phone",
        "gender",
        "date_of_birth",
        "address",
        "emergency_contact",
        "join_date",
        "leave_date",
        "employment_status",
    ]

    old_value = {}
    new_value = {}
    updated = False

    for field in fields_to_update:
        if field in data:
            old_val = getattr(employee, field)
            new_val = data[field]

            # Normalize values for comparison (especially Decimal)
            if isinstance(old_val, Decimal) and new_val is not None:
                new_val = Decimal(str(new_val))

            if old_val != new_val:
                old_value[field] = str(old_val) if isinstance(old_val, Decimal) else old_val
                new_value[field] = str(new_val) if isinstance(new_val, Decimal) else new_val
                setattr(employee, field, new_val)
                updated = True

    if updated:
        employee.save()
        create_system_log(
            user=updater,
            action="update",
            table_name="employee",
            record_id=str(employee.id),
            old_value=old_value,
            new_value=new_value,
        )

    return employee
