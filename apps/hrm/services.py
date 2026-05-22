from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional

from django.contrib.auth.hashers import make_password
from django.db import transaction

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import ValidationException
from apps.hrm.models import EmployeeDocument, EmploymentContract
from apps.master_data.models import Employee


@transaction.atomic
def employee_create_with_user(
    *,
    data: Dict[str, Any],
    creator: Optional[User] = None,
) -> Employee:
    """
    Tạo mới một Employee và tùy chọn tạo tài khoản User liên kết qua employee_id.
    """
    employee_id = data.get("employee_id")
    if not employee_id:
        raise ValidationException("Mã nhân viên (employee_id) là bắt buộc")

    if Employee.objects.filter(employee_id=employee_id).exists():
        raise ValidationException(f"Mã nhân viên {employee_id} đã tồn tại")

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


@transaction.atomic
def contract_create_or_renew(
    *,
    employee_id: str,
    contract_data: Dict[str, Any],
    creator: Optional[User] = None,
) -> EmploymentContract:
    """
    Tạo mới hoặc gia hạn hợp đồng lao động cho nhân viên.
    Nếu có hợp đồng đang 'active' khác, chuyển nó sang 'expired'.

    Args:
        employee_id: ID của nhân viên
        contract_data: Dict chứa thông tin hợp đồng mới
        creator: User thực hiện hành động

    Returns:
        EmploymentContract: Hợp đồng lao động mới
    """
    try:
        employee = Employee.objects.get(id=employee_id)
    except Employee.DoesNotExist:
        raise ValidationException("Nhân viên không tồn tại")

    contract_no = contract_data.get("contract_no")
    if not contract_no:
        raise ValidationException("Số hợp đồng (contract_no) là bắt buộc")

    if EmploymentContract.objects.filter(contract_no=contract_no).exists():
        raise ValidationException(f"Số hợp đồng {contract_no} đã tồn tại")

    # 1. Tìm các hợp đồng active cũ của nhân viên để chuyển sang expired
    active_contracts = EmploymentContract.objects.filter(employee=employee, status="active")
    for old_contract in active_contracts:
        old_contract.status = "expired"
        old_contract.save(update_fields=["status"])

        # Log old contract update
        create_system_log(
            user=creator,
            action="update",
            table_name="employment_contract",
            record_id=str(old_contract.id),
            old_value={"status": "active"},
            new_value={"status": "expired"},
        )

    # 2. Tạo hợp đồng mới ở trạng thái active
    contract = EmploymentContract.objects.create(
        employee=employee,
        contract_no=contract_no,
        contract_type=contract_data.get("contract_type"),
        start_date=contract_data.get("start_date"),
        end_date=contract_data.get("end_date"),
        status="active",
        note=contract_data.get("note"),
        file_url=contract_data.get("file_url"),
    )

    # Log new contract creation
    contract_log_data = {
        "contract_no": contract.contract_no,
        "contract_type": contract.contract_type,
        "start_date": str(contract.start_date),
        "end_date": str(contract.end_date) if contract.end_date else None,
        "status": contract.status,
    }
    create_system_log(
        user=creator,
        action="create",
        table_name="employment_contract",
        record_id=str(contract.id),
        new_value=contract_log_data,
    )

    # 3. Tạo tài liệu đính kèm scan hợp đồng nếu có file_url
    file_url = contract_data.get("file_url")
    if file_url:
        doc = EmployeeDocument.objects.create(
            employee=employee,
            doc_type="contract_scan",
            title=f"Scan Hợp đồng {contract_no}",
            file_url=file_url,
            uploaded_by=creator,
        )

        # Log document creation
        create_system_log(
            user=creator,
            action="create",
            table_name="employee_document",
            record_id=str(doc.id),
            new_value={
                "doc_type": doc.doc_type,
                "title": doc.title,
                "file_url": doc.file_url,
            },
        )

    return contract


@transaction.atomic
def contract_terminate(
    *,
    contract_id: str,
    termination_date: date,
    reason: str,
    terminator: Optional[User] = None,
    file_url: Optional[str] = None,
) -> EmploymentContract:
    """
    Chấm dứt hợp đồng lao động:
    - Chuyển trạng thái hợp đồng sang 'terminated'
    - Điền leave_date và chuyển status của Employee sang 'inactive'
    - Khóa tài khoản User tương ứng (is_active = False)
    - Lưu tài liệu đính kèm quyết định thôi việc nếu có

    Args:
        contract_id: ID của hợp đồng cần chấm dứt
        termination_date: Ngày chấm dứt hợp đồng
        reason: Lý do chấm dứt
        terminator: User thực hiện chấm dứt
        file_url: Đường dẫn file scan quyết định thôi việc

    Returns:
        EmploymentContract: Hợp đồng đã chấm dứt
    """
    try:
        contract = EmploymentContract.objects.get(id=contract_id)
    except EmploymentContract.DoesNotExist:
        raise ValidationException("Hợp đồng không tồn tại")

    if contract.status == "terminated":
        raise ValidationException("Hợp đồng này đã được chấm dứt trước đó")

    employee = contract.employee

    # 1. Cập nhật EmploymentContract
    old_contract_status = contract.status
    old_contract_end = contract.end_date
    contract.status = "terminated"
    contract.end_date = termination_date
    contract.note = f"{contract.note or ''}\n[Termination Reason]: {reason}".strip()
    contract.save(update_fields=["status", "end_date", "note"])

    create_system_log(
        user=terminator,
        action="update",
        table_name="employment_contract",
        record_id=str(contract.id),
        old_value={
            "status": old_contract_status,
            "end_date": str(old_contract_end) if old_contract_end else None,
        },
        new_value={
            "status": "terminated",
            "end_date": str(termination_date),
        },
    )

    # 2. Cập nhật Employee sang inactive và điền leave_date
    old_emp_status = employee.employment_status
    old_leave_date = employee.leave_date
    employee.employment_status = "inactive"
    employee.leave_date = termination_date
    employee.save(update_fields=["employment_status", "leave_date"])

    create_system_log(
        user=terminator,
        action="update",
        table_name="employee",
        record_id=str(employee.id),
        old_value={
            "employment_status": old_emp_status,
            "leave_date": str(old_leave_date) if old_leave_date else None,
        },
        new_value={
            "employment_status": "inactive",
            "leave_date": str(termination_date),
        },
    )

    # 3. Vô hiệu hóa tài khoản User liên kết qua employee_id
    linked_user = User.objects.filter(employee_id=employee.employee_id).first()
    if linked_user:
        old_active = linked_user.is_active
        linked_user.is_active = False
        linked_user.save(update_fields=["is_active"])

        create_system_log(
            user=terminator,
            action="update",
            table_name="user",
            record_id=str(linked_user.id),
            old_value={"is_active": old_active},
            new_value={"is_active": False},
        )

    # 4. Lưu tài liệu quyết định thôi việc nếu có file_url
    if file_url:
        doc = EmployeeDocument.objects.create(
            employee=employee,
            doc_type="resignation_letter",
            title=f"Quyết định thôi việc - {employee.full_name}",
            file_url=file_url,
            uploaded_by=terminator,
        )

        create_system_log(
            user=terminator,
            action="create",
            table_name="employee_document",
            record_id=str(doc.id),
            new_value={
                "doc_type": doc.doc_type,
                "title": doc.title,
                "file_url": doc.file_url,
            },
        )

    return contract
