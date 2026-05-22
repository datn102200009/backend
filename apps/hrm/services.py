from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import ValidationException
from apps.hrm.models import Attendance, EmployeeDocument, EmploymentContract, EmploymentHistory, LeaveRequest
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


@transaction.atomic
def employee_update_salary_or_title(
    *,
    employee_id: str,
    change_data: Dict[str, Any],
    approved_by_user_id: str,
) -> Employee:
    """
    Cập nhật lương cơ bản, chức danh hoặc phòng ban của nhân viên và tự động ghi nhận vào EmploymentHistory.
    """
    try:
        employee = Employee.objects.get(id=employee_id)
    except Employee.DoesNotExist:
        raise ValidationException("Nhân viên không tồn tại")

    try:
        approved_by = User.objects.get(id=approved_by_user_id)
    except User.DoesNotExist:
        approved_by = None

    change_type = change_data.get("change_type")
    if not change_type:
        raise ValidationException("Loại thay đổi (change_type) là bắt buộc")

    effective_date = change_data.get("effective_date")
    if not effective_date:
        raise ValidationException("Ngày có hiệu lực (effective_date) là bắt buộc")

    # Lưu giá trị cũ
    old_salary_base = employee.salary_base
    old_title = employee.position_title
    old_department = employee.department

    # Khởi tạo giá trị mới
    new_salary_base = change_data.get("new_salary_base")
    new_title = change_data.get("new_title")
    new_department = change_data.get("new_department")

    # Thực hiện cập nhật
    if change_type == "salary_change":
        if new_salary_base is None:
            raise ValidationException("Lương cơ bản mới là bắt buộc cho thay đổi lương")
        employee.salary_base = Decimal(str(new_salary_base))
    elif change_type == "title_change":
        if not new_title:
            raise ValidationException("Chức danh mới là bắt buộc cho thay đổi chức danh")
        employee.position_title = new_title
    elif change_type == "department_transfer":
        if not new_department:
            raise ValidationException("Phòng ban mới là bắt buộc cho điều chuyển phòng ban")
        employee.department = new_department
    elif change_type == "other":
        if new_salary_base is not None:
            employee.salary_base = Decimal(str(new_salary_base))
        if new_title is not None:
            employee.position_title = new_title
        if new_department is not None:
            employee.department = new_department
    else:
        raise ValidationException(f"Loại thay đổi không hợp lệ: {change_type}")

    employee.save()

    # Ghi nhận log employee update trước
    employee_old = {}
    employee_new = {}
    if old_salary_base != employee.salary_base:
        employee_old["salary_base"] = str(old_salary_base) if old_salary_base is not None else None
        employee_new["salary_base"] = str(employee.salary_base)
    if old_title != employee.position_title:
        employee_old["position_title"] = old_title
        employee_new["position_title"] = employee.position_title
    if old_department != employee.department:
        employee_old["department"] = old_department
        employee_new["department"] = employee.department

    if employee_new:
        create_system_log(
            user=approved_by,
            action="update",
            table_name="employee",
            record_id=str(employee.id),
            old_value=employee_old,
            new_value=employee_new,
        )

    # 2. Tạo bản ghi EmploymentHistory
    history = EmploymentHistory.objects.create(
        employee=employee,
        change_type=change_type,
        old_salary_base=old_salary_base,
        new_salary_base=employee.salary_base,
        old_title=old_title,
        new_title=employee.position_title,
        old_department=old_department,
        new_department=employee.department,
        effective_date=effective_date,
        approved_by=approved_by,
        reason=change_data.get("reason"),
    )

    # 3. Ghi log cho EmploymentHistory
    history_log_data = {
        "change_type": history.change_type,
        "old_salary_base": str(history.old_salary_base) if history.old_salary_base is not None else None,
        "new_salary_base": str(history.new_salary_base) if history.new_salary_base is not None else None,
        "old_title": history.old_title,
        "new_title": history.new_title,
        "old_department": history.old_department,
        "new_department": history.new_department,
        "effective_date": str(history.effective_date),
        "reason": history.reason,
    }
    create_system_log(
        user=approved_by,
        action="create",
        table_name="employment_history",
        record_id=str(history.id),
        new_value=history_log_data,
    )

    return employee


@transaction.atomic
def attendance_batch_record(
    *,
    date: date,
    records: list[Dict[str, Any]],
    creator: Optional[User] = None,
) -> list[Attendance]:
    """
    Chấm công hàng loạt cho nhân viên vào một ngày cụ thể (tạo mới hoặc cập nhật).
    """
    result = []
    for rec in records:
        employee_id = rec.get("employee_id")
        status = rec.get("status")
        if not employee_id or not status:
            raise ValidationException("Thông tin nhân viên và trạng thái chấm công là bắt buộc")

        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            raise ValidationException(f"Nhân viên ID {employee_id} không tồn tại")

        work_hours = Decimal(str(rec.get("work_hours", 8.00)))
        overtime_hours = Decimal(str(rec.get("overtime_hours", 0.00)))
        remarks = rec.get("remarks")

        # Tìm bản ghi chấm công đã tồn tại
        attendance, created = Attendance.objects.get_or_create(
            employee=employee,
            date=date,
            defaults={
                "status": status,
                "work_hours": work_hours,
                "overtime_hours": overtime_hours,
                "remarks": remarks,
            },
        )

        if not created:
            # Cập nhật nếu đã tồn tại
            old_status = attendance.status
            old_work_hours = attendance.work_hours
            old_overtime_hours = attendance.overtime_hours
            old_remarks = attendance.remarks

            attendance.status = status
            attendance.work_hours = work_hours
            attendance.overtime_hours = overtime_hours
            attendance.remarks = remarks
            attendance.save()

            # Ghi log update
            create_system_log(
                user=creator,
                action="update",
                table_name="attendance",
                record_id=str(attendance.id),
                old_value={
                    "status": old_status,
                    "work_hours": str(old_work_hours),
                    "overtime_hours": str(old_overtime_hours),
                    "remarks": old_remarks,
                },
                new_value={
                    "status": status,
                    "work_hours": str(work_hours),
                    "overtime_hours": str(overtime_hours),
                    "remarks": remarks,
                },
            )
        else:
            # Ghi log create
            create_system_log(
                user=creator,
                action="create",
                table_name="attendance",
                record_id=str(attendance.id),
                new_value={
                    "employee_id": str(employee.id),
                    "date": str(date),
                    "status": status,
                    "work_hours": str(work_hours),
                    "overtime_hours": str(overtime_hours),
                    "remarks": remarks,
                },
            )

        result.append(attendance)

    return result


@transaction.atomic
def leave_request_create(
    *,
    employee_id: str,
    data: Dict[str, Any],
) -> LeaveRequest:
    """
    Tạo đơn xin nghỉ phép của nhân viên (mặc định trạng thái pending).
    """
    try:
        employee = Employee.objects.get(id=employee_id)
    except Employee.DoesNotExist:
        raise ValidationException("Nhân viên không tồn tại")

    start_date = data.get("start_date")
    end_date = data.get("end_date")
    days = Decimal(str(data.get("days")))
    leave_type = data.get("leave_type")
    reason = data.get("reason")

    if not start_date or not end_date or not leave_type or days <= 0:
        raise ValidationException(
            "Các thông tin ngày bắt đầu, ngày kết thúc, loại nghỉ và số ngày nghỉ (>0) là bắt buộc"
        )

    leave_request = LeaveRequest.objects.create(
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        days=days,
        reason=reason,
        status="pending",
    )

    create_system_log(
        user=None,
        action="create",
        table_name="leave_request",
        record_id=str(leave_request.id),
        new_value={
            "employee_id": str(employee.id),
            "leave_type": leave_type,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "days": str(days),
            "reason": reason,
            "status": "pending",
        },
    )

    return leave_request


@transaction.atomic
def leave_request_approve(
    *,
    leave_request_id: str,
    approved_by_user_id: str,
) -> LeaveRequest:
    """
    Phê duyệt đơn xin nghỉ phép và tự động đồng bộ sang chấm công.
    """
    try:
        leave_request = LeaveRequest.objects.get(id=leave_request_id)
    except LeaveRequest.DoesNotExist:
        raise ValidationException("Đơn xin nghỉ phép không tồn tại")

    if leave_request.status != "pending":
        raise ValidationException(f"Đơn xin nghỉ phép đã ở trạng thái: {leave_request.status}")

    try:
        approved_by = User.objects.get(id=approved_by_user_id)
    except User.DoesNotExist:
        approved_by = None

    old_status = leave_request.status
    leave_request.status = "approved"
    leave_request.approved_by = approved_by
    leave_request.approved_at = timezone.now()
    leave_request.save()

    create_system_log(
        user=approved_by,
        action="update",
        table_name="leave_request",
        record_id=str(leave_request.id),
        old_value={"status": old_status},
        new_value={
            "status": "approved",
            "approved_by_id": str(approved_by_user_id),
            "approved_at": str(leave_request.approved_at),
        },
    )

    # Tự động tạo/cập nhật bảng Attendance cho các ngày nghỉ
    status_map = {
        "annual": "paid_leave",
        "sick": "sick_leave",
        "unpaid": "unpaid_leave",
        "maternity": "paid_leave",
        "personal": "unpaid_leave",
        "other": "other",
    }
    attendance_status = status_map.get(leave_request.leave_type, "other")

    start = leave_request.start_date
    end = leave_request.end_date
    current_date = start

    while current_date <= end:
        attendance, created = Attendance.objects.get_or_create(
            employee=leave_request.employee,
            date=current_date,
            defaults={
                "status": attendance_status,
                "work_hours": Decimal("0.00"),
                "overtime_hours": Decimal("0.00"),
                "remarks": f"Tự động đồng bộ từ Đơn nghỉ phép ID {leave_request.id}",
            },
        )

        if not created:
            old_att_status = attendance.status
            old_att_work = attendance.work_hours
            old_att_overtime = attendance.overtime_hours
            old_att_remarks = attendance.remarks

            attendance.status = attendance_status
            attendance.work_hours = Decimal("0.00")
            attendance.overtime_hours = Decimal("0.00")
            attendance.remarks = f"Tự động đồng bộ từ Đơn nghỉ phép ID {leave_request.id}"
            attendance.save()

            create_system_log(
                user=approved_by,
                action="update",
                table_name="attendance",
                record_id=str(attendance.id),
                old_value={
                    "status": old_att_status,
                    "work_hours": str(old_att_work),
                    "overtime_hours": str(old_att_overtime),
                    "remarks": old_att_remarks,
                },
                new_value={
                    "status": attendance_status,
                    "work_hours": "0.00",
                    "overtime_hours": "0.00",
                    "remarks": attendance.remarks,
                },
            )
        else:
            create_system_log(
                user=approved_by,
                action="create",
                table_name="attendance",
                record_id=str(attendance.id),
                new_value={
                    "employee_id": str(leave_request.employee.id),
                    "date": str(current_date),
                    "status": attendance_status,
                    "work_hours": "0.00",
                    "overtime_hours": "0.00",
                    "remarks": attendance.remarks,
                },
            )

        current_date += timedelta(days=1)

    return leave_request
