import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.finance.models import SalarySlip
from apps.hrm.models import (
    Attendance,
    DisciplineRecord,
    EmployeeDocument,
    EmploymentContract,
    LeaveRequest,
    PublicHoliday,
    RewardRecord,
)
from apps.hrm.selectors import get_salary_at_date, get_salary_for_day, get_salary_timeline, split_into_segments
from apps.master_data.models import Employee

logger = logging.getLogger(__name__)

# Quyết toán lương - các hằng số nghiệp vụ
RESIGNATION_FINE_HALF_MONTH = Decimal("0.5")  # Nửa tháng lương (Điều 40 BLLĐ 2019)
SOCIAL_INSURANCE_RATE = Decimal("0.105")  # 10.5% BHXH (người lao động đóng)
SOCIAL_INSURANCE_MIN_DAYS = 14  # Số ngày làm việc tối thiểu để đóng BHXH tháng đó
DEFAULT_STANDARD_WORKING_DAYS = Decimal("26.00")  # Ngày công chuẩn fallback


def _delete_linked_user(*, employee: Employee, terminator: Optional[User] = None) -> None:
    """
    Xóa tài khoản User liên kết với employee_id.
    """
    linked_user = User.objects.filter(employee_id=employee.employee_id).first()
    if not linked_user:
        return

    user_id = linked_user.id
    username = linked_user.username
    linked_user.delete()

    if terminator:
        create_system_log(
            user=terminator,
            action="delete",
            table_name="user",
            record_id=str(user_id),
            old_value={"username": username},
            new_value=None,
        )


def _terminate_active_contract(
    *,
    employee: Employee,
    termination_date: date,
    reason: str,
    file_url: Optional[str],
    terminator: User,
    is_lawful: bool = True,
) -> None:
    """
    Terminate HĐLĐ đang active (bao gồm quyết toán lương cuối kỳ).
    Raises ValidationException nếu không terminate được.
    """
    active_contract = EmploymentContract.objects.select_for_update().filter(employee=employee, status="active").first()
    if not active_contract:
        return

    try:
        contract_terminate(
            contract_id=str(active_contract.id),
            termination_date=termination_date,
            reason=reason,
            file_url=file_url,
            terminator=terminator,
            is_lawful=is_lawful,
        )
    except ValidationException as e:
        raise ValidationException(f"Không thể sa thải nhân viên: {str(e)}")


def _deactivate_employee(
    *,
    employee: Employee,
    termination_date: date,
    terminator: User,
) -> None:
    """
    Set Employee.employment_status = 'inactive' + leave_date.
    Dùng khi nhân viên không có HĐLĐ active (vd: nhân viên thử việc).
    """
    if employee.employment_status == "inactive":
        raise ValidationException("Nhân viên này đã bị sa thải hoặc ngưng hoạt động trước đó.")

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
            "note": "Sa thải theo kỷ luật - không có HĐLĐ active",
        },
    )

    _delete_linked_user(employee=employee, terminator=terminator)


def _create_termination_document(
    *,
    employee: Employee,
    file_url: str,
    terminator: User,
) -> None:
    """
    Lưu EmployeeDocument cho file quyết định sa thải.
    """
    doc = EmployeeDocument.objects.create(
        employee=employee,
        doc_type="disciplinary_minutes",
        title=f"Quyết định sa thải kỷ luật - {employee.full_name}",
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


def generate_employee_id() -> str:
    """
    Tự động sinh mã nhân viên dạng NV#### (ví dụ: NV0001, NV0002...).
    Tìm mã NV có số thứ tự lớn nhất hiện tại trong Database và cộng thêm 1.
    Padding tối thiểu là 4 chữ số, tự động nở rộng thành 5 chữ số từ NV10000.
    """
    max_num = 0
    # Lấy các mã NV bắt đầu bằng "NV" hiện tại trong DB
    employee_ids = Employee.objects.filter(employee_id__startswith="NV").values_list("employee_id", flat=True)

    for emp_id in employee_ids:
        match = re.match(r"^NV(\d+)$", emp_id)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    next_num = max_num + 1
    num_str = str(next_num).zfill(4)
    return f"NV{num_str}"


@transaction.atomic
def employee_create_with_contract(
    *,
    data: Dict[str, Any],
    contract_data: Dict[str, Any],
    creator: Optional[User] = None,
) -> tuple[Employee, EmploymentContract]:
    """
    Tạo mới một Employee, tài khoản User và hợp đồng lao động EmploymentContract bắt buộc đi kèm.
    """
    if not contract_data:
        raise ValidationException("Thông tin hợp đồng lao động là bắt buộc")

    if creator:
        PermissionChecker.check_permission(creator, "hrm.add_employee")
        PermissionChecker.check_permission(creator, "hrm.add_employmentcontract")

    employee_id = data.get("employee_id")
    if not employee_id:
        employee_id = generate_employee_id()
    elif not re.match(r"^NV\d{4,}$", employee_id):
        raise ValidationException("Mã nhân viên phải có format NV#### (ví dụ: NV0001)")

    if Employee.objects.filter(employee_id=employee_id).exists():
        raise ValidationException(f"Mã nhân viên {employee_id} đã tồn tại")

    # Tạo Employee
    employee = Employee.objects.create(
        employee_id=employee_id,
        full_name=data.get("full_name"),
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

    # Tạo EmploymentContract bắt buộc
    from apps.hrm.selectors import count_active_contracts

    active_count = count_active_contracts(employee)
    if active_count > 0:
        raise ValidationException(
            f"Nhân viên {employee.employee_id} đã có {active_count} hợp đồng đang active. "
            "Không thể tạo hợp đồng mới."
        )

    contract_no = contract_data.get("contract_no")
    if not contract_no:
        raise ValidationException("Số hợp đồng (contract_no) là bắt buộc")
    if EmploymentContract.objects.filter(contract_no=contract_no).exists():
        raise ValidationException(f"Số hợp đồng {contract_no} đã tồn tại")

    contract = EmploymentContract.objects.create(
        employee=employee,
        contract_no=contract_no,
        contract_type=contract_data.get("contract_type"),
        start_date=contract_data.get("start_date"),
        end_date=contract_data.get("end_date"),
        status="active",
        note=contract_data.get("note"),
        file_url=contract_data.get("file_url"),
        salary_base=(
            Decimal(str(contract_data["salary_base"])) if contract_data.get("salary_base") is not None else None
        ),
    )

    # Log contract creation
    contract_data_for_log = {
        "contract_no": contract.contract_no,
        "contract_type": contract.contract_type,
        "start_date": str(contract.start_date),
        "end_date": str(contract.end_date) if contract.end_date else None,
        "employee_id": str(employee.id),
        "salary_base": str(contract.salary_base) if contract.salary_base is not None else None,
    }
    create_system_log(
        user=creator,
        action="create",
        table_name="employment_contract",
        record_id=str(contract.id),
        new_value=contract_data_for_log,
    )

    return employee, contract


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
    if updater:
        PermissionChecker.check_permission(updater, "hrm.change_employee")

    fields_to_update = [
        "full_name",
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
    if creator:
        PermissionChecker.check_permission(creator, "hrm.add_employmentcontract")

    try:
        employee = Employee.objects.get(id=employee_id)
    except Employee.DoesNotExist:
        raise ValidationException("Nhân viên không tồn tại")

    contract_no = contract_data.get("contract_no")
    if not contract_no:
        raise ValidationException("Số hợp đồng (contract_no) là bắt buộc")

    if EmploymentContract.objects.filter(contract_no=contract_no).exists():
        raise ValidationException(f"Số hợp đồng {contract_no} đã tồn tại")

    # 1. Tìm các hợp đồng active cũ của nhân viên để chuyển sang expired hoặc điều chỉnh ngày (overlap)
    from apps.hrm.selectors import count_active_contracts

    active_count = count_active_contracts(employee)
    if active_count > 1:
        raise ValidationException(
            f"Nhân viên {employee.employee_id} đã có {active_count} hợp đồng đang active. "
            "Vui lòng dọn dẹp dữ liệu trước khi tạo mới."
        )

    # Lấy start_date mới
    new_start = contract_data.get("start_date")
    if not new_start:
        new_start = date.today()
        contract_data["start_date"] = new_start

    active_contracts = EmploymentContract.objects.select_for_update().filter(employee=employee, status="active")
    for old_contract in active_contracts:
        if new_start < old_contract.start_date:
            raise ValidationException(
                f"start_date mới ({new_start}) phải >= start_date HĐLĐ cũ ({old_contract.start_date})"
            )

        old_status = old_contract.status
        old_end_date = old_contract.end_date

        # CHUYỂN status sang expired TRƯỚC khi tạo HĐ mới để không vi phạm partial unique index
        old_contract.status = "expired"

        if old_contract.end_date and new_start <= old_contract.end_date:
            new_end_for_old = new_start - timedelta(days=1)
            old_contract.end_date = new_end_for_old
            old_contract.save(update_fields=["status", "end_date"])

            # Log old contract update
            create_system_log(
                user=creator,
                action="update",
                table_name="employment_contract",
                record_id=str(old_contract.id),
                old_value={"status": old_status, "end_date": str(old_end_date) if old_end_date else None},
                new_value={"status": "expired", "end_date": str(new_end_for_old)},
            )
        else:
            old_contract.save(update_fields=["status"])

            # Log old contract update
            create_system_log(
                user=creator,
                action="update",
                table_name="employment_contract",
                record_id=str(old_contract.id),
                old_value={"status": old_status},
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
        salary_base=(
            Decimal(str(contract_data["salary_base"])) if contract_data.get("salary_base") is not None else None
        ),
    )

    # Log new contract creation
    contract_log_data = {
        "contract_no": contract.contract_no,
        "contract_type": contract.contract_type,
        "start_date": str(contract.start_date),
        "end_date": str(contract.end_date) if contract.end_date else None,
        "status": contract.status,
        "salary_base": str(contract.salary_base) if contract.salary_base is not None else None,
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
def contract_renew(
    *,
    contract_id: str,
    new_contract_no: Optional[str] = None,
    new_contract_type: Optional[str] = None,
    start_date: Optional[date] = None,
    new_salary_base: Optional[Decimal] = None,
    file_url: Optional[str] = None,
    note: Optional[str] = None,
    renewer: Optional[User] = None,
) -> Dict[str, Any]:
    """
    Gia hạn hợp đồng lao động (tái ký) cho nhân viên, có thể kèm điều chỉnh lương.
    """
    if renewer:
        PermissionChecker.check_permission(renewer, "hrm.change_employmentcontract")
        if new_salary_base is not None:
            PermissionChecker.check_permission(renewer, "hrm.change_employee")

    try:
        old_contract = EmploymentContract.objects.select_for_update().get(id=contract_id)
    except EmploymentContract.DoesNotExist:
        raise ValidationException("Hợp đồng không tồn tại")

    employee = old_contract.employee
    actual_start = start_date or (old_contract.end_date + timedelta(days=1) if old_contract.end_date else date.today())
    if actual_start < old_contract.start_date:
        raise ValidationException(
            f"start_date mới ({actual_start}) phải >= start_date HĐLĐ cũ ({old_contract.start_date})"
        )

    # 1. Xử lý HĐLĐ cũ: nếu overlap thì rút end_date, nếu không thì set expired
    old_status = old_contract.status
    old_end_date = old_contract.end_date
    old_contract.status = "expired"

    if old_contract.end_date and actual_start <= old_contract.end_date:
        new_end_for_old = actual_start - timedelta(days=1)
        old_contract.end_date = new_end_for_old
        old_contract.save(update_fields=["status", "end_date"])

        create_system_log(
            user=renewer,
            action="update",
            table_name="employment_contract",
            record_id=str(old_contract.id),
            old_value={"status": old_status, "end_date": str(old_end_date) if old_end_date else None},
            new_value={"status": "expired", "end_date": str(new_end_for_old)},
        )
    else:
        old_contract.save(update_fields=["status"])

        create_system_log(
            user=renewer,
            action="update",
            table_name="employment_contract",
            record_id=str(old_contract.id),
            old_value={"status": old_status},
            new_value={"status": "expired"},
        )

    # 2. Tạo HĐLĐ mới
    new_contract = EmploymentContract.objects.create(
        employee=employee,
        contract_no=new_contract_no or f"{old_contract.contract_no}-RENEW",
        contract_type=new_contract_type or old_contract.contract_type,
        start_date=actual_start,
        status="active",
        file_url=file_url,
        note=note,
        salary_base=new_salary_base if new_salary_base is not None else old_contract.salary_base,
    )

    create_system_log(
        user=renewer,
        action="create",
        table_name="employment_contract",
        record_id=str(new_contract.id),
        new_value={
            "contract_no": new_contract.contract_no,
            "contract_type": new_contract.contract_type,
            "start_date": str(new_contract.start_date),
            "status": new_contract.status,
            "renewed_from": str(old_contract.id),
            "salary_base": str(new_contract.salary_base) if new_contract.salary_base is not None else None,
        },
    )

    # 4. Lưu file scan hợp đồng (nếu có)
    if file_url:
        doc = EmployeeDocument.objects.create(
            employee=employee,
            doc_type="contract_scan",
            title=f"Scan HĐLĐ gia hạn {new_contract.contract_no}",
            file_url=file_url,
            uploaded_by=renewer,
        )

        create_system_log(
            user=renewer,
            action="create",
            table_name="employee_document",
            record_id=str(doc.id),
            new_value={
                "doc_type": doc.doc_type,
                "title": doc.title,
                "file_url": doc.file_url,
            },
        )
    return {"contract": new_contract}


@transaction.atomic
def contract_terminate(
    *,
    contract_id: str,
    termination_date: date,
    reason: str,
    terminator: Optional[User] = None,
    file_url: Optional[str] = None,
    is_lawful: bool = True,
    unused_leave_days: Decimal = Decimal("0.00"),
    standard_working_days: int = 26,
    unnotified_days: int = 0,
) -> EmploymentContract:
    """
    Chấm dứt hợp đồng lao động:
    - Ràng buộc: Kiểm tra không nợ bất kỳ kỳ lương nào trước đó.
    - Quyết toán & thanh toán kỳ lương hiện tại (lương thực tế, phép năm, đóng BHXH, phạt nghỉ ngang).
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
        is_lawful: Nghỉ việc hợp pháp (đúng luật)
        unused_leave_days: Số ngày phép năm chưa nghỉ cần thanh toán
        standard_working_days: Số ngày công chuẩn của tháng (default 26)
        unnotified_days: Số ngày nghỉ không báo trước (nếu nghỉ trái luật)

    Returns:
        EmploymentContract: Hợp đồng đã chấm dứt
    """
    if terminator:
        PermissionChecker.check_permission(terminator, "hrm.change_employmentcontract")

    try:
        contract = EmploymentContract.objects.select_for_update().get(id=contract_id)
    except EmploymentContract.DoesNotExist:
        raise ValidationException("Hợp đồng không tồn tại")

    if contract.status == "terminated":
        raise ValidationException("Hợp đồng này đã được chấm dứt trước đó")

    employee = contract.employee

    # 1. Kiểm tra nợ kỳ lương trước đó
    current_period = termination_date.strftime("%Y-%m")
    unpaid_slips = SalarySlip.objects.filter(employee=employee, salary_period__lt=current_period).exclude(status="paid")

    if unpaid_slips.exists():
        periods = [slip.salary_period for slip in unpaid_slips]
        raise ValidationException(
            f"Không thể chấm dứt hợp đồng do nhân viên vẫn còn nợ lương kỳ trước chưa thanh toán ({', '.join(periods)}). Vui lòng thanh toán trước."
        )

    # 2. Tạo hoặc lấy SalarySlip
    slip_name = f"FINAL-SALARY-{employee.employee_id}-{current_period}"
    slip, created = SalarySlip.objects.get_or_create(
        employee=employee,
        salary_period=current_period,
        defaults={
            "name": slip_name,
            "base_salary": Decimal("0.00"),
            "overtime_amount": Decimal("0.00"),
            "allowance_amount": Decimal("0.00"),
            "reward_amount_total": Decimal("0.00"),
            "discipline_deduction_total": Decimal("0.00"),
            "gross_pay": Decimal("0.00"),
            "deductions": Decimal("0.00"),
            "net_pay": Decimal("0.00"),
            "status": "draft",
        },
    )

    # 3. Set breakdown.is_partial (để payroll_calculate_terminated_salary tính prorated)
    year = termination_date.year
    month = termination_date.month
    import calendar

    last_day = calendar.monthrange(year, month)[1]
    period_end_date = date(year, month, last_day)

    # Đánh dấu is_partial=True với period_end là termination_date để tính prorated trong kỳ lương
    slip.breakdown = {
        "is_partial": True,
        "period_start": str(date(year, month, 1)),
        "period_end": str(termination_date),
        "is_lawful": is_lawful,
        "unused_leave_days": float(unused_leave_days),
        "unnotified_days": unnotified_days,
        "standard_working_days": standard_working_days,
    }
    slip.save(update_fields=["breakdown"])

    # 4. Gọi hàm payroll_calculate_terminated_salary
    try:
        payroll_calculate_terminated_salary(
            salary_slip_id=str(slip.id),
            termination_date=termination_date,
            is_lawful=is_lawful,
            unused_leave_days=unused_leave_days,
            unnotified_days=unnotified_days,
            standard_working_days=standard_working_days,
            creator=terminator,
        )
    except ValidationException as e:
        raise ValidationException(f"Không thể tính lương quyết toán cho {employee.full_name}: {str(e)}")

    # 5. Gửi duyệt phiếu lương quyết toán cho Finance (set status = pending_finance_review)
    try:
        payroll_submit_for_review(
            salary_slip_id=str(slip.id),
            user=terminator,
            bypass_current_period_check=True,
        )
    except ValidationException as e:
        raise ValidationException(f"Không thể gửi phiếu lương quyết toán cho Finance: {str(e)}")

    # 3. Cập nhật EmploymentContract
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

    # 4. Cập nhật Employee sang inactive và điền leave_date
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

    # 5. Xóa tài khoản User liên kết qua employee_id
    _delete_linked_user(employee=employee, terminator=terminator)

    # 6. Lưu tài liệu quyết định thôi việc nếu có file_url
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
def employee_adjust_salary_apply(
    *,
    employee_id: str,
    new_salary_base: Decimal,
    reason: Optional[str] = None,
    actor: Optional[User] = None,
) -> Dict[str, Any]:
    """
    Áp dụng điều chỉnh lương cơ bản (Cách B - apply trực tiếp).
    """
    if actor:
        PermissionChecker.check_permission(actor, "hrm.adjust_salary")

    today = date.today()

    try:
        employee = Employee.objects.select_for_update().get(id=employee_id)
    except Employee.DoesNotExist:
        raise NotFoundException("Nhân viên không tồn tại")

    if new_salary_base is None:
        raise ValidationException("Lương cơ bản mới là bắt buộc")
    new_salary_base = Decimal(str(new_salary_base))

    # Tìm HĐLĐ active
    active_contract = (
        EmploymentContract.objects.select_for_update()
        .filter(employee=employee, status="active")
        .order_by("-start_date")
        .first()
    )

    # Quyết định: update hoặc tạo mới
    if active_contract and (active_contract.end_date is None or today <= active_contract.end_date):
        # Case 1: HĐLĐ active còn hạn -> UPDATE
        old_salary = active_contract.salary_base
        active_contract.salary_base = new_salary_base
        active_contract.save(update_fields=["salary_base", "updated_at"])

        create_system_log(
            user=actor,
            action="update",
            table_name="employment_contract",
            record_id=str(active_contract.id),
            old_value={"salary_base": str(old_salary) if old_salary else None},
            new_value={"salary_base": str(new_salary_base), "effective_date": str(today)},
        )
        result_contract = active_contract
    else:
        # Case 2: HĐLĐ active hết hạn (hoặc chưa có) -> TẠO MỚI
        if active_contract:
            old_status = active_contract.status
            active_contract.status = "expired"
            if active_contract.end_date is None or today <= active_contract.end_date:
                active_contract.end_date = today - timedelta(days=1)
            active_contract.save(update_fields=["status", "end_date", "updated_at"])

            create_system_log(
                user=actor,
                action="update",
                table_name="employment_contract",
                record_id=str(active_contract.id),
                old_value={"status": old_status},
                new_value={"status": "expired", "end_date": str(active_contract.end_date)},
            )

        new_contract = EmploymentContract.objects.create(
            employee=employee,
            contract_no=f"ADJ-{today.strftime('%Y%m%d')}-{employee.employee_id}",
            contract_type=active_contract.contract_type if active_contract else "indefinite_term",
            start_date=today,
            end_date=None,
            status="active",
            salary_base=new_salary_base,
        )

        create_system_log(
            user=actor,
            action="create",
            table_name="employment_contract",
            record_id=str(new_contract.id),
            new_value={
                "contract_no": new_contract.contract_no,
                "salary_base": str(new_salary_base),
                "start_date": str(today),
                "status": "active",
            },
        )
        result_contract = new_contract

    # Tính lại payslip kỳ hiện tại (status < paid, bao gồm partial)
    affected_slips = []
    salary_period = today.strftime("%Y-%m")
    slips_to_recalc = SalarySlip.objects.filter(employee=employee, salary_period=salary_period).exclude(status="paid")

    for slip in slips_to_recalc:
        try:
            updated_slip = payroll_calculate_salary(
                salary_slip_id=str(slip.id),
                creator=actor,
            )
            affected_slips.append(updated_slip)
        except ValidationException:
            continue

    return {"contract": result_contract, "affected_payslips": affected_slips}


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
    if creator:
        PermissionChecker.check_permission(creator, "hrm.add_attendance")

    from apps.hrm.selectors import is_salary_period_fully_paid

    salary_period = f"{date.year:04d}-{date.month:02d}"
    if is_salary_period_fully_paid(salary_period):
        raise ValidationException(
            f"Kỳ lương {salary_period} đã được thanh toán 100%. Không cho phép chỉnh sửa chấm công."
        )

    employee_ids = [rec.get("employee_id") for rec in records if rec.get("employee_id")]
    employees = {str(emp.id): emp for emp in Employee.objects.filter(id__in=employee_ids)}

    existing_attendances = {
        str(att.employee_id): att
        for att in Attendance.objects.select_for_update().filter(date=date, employee_id__in=employee_ids)
    }

    result = []
    for rec in records:
        employee_id = rec.get("employee_id")
        status = rec.get("status")
        if not employee_id or not status:
            raise ValidationException("Thông tin nhân viên và trạng thái chấm công là bắt buộc")

        employee = employees.get(str(employee_id))
        if not employee:
            raise ValidationException(f"Nhân viên ID {employee_id} không tồn tại")

        work_hours = Decimal(str(rec.get("work_hours", 8.00)))
        overtime_hours = Decimal(str(rec.get("overtime_hours", 0.00)))
        remarks = rec.get("remarks")

        attendance = existing_attendances.get(str(employee_id))
        if not attendance:
            # Tạo mới nếu chưa tồn tại
            attendance = Attendance.objects.create(
                employee=employee,
                date=date,
                status=status,
                work_hours=work_hours,
                overtime_hours=overtime_hours,
                remarks=remarks,
            )
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
        else:
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

        result.append(attendance)

    return result


@transaction.atomic
def leave_request_create(
    *,
    employee_id: str,
    data: Dict[str, Any],
    creator: Optional[User] = None,
) -> LeaveRequest:
    """
    Tạo đơn xin nghỉ phép của nhân viên (mặc định trạng thái pending).
    """
    if creator:
        PermissionChecker.check_permission(creator, "hrm.add_leaverequest")

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
        user=creator,
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
    approved_by: Optional[User] = None,
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

    if leave_request.employee.employment_status != "active":
        raise ValidationException("Nhân viên xin nghỉ phép phải ở trạng thái đang làm việc (active).")

    if not approved_by:
        try:
            approved_by = User.objects.get(id=approved_by_user_id)
        except User.DoesNotExist:
            raise ValidationException("Người phê duyệt không tồn tại")

    PermissionChecker.check_permission(approved_by, "hrm.change_leaverequest")

    from apps.hrm.selectors import is_salary_period_fully_paid

    start = leave_request.start_date
    end = leave_request.end_date
    unique_periods = set()
    current_date = start
    while current_date <= end:
        unique_periods.add(f"{current_date.year:04d}-{current_date.month:02d}")
        current_date += timedelta(days=1)

    for period in unique_periods:
        if is_salary_period_fully_paid(period):
            raise ValidationException(
                f"Kỳ lương {period} đã được thanh toán 100%. Không cho phép duyệt đơn xin nghỉ phép trong thời gian này."
            )

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
        "paid": "paid_leave",
        "unpaid": "unpaid_leave",
    }
    attendance_status = status_map.get(leave_request.leave_type, "unpaid_leave")

    start = leave_request.start_date
    end = leave_request.end_date

    # 1. Lấy toàn bộ Attendance hiện tại trong khoảng ngày phép bằng 1 câu truy vấn duy nhất (select_for_update)
    existing_attendances = {
        att.date: att
        for att in Attendance.objects.select_for_update().filter(
            employee=leave_request.employee, date__gte=start, date__lte=end
        )
    }

    atts_to_create = []
    atts_to_update = []
    current_date = start

    while current_date <= end:
        attendance = existing_attendances.get(current_date)
        if attendance:
            if attendance.status != attendance_status:
                # Cảnh báo qua logger nếu ghi đè ngày công thực tế (có work_hours hoặc overtime_hours > 0)
                if attendance.work_hours > 0 or attendance.overtime_hours > 0:
                    logger.warning(
                        f"Overwriting working attendance for employee {leave_request.employee.employee_id} "
                        f"on {current_date}: work_hours={attendance.work_hours}, overtime_hours={attendance.overtime_hours}"
                    )

                # Lưu thông tin cũ cho log
                attendance._old_values = {
                    "status": attendance.status,
                    "work_hours": str(attendance.work_hours),
                    "overtime_hours": str(attendance.overtime_hours),
                    "remarks": attendance.remarks,
                }

                attendance.status = attendance_status
                attendance.work_hours = Decimal("0.00")
                attendance.overtime_hours = Decimal("0.00")
                attendance.remarks = f"Tự động đồng bộ từ Đơn nghỉ phép ID {leave_request.id}"
                atts_to_update.append(attendance)
        else:
            new_att = Attendance(
                employee=leave_request.employee,
                date=current_date,
                status=attendance_status,
                work_hours=Decimal("0.00"),
                overtime_hours=Decimal("0.00"),
                remarks=f"Tự động đồng bộ từ Đơn nghỉ phép ID {leave_request.id}",
            )
            atts_to_create.append(new_att)

        current_date += timedelta(days=1)

    # 2. Thực hiện ghi/cập nhật hàng loạt (Bulk Operations)
    if atts_to_create:
        created_records = Attendance.objects.bulk_create(atts_to_create)

        # Ghi logs hệ thống hàng loạt cho các bản ghi mới tạo
        from apps.accounts.models import SystemLog

        new_logs = [
            SystemLog(
                user=approved_by,
                action="create",
                table_name="attendance",
                record_id=str(att.id),
                new_value={
                    "employee_id": str(leave_request.employee.id),
                    "date": str(att.date),
                    "status": attendance_status,
                    "work_hours": "0.00",
                    "overtime_hours": "0.00",
                    "remarks": att.remarks,
                },
            )
            for att in created_records
        ]
        SystemLog.objects.bulk_create(new_logs)

    if atts_to_update:
        Attendance.objects.bulk_update(atts_to_update, ["status", "work_hours", "overtime_hours", "remarks"])

        # Ghi logs hệ thống hàng loạt cho các bản ghi được cập nhật
        from apps.accounts.models import SystemLog

        update_logs = [
            SystemLog(
                user=approved_by,
                action="update",
                table_name="attendance",
                record_id=str(att.id),
                old_value=att._old_values,
                new_value={
                    "status": attendance_status,
                    "work_hours": "0.00",
                    "overtime_hours": "0.00",
                    "remarks": att.remarks,
                },
            )
            for att in atts_to_update
        ]
        SystemLog.objects.bulk_create(update_logs)

    return leave_request


@transaction.atomic
def reward_record_create(
    *,
    employee_id: str,
    data: Dict[str, Any],
    creator: Optional[User] = None,
) -> RewardRecord:
    """
    Ghi nhận khen thưởng của nhân viên.
    """
    if creator:
        PermissionChecker.check_permission(creator, "hrm.add_rewardrecord")

    try:
        employee = Employee.objects.get(id=employee_id)
    except Employee.DoesNotExist:
        raise ValidationException("Nhân viên không tồn tại")

    reward_date = data.get("reward_date")
    if reward_date:
        if isinstance(reward_date, str):
            reward_date = datetime.strptime(reward_date, "%Y-%m-%d").date()
        reward_period = reward_date.strftime("%Y-%m")
        from apps.hrm.selectors import is_salary_period_fully_paid

        if is_salary_period_fully_paid(reward_period):
            raise ValidationException(
                f"Kỳ lương {reward_period} đã được thanh toán 100%. Không cho phép ghi nhận khen thưởng trong kỳ này."
            )

    amount = data.get("amount")
    if amount is not None:
        amount = Decimal(str(amount))

    salary_slip_id = data.get("salary_slip_id")
    if salary_slip_id:
        from apps.finance.models import SalarySlip

        try:
            slip = SalarySlip.objects.get(id=salary_slip_id)
        except SalarySlip.DoesNotExist:
            raise ValidationException("Phiếu lương không tồn tại")
        if str(slip.employee.id) != str(employee.id):
            raise ValidationException("Phiếu lương không thuộc về nhân viên này")
        if slip.status == "paid":
            raise ValidationException("Không thể gán khen thưởng cho phiếu lương đã chi trả")

    reward = RewardRecord.objects.create(
        employee=employee,
        reward_date=data.get("reward_date"),
        reward_type=data.get("reward_type"),
        amount=amount,
        description=data.get("description"),
        salary_slip_id=salary_slip_id,
        status="pending_approval",
    )

    create_system_log(
        user=creator,
        action="create",
        table_name="reward_record",
        record_id=str(reward.id),
        new_value={
            "employee_id": str(employee.id),
            "reward_date": str(reward.reward_date),
            "reward_type": reward.reward_type,
            "amount": str(reward.amount) if reward.amount is not None else None,
            "description": reward.description,
        },
    )

    return reward


@transaction.atomic
def discipline_record_create(
    *,
    employee_id: str,
    data: Dict[str, Any],
    creator: Optional[User] = None,
) -> DisciplineRecord:
    """
    Ghi nhận kỷ luật của nhân viên.
    """
    if creator:
        PermissionChecker.check_permission(creator, "hrm.add_disciplinerecord")

    try:
        employee = Employee.objects.get(id=employee_id)
    except Employee.DoesNotExist:
        raise ValidationException("Nhân viên không tồn tại")

    incident_date = data.get("incident_date")
    discipline_date = data.get("discipline_date")
    checked_periods = set()
    for dt in [incident_date, discipline_date]:
        if dt:
            if isinstance(dt, str):
                dt = datetime.strptime(dt, "%Y-%m-%d").date()
            checked_periods.add(dt.strftime("%Y-%m"))

    from apps.hrm.selectors import is_salary_period_fully_paid

    for period in checked_periods:
        if is_salary_period_fully_paid(period):
            raise ValidationException(
                f"Kỳ lương {period} đã được thanh toán 100%. Không cho phép ghi nhận kỷ luật trong kỳ này."
            )

    penalty_amount = data.get("penalty_amount")
    if penalty_amount is not None:
        penalty_amount = Decimal(str(penalty_amount))

    salary_slip_id = data.get("salary_slip_id")
    if salary_slip_id:
        from apps.finance.models import SalarySlip

        try:
            slip = SalarySlip.objects.get(id=salary_slip_id)
        except SalarySlip.DoesNotExist:
            raise ValidationException("Phiếu lương không tồn tại")
        if str(slip.employee.id) != str(employee.id):
            raise ValidationException("Phiếu lương không thuộc về nhân viên này")
        if slip.status == "paid":
            raise ValidationException("Không thể gán kỷ luật cho phiếu lương đã chi trả")

    discipline = DisciplineRecord.objects.create(
        employee=employee,
        incident_date=data.get("incident_date"),
        discipline_date=data.get("discipline_date"),
        discipline_type=data.get("discipline_type"),
        description=data.get("description"),
        penalty_amount=penalty_amount,
        salary_slip_id=salary_slip_id,
        file_url=data.get("file_url"),
        status="pending_approval",
    )

    create_system_log(
        user=creator,
        action="create",
        table_name="discipline_record",
        record_id=str(discipline.id),
        new_value={
            "employee_id": str(employee.id),
            "incident_date": str(discipline.incident_date),
            "discipline_date": str(discipline.discipline_date),
            "discipline_type": discipline.discipline_type,
            "penalty_amount": str(discipline.penalty_amount) if discipline.penalty_amount is not None else None,
            "description": discipline.description,
            "file_url": discipline.file_url,
        },
    )

    return discipline


def get_holiday_dates_for_period(
    year: int,
    month: int,
    end_limit_date: Optional[date] = None,
) -> tuple[set[date], set[date]]:
    """
    Xác định (official_holiday_dates, compensatory_holiday_dates) trong tháng/năm.
    Hỗ trợ chế độ làm việc cố định 6 ngày/tuần (Nghỉ Chủ Nhật).
    """
    import calendar

    from django.conf import settings

    weekly_rest_days = getattr(settings, "HRM_WEEKLY_REST_DAYS", [6])
    period_start_date = date(year, month, 1)

    # Sử dụng khoảng đệm cố định 30 ngày để tối ưu index (Rule 3)
    fetch_start = period_start_date - timedelta(days=30)

    last_day = calendar.monthrange(year, month)[1]
    upper_bound = end_limit_date or date(year, month, last_day)

    # Lấy các ngày nghỉ lễ chính thức
    public_holidays = PublicHoliday.objects.filter(start_date__gte=fetch_start, start_date__lte=upper_bound).order_by(
        "start_date"
    )

    official_holiday_dates = set()
    for holiday in public_holidays:
        for i in range(holiday.days):
            h_date = holiday.start_date + timedelta(days=i)
            official_holiday_dates.add(h_date)

    # Tính toán ngày nghỉ bù
    sorted_official = sorted(list(official_holiday_dates))
    compensatory_holiday_dates = set()

    for h_date in sorted_official:
        if h_date.weekday() in weekly_rest_days:
            # Lễ trùng với ngày nghỉ hằng tuần, nghỉ bù vào ngày làm việc kế tiếp
            comp_date = h_date + timedelta(days=1)
            while (
                comp_date.weekday() in weekly_rest_days
                or comp_date in official_holiday_dates
                or comp_date in compensatory_holiday_dates
            ):
                comp_date += timedelta(days=1)
            compensatory_holiday_dates.add(comp_date)

    # Lọc lại chỉ giữ các ngày nằm trong tháng/năm mục tiêu và trước hoặc bằng upper_bound
    final_official = set()
    for d in official_holiday_dates:
        if d.year == year and d.month == month:
            if not end_limit_date or d <= end_limit_date:
                final_official.add(d)

    final_compensatory = set()
    for d in compensatory_holiday_dates:
        if d.year == year and d.month == month:
            if not end_limit_date or d <= end_limit_date:
                final_compensatory.add(d)

    return final_official, final_compensatory


@transaction.atomic
def payroll_initialize_period(
    *,
    salary_period: str,
    creator: Optional[User] = None,
) -> list[SalarySlip]:
    """
    Khởi tạo hàng loạt bản ghi SalarySlip ở trạng thái draft cho toàn bộ nhân sự đang active trong kỳ lương.
    Cho phép khởi tạo bổ sung cho nhân sự mới.
    """
    if creator:
        PermissionChecker.check_permission(creator, "finance.add_salaryslip")

    from apps.accounts.models import SystemLog
    from apps.finance.models import SalarySlip

    active_employees = list(Employee.objects.filter(employment_status="active"))

    # 1. Lấy danh sách nhân viên đã có phiếu lương trong kỳ (1 query)
    existing_employee_ids = set(
        SalarySlip.objects.filter(salary_period=salary_period).values_list("employee_id", flat=True)
    )

    if existing_employee_ids:
        raise ValidationException("Kỳ lương đã được khởi tạo trước đó.")

    new_slips = []
    for employee in active_employees:
        if employee.id not in existing_employee_ids:
            name = f"SALARY-{employee.employee_id}-{salary_period}"
            new_slips.append(
                SalarySlip(
                    employee=employee,
                    salary_period=salary_period,
                    name=name,
                    base_salary=Decimal("0.00"),
                    overtime_amount=Decimal("0.00"),
                    allowance_amount=Decimal("0.00"),
                    reward_amount_total=Decimal("0.00"),
                    discipline_deduction_total=Decimal("0.00"),
                    gross_pay=Decimal("0.00"),
                    deductions=Decimal("0.00"),
                    net_pay=Decimal("0.00"),
                    status="draft",
                )
            )

    if new_slips:
        # bulk create slips
        created_slips = SalarySlip.objects.bulk_create(new_slips, ignore_conflicts=True)

        # bulk create logs (Ghi nhận log CREATE ở trạng thái draft trước)
        logs = [
            SystemLog(
                user=creator,
                action="create",
                table_name="salary_slip",
                record_id=str(slip.id),
                new_value={
                    "name": slip.name,
                    "employee_id": str(slip.employee_id),
                    "salary_period": salary_period,
                    "status": "draft",
                },
            )
            for slip in created_slips
        ]
        SystemLog.objects.bulk_create(logs)

        # Tự động tính toán lương sau khi khởi tạo (sử dụng holidays_cache để tránh N+1 queries)
        # Quá trình này sẽ tiếp tục cập nhật phiếu lương và tự động ghi log UPDATE vào DB sau log CREATE
        year, month = map(int, salary_period.split("-"))
        holidays_cache = get_holiday_dates_for_period(year, month)
        for slip in created_slips:
            payroll_calculate_salary(salary_slip_id=str(slip.id), creator=creator, holidays_cache=holidays_cache)

    return list(SalarySlip.objects.filter(salary_period=salary_period).select_related("employee"))


@transaction.atomic
def payroll_calculate_salary(
    *,
    salary_slip_id: str,
    creator: Optional[User] = None,
    holidays_cache: Optional[tuple[set[date], set[date]]] = None,
) -> SalarySlip:
    """
    Tính toán chi tiết phiếu lương dựa trên chấm công, phụ cấp, thưởng, phạt trong kỳ.
    """
    if creator:
        PermissionChecker.check_permission(creator, "finance.change_salaryslip")

    from django.conf import settings

    weekly_rest_days = getattr(settings, "HRM_WEEKLY_REST_DAYS", [6])
    standard_days = getattr(settings, "HRM_STANDARD_WORKING_DAYS", 26)
    compensatory_ot_rate = Decimal(str(getattr(settings, "HRM_COMPENSATORY_OVERTIME_RATE", 2.0)))

    try:
        slip = SalarySlip.objects.get(id=salary_slip_id)
    except SalarySlip.DoesNotExist:
        raise ValidationException("Phiếu lương không tồn tại")

    if slip.status == "paid":
        raise ValidationException("Không thể tính lại phiếu lương đã thanh toán.")

    employee = slip.employee

    # Lưu thông tin partial nếu có để bảo lưu
    is_partial = False
    p_start = None
    p_end = None
    if slip.breakdown and slip.breakdown.get("is_partial"):
        is_partial = True
        p_start = slip.breakdown.get("period_start")
        p_end = slip.breakdown.get("period_end")

    # 1. Tính toán ngày công từ Attendance trong kỳ (hỗ trợ partial slip)
    if is_partial and p_start and p_end:
        period_start_date = date.fromisoformat(p_start)
        period_end_date = date.fromisoformat(p_end)
        year = period_start_date.year
        month = period_start_date.month
    else:
        year, month = map(int, slip.salary_period.split("-"))
        import calendar

        last_day = calendar.monthrange(year, month)[1]
        period_start_date = date(year, month, 1)
        period_end_date = date(year, month, last_day)

    salary_base = get_salary_at_date(employee, period_end_date) or Decimal("0.00")

    attendances = Attendance.objects.filter(employee=employee, date__year=year, date__month=month)

    # Fetch public holidays and compensatory holidays for this period (use cache if provided)
    if holidays_cache:
        official_holiday_dates, compensatory_holiday_dates = holidays_cache
    else:
        official_holiday_dates, compensatory_holiday_dates = get_holiday_dates_for_period(year, month)
    all_holiday_dates = official_holiday_dates | compensatory_holiday_dates

    working_days = Decimal("0.00")
    paid_leave_days = Decimal("0.00")
    ot_normal_hours = Decimal("0.00")
    ot_weekend_hours = Decimal("0.00")
    ot_holiday_hours = Decimal("0.00")
    ot_compensatory_hours = Decimal("0.00")

    # Chuẩn bị Attendance dict
    attendance_dict = {att.date: att for att in attendances}

    # 2. Tính lương Prorated theo các segment
    timeline = get_salary_timeline(employee, period_start_date, period_end_date)
    segments = split_into_segments(timeline, period_start_date, period_end_date)

    salary_segments_breakdown = []
    base_salary_earned = Decimal("0.00")

    total_working_days = Decimal("0.00")
    total_paid_leave_days = Decimal("0.00")

    for seg_start, seg_end, seg_salary in segments:
        seg_working_days = Decimal("0.00")
        seg_paid_leave_days = Decimal("0.00")

        current_date = seg_start
        while current_date <= seg_end:
            # Kiểm tra quan hệ lao động
            day_salary, day_contract = get_salary_for_day(employee, current_date)
            if day_contract is not None:
                att = attendance_dict.get(current_date)
                if att:
                    if att.status == "working" and (att.work_hours or 0) > 0:
                        seg_working_days += Decimal("1.00")
                    elif att.status in ["paid_leave", "holiday"]:
                        seg_paid_leave_days += Decimal("1.00")

                    # Tính OT cho ngày này
                    ot_h = att.overtime_hours or Decimal("0.00")
                    if ot_h > 0:
                        if current_date in official_holiday_dates:
                            ot_holiday_hours += ot_h
                        elif current_date in compensatory_holiday_dates:
                            ot_compensatory_hours += ot_h
                        elif current_date.weekday() in weekly_rest_days:
                            ot_weekend_hours += ot_h
                        else:
                            ot_normal_hours += ot_h
                else:
                    # Tự động tính 100% lương cho ngày nghỉ lễ/nghỉ bù nếu chưa có chấm công
                    if current_date in all_holiday_dates:
                        seg_paid_leave_days += Decimal("1.00")

            current_date += timedelta(days=1)

        seg_total_days = seg_working_days + seg_paid_leave_days
        total_working_days += seg_working_days
        total_paid_leave_days += seg_paid_leave_days

        if standard_days > 0:
            seg_earned = seg_salary * (seg_total_days / Decimal(str(standard_days)))
        else:
            seg_earned = Decimal("0.00")
        seg_earned = seg_earned.quantize(Decimal("0.01"))

        base_salary_earned += seg_earned

        salary_segments_breakdown.append(
            {
                "start_date": seg_start.strftime("%Y-%m-%d"),
                "end_date": seg_end.strftime("%Y-%m-%d"),
                "salary_base": float(seg_salary),
                "work_days": float(seg_total_days),
                "earned": float(seg_earned),
            }
        )

    working_days = total_working_days
    paid_leave_days = total_paid_leave_days

    if standard_days > 0:
        hourly_rate = salary_base / Decimal(str(standard_days)) / Decimal("8.00")
        ot_normal_rate = hourly_rate * Decimal("1.5")
        ot_weekend_rate = hourly_rate * Decimal("2.0")
        ot_holiday_rate = hourly_rate * Decimal("3.0")
        ot_compensatory_rate = hourly_rate * compensatory_ot_rate

        ot_normal_amount = ot_normal_hours * ot_normal_rate
        ot_weekend_amount = ot_weekend_hours * ot_weekend_rate
        ot_holiday_amount = ot_holiday_hours * ot_holiday_rate
        ot_compensatory_amount = ot_compensatory_hours * ot_compensatory_rate

        overtime_amount_earned = ot_normal_amount + ot_weekend_amount + ot_holiday_amount + ot_compensatory_amount
    else:
        ot_normal_amount = Decimal("0.00")
        ot_weekend_amount = Decimal("0.00")
        ot_holiday_amount = Decimal("0.00")
        ot_compensatory_amount = Decimal("0.00")
        overtime_amount_earned = Decimal("0.00")
    overtime_amount_earned = overtime_amount_earned.quantize(Decimal("0.01"))

    from django.db.models import Q

    # Định nghĩa ngày bắt đầu của kỳ lương
    period_start_date = date(year, month, 1)

    # 2. Thưởng & Phạt trong kỳ (không gom bù)
    rewards = RewardRecord.objects.filter(
        employee=employee,
        reward_date__gte=period_start_date,
        reward_date__lte=period_end_date,
        status="approved",
    ).filter(Q(salary_slip__isnull=True) | Q(salary_slip=slip))

    reward_total = Decimal("0.00")
    rewards_to_update = []
    for r in rewards:
        reward_total += r.amount or Decimal("0.00")
        if r.salary_slip_id != slip.id:
            r.salary_slip = slip
            rewards_to_update.append(r)
    if rewards_to_update:
        RewardRecord.objects.bulk_update(rewards_to_update, ["salary_slip"])

    disciplines = DisciplineRecord.objects.filter(
        employee=employee,
        discipline_date__gte=period_start_date,
        discipline_date__lte=period_end_date,
        status="approved",
    ).filter(Q(salary_slip__isnull=True) | Q(salary_slip=slip))

    discipline_total = Decimal("0.00")
    disciplines_to_update = []
    for d in disciplines:
        discipline_total += d.penalty_amount or Decimal("0.00")
        if d.salary_slip_id != slip.id:
            d.salary_slip = slip
            disciplines_to_update.append(d)
    if disciplines_to_update:
        DisciplineRecord.objects.bulk_update(disciplines_to_update, ["salary_slip"])

    allowance_amount = Decimal("0.00")

    gross_pay = base_salary_earned + overtime_amount_earned + allowance_amount
    deductions = discipline_total
    net_pay = gross_pay + reward_total - deductions

    remarks = slip.remarks or ""
    if slip.payment_method == "cash" and net_pay >= Decimal("5000000.00"):
        warning_msg = "[CẢNH BÁO]: Lương thực nhận từ 5,000,000đ trở lên, khuyến nghị thanh toán bằng chuyển khoản để được tính chi phí hợp lý khi quyết toán thuế."
        if warning_msg not in remarks:
            remarks = f"{remarks}\n{warning_msg}".strip()

    old_slip_data = {
        "base_salary": str(slip.base_salary),
        "overtime_amount": str(slip.overtime_amount),
        "allowance_amount": str(slip.allowance_amount),
        "reward_amount_total": str(slip.reward_amount_total),
        "discipline_deduction_total": str(slip.discipline_deduction_total),
        "gross_pay": str(slip.gross_pay),
        "deductions": str(slip.deductions),
        "net_pay": str(slip.net_pay),
        "remarks": slip.remarks,
    }

    slip.base_salary = base_salary_earned
    slip.overtime_amount = overtime_amount_earned
    slip.allowance_amount = allowance_amount
    slip.reward_amount_total = reward_total
    slip.discipline_deduction_total = discipline_total
    slip.gross_pay = gross_pay
    slip.deductions = deductions
    slip.net_pay = net_pay
    slip.status = "calculated"
    slip.remarks = remarks

    total_days = float(working_days + paid_leave_days)
    total_days_str = f"{total_days:g}"

    incomes = [
        {
            "name": f"Lương theo ngày công ({total_days_str}/{standard_days} ngày)",
            "amount": float(base_salary_earned),
        }
    ]

    if overtime_amount_earned > 0:
        if ot_normal_hours > 0:
            incomes.append(
                {
                    "name": f"Lương tăng ca ngày thường (1.5x) ({float(ot_normal_hours):g} giờ)",
                    "amount": float(ot_normal_amount.quantize(Decimal("0.01"))),
                }
            )
        if ot_weekend_hours > 0:
            incomes.append(
                {
                    "name": f"Lương tăng ca Chủ nhật (2.0x) ({float(ot_weekend_hours):g} giờ)",
                    "amount": float(ot_weekend_amount.quantize(Decimal("0.01"))),
                }
            )
        if ot_holiday_hours > 0:
            incomes.append(
                {
                    "name": f"Lương tăng ca ngày Lễ/Tết (3.0x) ({float(ot_holiday_hours):g} giờ)",
                    "amount": float(ot_holiday_amount.quantize(Decimal("0.01"))),
                }
            )
        if ot_compensatory_hours > 0:
            rate_str = f"{float(compensatory_ot_rate):g}x"
            incomes.append(
                {
                    "name": f"Lương tăng ca ngày nghỉ bù ({rate_str}) ({float(ot_compensatory_hours):g} giờ)",
                    "amount": float(ot_compensatory_amount.quantize(Decimal("0.01"))),
                }
            )
    else:
        incomes.append(
            {
                "name": "Lương tăng ca (OT) (0 giờ)",
                "amount": 0.0,
            }
        )

    incomes.extend(
        [
            {"name": "Phụ cấp cố định", "amount": float(allowance_amount)},
            {"name": "Khen thưởng/Thưởng thêm", "amount": float(reward_total)},
        ]
    )

    slip.breakdown = {
        "standard_working_days": int(standard_days),
        "incomes": incomes,
        "deductions": [
            {"name": "Phạt kỷ luật/Khấu trừ", "amount": float(discipline_total)},
        ],
        "salary_segments": salary_segments_breakdown,
    }
    if is_partial:
        slip.breakdown["is_partial"] = True
        slip.breakdown["period_start"] = p_start
        slip.breakdown["period_end"] = p_end
    slip.save()

    create_system_log(
        user=creator,
        action="update",
        table_name="salary_slip",
        record_id=str(slip.id),
        old_value=old_slip_data,
        new_value={
            "base_salary": str(slip.base_salary),
            "overtime_amount": str(slip.overtime_amount),
            "allowance_amount": str(slip.allowance_amount),
            "reward_amount_total": str(slip.reward_amount_total),
            "discipline_deduction_total": str(slip.discipline_deduction_total),
            "gross_pay": str(slip.gross_pay),
            "deductions": str(slip.deductions),
            "net_pay": str(slip.net_pay),
            "remarks": slip.remarks,
        },
    )

    return slip


@transaction.atomic
def public_holiday_create(
    *,
    name: str,
    start_date: date,
    days: int = 1,
    description: str = "",
    creator: Optional[User] = None,
) -> PublicHoliday:
    """
    Khai báo ngày nghỉ lễ mới. Chặn ngày trong quá khứ.
    """
    if creator:
        PermissionChecker.check_permission(creator, "hrm.add_publicholiday")

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

    if days <= 0:
        raise ValidationException("Số ngày nghỉ phải lớn hơn 0.")

    if start_date < timezone.now().date():
        raise ValidationException("Không được chọn ngày nghỉ lễ trong quá khứ.")

    holiday = PublicHoliday.objects.create(
        name=name,
        start_date=start_date,
        days=days,
        description=description,
    )

    create_system_log(
        user=creator,
        action="create",
        table_name="public_holiday",
        record_id=str(holiday.id),
        new_value={
            "name": holiday.name,
            "start_date": str(holiday.start_date),
            "days": holiday.days,
            "description": holiday.description,
        },
    )

    return holiday


@transaction.atomic
def public_holiday_update(
    *,
    holiday: PublicHoliday,
    data: Dict[str, Any],
    updater: Optional[User] = None,
) -> PublicHoliday:
    """
    Cập nhật thông tin ngày nghỉ lễ. Chặn ngày trong quá khứ nếu ngày nghỉ bị thay đổi.
    """
    if updater:
        PermissionChecker.check_permission(updater, "hrm.change_publicholiday")

    if holiday.start_date <= timezone.now().date():
        raise ValidationException("Không được phép chỉnh sửa hoặc xóa ngày nghỉ lễ trong quá khứ hoặc đang diễn ra.")

    old_value = {
        "name": holiday.name,
        "start_date": str(holiday.start_date),
        "days": holiday.days,
        "description": holiday.description,
    }

    new_start_date = data.get("start_date")
    if new_start_date:
        if isinstance(new_start_date, str):
            new_start_date = datetime.strptime(new_start_date, "%Y-%m-%d").date()

        # Nếu ngày thay đổi, kiểm tra xem ngày mới có ở quá khứ không
        if new_start_date != holiday.start_date and new_start_date < timezone.now().date():
            raise ValidationException("Không được chọn ngày nghỉ lễ trong quá khứ.")
        holiday.start_date = new_start_date

    new_days = data.get("days")
    if new_days is not None:
        try:
            new_days = int(new_days)
        except (ValueError, TypeError):
            raise ValidationException("Số ngày nghỉ phải là số nguyên.")
        if new_days <= 0:
            raise ValidationException("Số ngày nghỉ phải lớn hơn 0.")
        holiday.days = new_days

    if "name" in data:
        holiday.name = data["name"]
    if "description" in data:
        holiday.description = data["description"]

    holiday.save()

    create_system_log(
        user=updater,
        action="update",
        table_name="public_holiday",
        record_id=str(holiday.id),
        old_value=old_value,
        new_value={
            "name": holiday.name,
            "start_date": str(holiday.start_date),
            "days": holiday.days,
            "description": holiday.description,
        },
    )

    return holiday


@transaction.atomic
def public_holiday_delete(
    *,
    holiday: PublicHoliday,
    deleter: Optional[User] = None,
) -> None:
    """
    Xóa ngày nghỉ lễ.
    """
    if deleter:
        PermissionChecker.check_permission(deleter, "hrm.delete_publicholiday")

    if holiday.start_date <= timezone.now().date():
        raise ValidationException("Không được phép chỉnh sửa hoặc xóa ngày nghỉ lễ trong quá khứ hoặc đang diễn ra.")

    old_value = {
        "name": holiday.name,
        "start_date": str(holiday.start_date),
        "days": holiday.days,
        "description": holiday.description,
    }
    record_id = str(holiday.id)
    holiday.delete()

    create_system_log(
        user=deleter,
        action="delete",
        table_name="public_holiday",
        record_id=record_id,
        old_value=old_value,
        new_value={},
    )


@transaction.atomic
def reward_record_approve(*, user: User, reward_id: str) -> RewardRecord:
    """
    Phê duyệt quyết định khen thưởng của nhân viên.
    """
    PermissionChecker.check_permission(user, "hrm.change_rewardrecord")

    reward = RewardRecord.objects.select_for_update().filter(id=reward_id).first()
    if not reward:
        raise NotFoundException("Quyết định khen thưởng không tồn tại.")

    if reward.status != "pending_approval":
        raise ValidationException("Quyết định khen thưởng này đã được xử lý.")

    reward_date = reward.reward_date
    if reward_date:
        if isinstance(reward_date, str):
            reward_date = datetime.strptime(reward_date, "%Y-%m-%d").date()
        reward_period = reward_date.strftime("%Y-%m")
        from apps.hrm.selectors import is_salary_period_fully_paid

        if is_salary_period_fully_paid(reward_period):
            raise ValidationException(
                f"Kỳ lương {reward_period} đã được thanh toán 100%. Không cho phép duyệt khen thưởng trong kỳ này."
            )

    reward.status = "approved"
    reward.approved_by = user
    reward.approved_at = timezone.now()
    reward.save()

    create_system_log(
        user=user,
        action="approve",
        table_name="reward_record",
        record_id=str(reward.id),
        new_value={"status": reward.status, "approved_by_id": str(user.id)},
    )

    return reward


@transaction.atomic
def discipline_record_approve(*, user: User, discipline_id: str) -> DisciplineRecord:
    """
    Phê duyệt quyết định kỷ luật của nhân viên.

    Nếu discipline_type == 'termination' (Sa thải), hệ thống tự động:
      - Terminate EmploymentContract đang active (bao gồm quyết toán lương).
      - Set Employee.employment_status = 'inactive' và leave_date.
      - Disable User.is_active liên kết.
      - Lưu EmployeeDocument nếu có file_url.
    Tất cả thực hiện trong cùng transaction để đảm bảo toàn vẹn.
    """
    PermissionChecker.check_permission(user, "hrm.change_disciplinerecord")

    discipline = DisciplineRecord.objects.select_for_update().filter(id=discipline_id).first()
    if not discipline:
        raise NotFoundException("Quyết định kỷ luật không tồn tại.")

    if discipline.status != "pending_approval":
        raise ValidationException("Quyết định kỷ luật này đã được xử lý.")

    incident_date = discipline.incident_date
    discipline_date = discipline.discipline_date
    checked_periods = set()
    for dt in [incident_date, discipline_date]:
        if dt:
            if isinstance(dt, str):
                dt = datetime.strptime(dt, "%Y-%m-%d").date()
            checked_periods.add(dt.strftime("%Y-%m"))

    from apps.hrm.selectors import is_salary_period_fully_paid

    for period in checked_periods:
        if is_salary_period_fully_paid(period):
            raise ValidationException(
                f"Kỳ lương {period} đã được thanh toán 100%. Không cho phép duyệt kỷ luật trong kỳ này."
            )

    discipline.status = "approved"
    discipline.approved_by = user
    discipline.approved_at = timezone.now()
    discipline.save()

    create_system_log(
        user=user,
        action="approve",
        table_name="discipline_record",
        record_id=str(discipline.id),
        new_value={"status": discipline.status, "approved_by_id": str(user.id)},
    )

    if discipline.discipline_type == "termination":
        _handle_termination_side_effects(
            discipline=discipline,
            approver=user,
        )

    return discipline


def _handle_termination_side_effects(*, discipline: DisciplineRecord, approver: User) -> None:
    """
    Hàm nội bộ: xử lý hậu quả khi kỷ luật Sa thải được phê duyệt.
    Orchestrator: gọi các helper con theo đúng case.
    """
    employee = discipline.employee
    discipline_date = discipline.discipline_date
    had_active_contract = EmploymentContract.objects.filter(employee=employee, status="active").exists()

    # 1. Terminate HĐLĐ (nếu có)
    if had_active_contract:
        _terminate_active_contract(
            employee=employee,
            termination_date=discipline_date,
            reason=f"[Sa thải theo kỷ luật] {discipline.description}",
            file_url=discipline.file_url or None,
            terminator=approver,
        )
    else:
        # 2. Hoặc deactivate Employee (nếu không có HĐLĐ)
        _deactivate_employee(
            employee=employee,
            termination_date=discipline_date,
            terminator=approver,
        )

    # 3. Lưu EmployeeDocument (nếu không có HĐLĐ và có file_url)
    if not had_active_contract and discipline.file_url:
        _create_termination_document(
            employee=employee,
            file_url=discipline.file_url,
            terminator=approver,
        )

    # 4. Log tổng kết
    create_system_log(
        user=approver,
        action="terminated_by_discipline",
        table_name="discipline_record",
        record_id=str(discipline.id),
        new_value={
            "employee_id": str(employee.id),
            "termination_date": str(discipline_date),
            "had_active_contract": had_active_contract,
        },
    )


@transaction.atomic
def payroll_calculate_terminated_salary(
    *,
    salary_slip_id: str,
    termination_date: date,
    is_lawful: bool = True,
    unused_leave_days: Decimal = Decimal("0.00"),
    unnotified_days: int = 0,
    standard_working_days: int = 26,
    creator: Optional[User] = None,
) -> SalarySlip:
    """
    Tính lương quyết toán thôi việc.
    Bước 1: Gọi payroll_calculate_salary (4 thành phần định kỳ theo prorated).
    Bước 2: Cộng dồn 4 thành phần quyết toán (phép năm, BHXH, phạt nghỉ ngang).

    Yêu cầu: caller (contract_terminate) phải set slip.breakdown.is_partial=True
    với period_end=termination_date TRƯỚC khi gọi hàm này.
    """
    if creator:
        PermissionChecker.check_permission(creator, "finance.change_salaryslip")

    try:
        slip = SalarySlip.objects.select_for_update().get(id=salary_slip_id)
    except SalarySlip.DoesNotExist:
        raise ValidationException("Phiếu lương không tồn tại")

    if slip.status == "paid":
        raise ValidationException("Không thể tính lại phiếu lương đã thanh toán.")

    if not slip.breakdown or not slip.breakdown.get("is_partial"):
        raise ValidationException(
            "Phiếu lương quyết toán phải có breakdown.is_partial=True. "
            "Hãy set trước khi gọi payroll_calculate_terminated_salary."
        )

    # ===== BƯỚC 1: Lưu lại salary_segments từ lần calculate trước (nếu có) =====
    existing_salary_segments = None
    if slip.breakdown and slip.breakdown.get("salary_segments"):
        existing_salary_segments = slip.breakdown["salary_segments"]

    # ===== BƯỚC 2: Tính 4 thành phần định kỳ =====
    payroll_calculate_salary(salary_slip_id=str(slip.id), creator=creator)
    slip.refresh_from_db()

    # ===== BƯỚC 3: Đảm bảo salary_segments vẫn còn sau khi calculate =====
    # Nếu payroll_calculate_salary không ghi hoặc ghi rỗng salary_segments, dùng lại của lần trước
    has_segments = slip.breakdown and slip.breakdown.get("salary_segments")
    if existing_salary_segments and not has_segments:
        slip.breakdown = {
            **(slip.breakdown or {}),
            "salary_segments": existing_salary_segments,
        }

    # ===== BƯỚC 4: Tính 4 thành phần quyết toán =====
    employee = slip.employee
    salary_base = get_salary_at_date(employee, termination_date) or Decimal("0.00")

    # Tính tổng số ngày làm việc và ngày nghỉ được hưởng lương từ các phân đoạn lương
    total_work_days = Decimal("0.00")
    if slip.breakdown and "salary_segments" in slip.breakdown:
        for seg in slip.breakdown["salary_segments"]:
            total_work_days += Decimal(str(seg.get("work_days", 0)))

    working_days = total_work_days
    paid_leave_days = Decimal("0.00")

    comp = _calc_termination_compensation(
        salary_base=salary_base,
        working_days=working_days,
        paid_leave_days=paid_leave_days,
        is_lawful=is_lawful,
        unused_leave_days=unused_leave_days,
        unnotified_days=unnotified_days,
        standard_working_days=standard_working_days,
    )

    # Cộng dồn vào slip
    slip.gross_pay = (slip.gross_pay or Decimal("0.00")) + comp["unused_leave_compensation"]
    slip.deductions = (
        (slip.deductions or Decimal("0.00")) + comp["social_insurance_deduction"] + comp["resignation_fine"]
    )
    slip.net_pay = (slip.gross_pay or Decimal("0.00")) - (slip.deductions or Decimal("0.00"))

    # Cập nhật breakdown
    slip.breakdown = {
        **(slip.breakdown or {}),
        "termination_compensation": {
            "is_lawful": is_lawful,
            "unused_leave_days": float(unused_leave_days),
            "unused_leave_compensation": float(comp["unused_leave_compensation"]),
            "social_insurance_deduction": float(comp["social_insurance_deduction"]),
            "resignation_fine": float(comp["resignation_fine"]),
            "fine_half_month": float(comp["fine_half_month"]),
            "fine_unnotified": float(comp["fine_unnotified"]),
            "unnotified_days": unnotified_days,
            "termination_date": str(termination_date),
        },
    }

    # Ghi remarks (nếu chưa có) để Finance biết đây là quyết toán
    if not slip.remarks:
        remarks = (
            f"Quyết toán thôi việc ngày {termination_date} "
            f"({'Đúng luật' if is_lawful else 'Nghỉ ngang/Trái luật'}).\n"
            f"- Phép năm chưa nghỉ: {float(unused_leave_days):g} ngày "
            f"→ {comp['unused_leave_compensation']:,.2f}đ.\n"
            f"- BHXH (10.5%): {comp['social_insurance_deduction']:,.2f}đ "
            f"({'>=' if comp['social_insurance_deduction'] > 0 else '<'} 14 ngày làm việc)."
        )
        if not is_lawful and comp["resignation_fine"] > 0:
            remarks += (
                f"\n- Bồi thường nghỉ ngang: {comp['resignation_fine']:,.2f}đ "
                f"(0.5 tháng: {comp['fine_half_month']:,.2f}đ "
                f"+ {unnotified_days} ngày không báo trước: {comp['fine_unnotified']:,.2f}đ)."
            )
        slip.remarks = remarks

    slip.save()
    create_system_log(
        user=creator,
        action="update",
        table_name="salary_slip",
        record_id=str(slip.id),
        new_value={
            "log": "HRM calculated terminated salary",
            "is_lawful": is_lawful,
            "unused_leave_days": float(unused_leave_days),
        },
    )
    return slip


def _calc_termination_compensation(
    *,
    salary_base: Decimal,
    working_days: Decimal,
    paid_leave_days: Decimal,
    is_lawful: bool,
    unused_leave_days: Decimal,
    unnotified_days: int,
    standard_working_days: int = 26,
) -> Dict[str, Decimal]:
    """Tính 4 thành phần quyết toán thôi việc. Pure function (không query DB)."""
    # 1. Thanh toán phép năm chưa nghỉ (Điều 113-114 BLLĐ 2019)
    divisor = Decimal(str(standard_working_days))
    if divisor <= 0:
        divisor = DEFAULT_STANDARD_WORKING_DAYS

    unused_leave_compensation = ((salary_base / divisor) * Decimal(str(unused_leave_days))).quantize(Decimal("0.01"))

    # 2. BHXH 10.5% nếu làm >= 14 ngày trong tháng
    social_insurance_deduction = Decimal("0.00")
    if (working_days + paid_leave_days) >= SOCIAL_INSURANCE_MIN_DAYS:
        social_insurance_deduction = (salary_base * SOCIAL_INSURANCE_RATE).quantize(Decimal("0.01"))

    # 3. Bồi thường nghỉ ngang (chỉ áp dụng khi !is_lawful)
    resignation_fine = Decimal("0.00")
    fine_half_month = Decimal("0.00")
    fine_unnotified = Decimal("0.00")
    if not is_lawful:
        fine_half_month = (salary_base * RESIGNATION_FINE_HALF_MONTH).quantize(Decimal("0.01"))
        fine_unnotified = ((salary_base / divisor) * Decimal(str(unnotified_days))).quantize(Decimal("0.01"))
        resignation_fine = fine_half_month + fine_unnotified

    return {
        "unused_leave_compensation": unused_leave_compensation,
        "social_insurance_deduction": social_insurance_deduction,
        "resignation_fine": resignation_fine,
        "fine_half_month": fine_half_month,
        "fine_unnotified": fine_unnotified,
    }


@transaction.atomic
def create_partial_salary_slip(
    *,
    employee_id: str,
    period_start: date,
    period_end: date,
    name: str,
    creator: Optional[User] = None,
) -> SalarySlip:
    """
    Tạo phiếu lương nháp cho một giai đoạn (không phải cả tháng).
    """
    if creator:
        PermissionChecker.check_permission(creator, "finance.add_salaryslip")

    try:
        employee = Employee.objects.get(id=employee_id)
    except Employee.DoesNotExist:
        raise ValidationException("Nhân viên không tồn tại")

    if period_start >= period_end:
        raise ValidationException("period_end phải lớn hơn period_start")

    if period_start.year != period_end.year or period_start.month != period_end.month:
        raise ValidationException("period_start và period_end phải trong cùng một tháng")

    salary_period = period_start.strftime("%Y-%m")

    if SalarySlip.objects.filter(employee=employee, salary_period=salary_period).exists():
        raise ValidationException("Đã tồn tại phiếu lương cho nhân viên trong kỳ này")

    slip = SalarySlip.objects.create(
        employee=employee,
        salary_period=salary_period,
        name=name,
        base_salary=Decimal("0.00"),
        overtime_amount=Decimal("0.00"),
        allowance_amount=Decimal("0.00"),
        reward_amount_total=Decimal("0.00"),
        discipline_deduction_total=Decimal("0.00"),
        gross_pay=Decimal("0.00"),
        deductions=Decimal("0.00"),
        net_pay=Decimal("0.00"),
        status="draft",
        breakdown={
            "is_partial": True,
            "period_start": str(period_start),
            "period_end": str(period_end),
        },
    )

    create_system_log(
        user=creator,
        action="create",
        table_name="salary_slip",
        record_id=str(slip.id),
        new_value={
            "name": slip.name,
            "employee_id": str(slip.employee_id),
            "salary_period": salary_period,
            "status": "draft",
            "is_partial": True,
            "period_start": str(period_start),
            "period_end": str(period_end),
        },
    )

    return slip


@transaction.atomic
def payroll_submit_for_review(
    *,
    salary_slip_id: str,
    user: User,
    bypass_current_period_check: bool = False,
) -> SalarySlip:
    """
    HRM xác nhận phiếu lương đã tính xong và gửi cho Finance duyệt.
    """
    PermissionChecker.check_permission(user, "hrm.payroll_submit")

    try:
        slip = SalarySlip.objects.select_for_update().get(id=salary_slip_id)
    except SalarySlip.DoesNotExist:
        raise ValidationException("Phiếu lương không tồn tại")

    from apps.hrm.selectors import is_current_salary_period

    if not bypass_current_period_check and is_current_salary_period(slip.salary_period):
        raise ValidationException(
            f"Không thể gửi duyệt phiếu lương của kỳ {slip.salary_period} (tháng hiện tại). "
            f"Chỉ được phép thao tác với các kỳ từ tháng trước trở về trước."
        )

    if slip.status != "calculated":
        raise ValidationException("Chỉ được gửi duyệt phiếu lương ở trạng thái 'calculated'")

    slip.status = "pending_finance_review"
    slip.save(update_fields=["status"])

    create_system_log(
        user=user,
        action="update",
        table_name="salary_slip",
        record_id=str(slip.id),
        old_value={"status": "calculated"},
        new_value={"status": "pending_finance_review", "log": "HRM submitted for Finance review"},
    )

    return slip


@transaction.atomic
def payroll_bulk_calculate(
    *,
    salary_period: str,
    creator: Optional[User] = None,
) -> dict:
    """
    Tính toán hàng loạt phiếu lương nháp (draft) hoặc đã tính toán (calculated) trong một kỳ lương.
    """
    if creator:
        PermissionChecker.check_permission(creator, "finance.change_salaryslip")

    from apps.finance.models import SalarySlip

    slips = list(
        SalarySlip.objects.select_for_update().filter(salary_period=salary_period, status__in=["draft", "calculated"])
    )

    if not slips:
        return {"count": 0, "slip_ids": []}

    year, month = map(int, salary_period.split("-"))
    holidays_cache = get_holiday_dates_for_period(year, month)

    calculated_ids = []
    for slip in slips:
        payroll_calculate_salary(
            salary_slip_id=str(slip.id),
            creator=creator,
            holidays_cache=holidays_cache,
        )
        calculated_ids.append(str(slip.id))

    return {"count": len(calculated_ids), "slip_ids": calculated_ids}


@transaction.atomic
def payroll_bulk_submit_for_review(
    *,
    salary_period: str,
    user: User,
) -> dict:
    """
    HRM xác nhận hàng loạt phiếu lương đã tính xong và gửi cho Finance duyệt.
    """
    PermissionChecker.check_permission(user, "hrm.payroll_submit")

    from apps.hrm.selectors import is_current_salary_period

    if is_current_salary_period(salary_period):
        raise ValidationException(
            f"Không thể gửi duyệt hàng loạt phiếu lương kỳ {salary_period} (tháng hiện tại). "
            f"Chỉ được phép thao tác với các kỳ từ tháng trước trở về trước."
        )

    from apps.accounts.models import SystemLog
    from apps.finance.models import SalarySlip

    slips = list(SalarySlip.objects.select_for_update().filter(salary_period=salary_period, status="calculated"))

    if not slips:
        raise ValidationException("Không có phiếu lương nào ở trạng thái 'calculated' để gửi duyệt.")

    for slip in slips:
        slip.status = "pending_finance_review"

    SalarySlip.objects.bulk_update(slips, ["status"])

    logs = [
        SystemLog(
            user=user,
            action="update",
            table_name="salary_slip",
            record_id=str(slip.id),
            old_value={"status": "calculated"},
            new_value={"status": "pending_finance_review", "log": "HRM bulk submitted for Finance review"},
        )
        for slip in slips
    ]
    SystemLog.objects.bulk_create(logs)

    slip_ids = [str(slip.id) for slip in slips]
    return {"count": len(slip_ids), "slip_ids": slip_ids}


@transaction.atomic
def reward_record_update(
    *,
    reward_id: str,
    data: Dict[str, Any],
    updater: User,
) -> RewardRecord:
    """
    Cập nhật quyết định khen thưởng của nhân viên.
    """
    PermissionChecker.check_permission(updater, "hrm.change_rewardrecord")

    reward = RewardRecord.objects.select_for_update().filter(id=reward_id).first()
    if not reward:
        raise NotFoundException("Quyết định khen thưởng không tồn tại.")

    if reward.status != "pending_approval":
        raise ValidationException("Chỉ có thể sửa khen thưởng ở trạng thái chờ duyệt.")

    # Check existing period paid
    reward_period = reward.reward_date.strftime("%Y-%m")
    from apps.hrm.selectors import is_salary_period_fully_paid

    if is_salary_period_fully_paid(reward_period):
        raise ValidationException(
            f"Kỳ lương {reward_period} đã được thanh toán 100%. Không cho phép sửa khen thưởng này."
        )

    # Check new period paid if reward_date changes
    reward_date = data.get("reward_date")
    if reward_date:
        if isinstance(reward_date, str):
            reward_date = datetime.strptime(reward_date, "%Y-%m-%d").date()
        new_period = reward_date.strftime("%Y-%m")
        if new_period != reward_period and is_salary_period_fully_paid(new_period):
            raise ValidationException(
                f"Kỳ lương mới {new_period} đã được thanh toán 100%. Không cho phép chuyển khen thưởng vào kỳ này."
            )

    amount = data.get("amount")
    if amount is not None:
        amount = Decimal(str(amount))

    salary_slip_id = data.get("salary_slip_id")
    if salary_slip_id:
        from apps.finance.models import SalarySlip

        try:
            slip = SalarySlip.objects.get(id=salary_slip_id)
        except SalarySlip.DoesNotExist:
            raise ValidationException("Phiếu lương không tồn tại")
        if str(slip.employee.id) != str(reward.employee.id):
            raise ValidationException("Phiếu lương không thuộc về nhân viên này")
        if slip.status == "paid":
            raise ValidationException("Không thể gán khen thưởng cho phiếu lương đã chi trả")

    old_value = {
        "reward_date": str(reward.reward_date),
        "reward_type": reward.reward_type,
        "amount": str(reward.amount) if reward.amount is not None else None,
        "description": reward.description,
        "salary_slip_id": str(reward.salary_slip_id) if reward.salary_slip_id else None,
    }

    if "reward_date" in data:
        reward.reward_date = reward_date or reward.reward_date
    if "reward_type" in data:
        reward.reward_type = data["reward_type"]
    if "amount" in data:
        reward.amount = amount
    if "description" in data:
        reward.description = data["description"]
    if "salary_slip_id" in data:
        reward.salary_slip_id = salary_slip_id

    reward.save()

    create_system_log(
        user=updater,
        action="update",
        table_name="reward_record",
        record_id=str(reward.id),
        old_value=old_value,
        new_value={
            "reward_date": str(reward.reward_date),
            "reward_type": reward.reward_type,
            "amount": str(reward.amount) if reward.amount is not None else None,
            "description": reward.description,
            "salary_slip_id": str(reward.salary_slip_id) if reward.salary_slip_id else None,
        },
    )

    return reward


@transaction.atomic
def reward_record_cancel(
    *,
    reward_id: str,
    user: User,
    reason: Optional[str] = None,
) -> RewardRecord:
    """
    Hủy quyết định khen thưởng của nhân viên.
    """
    PermissionChecker.check_permission(user, "hrm.change_rewardrecord")

    reward = RewardRecord.objects.select_for_update().filter(id=reward_id).first()
    if not reward:
        raise NotFoundException("Quyết định khen thưởng không tồn tại.")

    if reward.status != "pending_approval":
        raise ValidationException("Chỉ có thể hủy khen thưởng ở trạng thái chờ duyệt.")

    reward_period = reward.reward_date.strftime("%Y-%m")
    from apps.hrm.selectors import is_salary_period_fully_paid

    if is_salary_period_fully_paid(reward_period):
        raise ValidationException(f"Kỳ lương {reward_period} đã được thanh toán 100%. Không cho phép hủy khen thưởng.")

    old_status = reward.status
    reward.status = "cancelled"
    reward.cancelled_by = user
    reward.cancelled_at = timezone.now()
    reward.save()

    create_system_log(
        user=user,
        action="cancel",
        table_name="reward_record",
        record_id=str(reward.id),
        old_value={"status": old_status},
        new_value={
            "status": "cancelled",
            "cancelled_by_id": str(user.id),
            "reason": reason,
        },
    )

    return reward


@transaction.atomic
def reward_record_delete(
    *,
    reward_id: str,
    deleter: User,
) -> None:
    """
    Xóa quyết định khen thưởng của nhân viên.
    """
    PermissionChecker.check_permission(deleter, "hrm.delete_rewardrecord")

    reward = RewardRecord.objects.select_for_update().filter(id=reward_id).first()
    if not reward:
        raise NotFoundException("Quyết định khen thưởng không tồn tại.")

    if reward.status != "pending_approval":
        raise ValidationException("Chỉ có thể xóa khen thưởng ở trạng thái chờ duyệt.")

    reward_period = reward.reward_date.strftime("%Y-%m")
    from apps.hrm.selectors import is_salary_period_fully_paid

    if is_salary_period_fully_paid(reward_period):
        raise ValidationException(f"Kỳ lương {reward_period} đã được thanh toán 100%. Không cho phép xóa khen thưởng.")

    old_value = {
        "reward_date": str(reward.reward_date),
        "reward_type": reward.reward_type,
        "amount": str(reward.amount) if reward.amount is not None else None,
        "description": reward.description,
        "salary_slip_id": str(reward.salary_slip_id) if reward.salary_slip_id else None,
        "status": reward.status,
    }
    record_id = str(reward.id)
    reward.delete()

    create_system_log(
        user=deleter,
        action="delete",
        table_name="reward_record",
        record_id=record_id,
        old_value=old_value,
        new_value={},
    )


@transaction.atomic
def discipline_record_update(
    *,
    discipline_id: str,
    data: Dict[str, Any],
    updater: User,
) -> DisciplineRecord:
    """
    Cập nhật quyết định kỷ luật của nhân viên.
    """
    PermissionChecker.check_permission(updater, "hrm.change_disciplinerecord")

    discipline = DisciplineRecord.objects.select_for_update().filter(id=discipline_id).first()
    if not discipline:
        raise NotFoundException("Quyết định kỷ luật không tồn tại.")

    if discipline.status != "pending_approval":
        raise ValidationException("Chỉ có thể sửa kỷ luật ở trạng thái chờ duyệt.")

    incident_date = data.get("incident_date")
    if incident_date and isinstance(incident_date, str):
        incident_date = datetime.strptime(incident_date, "%Y-%m-%d").date()
    discipline_date = data.get("discipline_date")
    if discipline_date and isinstance(discipline_date, str):
        discipline_date = datetime.strptime(discipline_date, "%Y-%m-%d").date()

    # Check periods paid
    checked_periods = set()
    for dt in [discipline.incident_date, discipline.discipline_date, incident_date, discipline_date]:
        if dt:
            checked_periods.add(dt.strftime("%Y-%m"))

    from apps.hrm.selectors import is_salary_period_fully_paid

    for period in checked_periods:
        if is_salary_period_fully_paid(period):
            raise ValidationException(
                f"Kỳ lương {period} đã được thanh toán 100%. Không cho phép sửa kỷ luật trong kỳ này."
            )

    penalty_amount = data.get("penalty_amount")
    if penalty_amount is not None:
        penalty_amount = Decimal(str(penalty_amount))

    salary_slip_id = data.get("salary_slip_id")
    if salary_slip_id:
        from apps.finance.models import SalarySlip

        try:
            slip = SalarySlip.objects.get(id=salary_slip_id)
        except SalarySlip.DoesNotExist:
            raise ValidationException("Phiếu lương không tồn tại")
        if str(slip.employee.id) != str(discipline.employee.id):
            raise ValidationException("Phiếu lương không thuộc về nhân viên này")
        if slip.status == "paid":
            raise ValidationException("Không thể gán kỷ luật cho phiếu lương đã chi trả")

    old_value = {
        "incident_date": str(discipline.incident_date),
        "discipline_date": str(discipline.discipline_date),
        "discipline_type": discipline.discipline_type,
        "penalty_amount": str(discipline.penalty_amount) if discipline.penalty_amount is not None else None,
        "description": discipline.description,
        "file_url": discipline.file_url,
        "salary_slip_id": str(discipline.salary_slip_id) if discipline.salary_slip_id else None,
    }

    if "incident_date" in data:
        discipline.incident_date = incident_date or discipline.incident_date
    if "discipline_date" in data:
        discipline.discipline_date = discipline_date or discipline.discipline_date
    if "discipline_type" in data:
        discipline.discipline_type = data["discipline_type"]
    if "penalty_amount" in data:
        discipline.penalty_amount = penalty_amount
    if "description" in data:
        discipline.description = data["description"]
    if "file_url" in data:
        discipline.file_url = data["file_url"]
    if "salary_slip_id" in data:
        discipline.salary_slip_id = salary_slip_id

    discipline.save()

    create_system_log(
        user=updater,
        action="update",
        table_name="discipline_record",
        record_id=str(discipline.id),
        old_value=old_value,
        new_value={
            "incident_date": str(discipline.incident_date),
            "discipline_date": str(discipline.discipline_date),
            "discipline_type": discipline.discipline_type,
            "penalty_amount": str(discipline.penalty_amount) if discipline.penalty_amount is not None else None,
            "description": discipline.description,
            "file_url": discipline.file_url,
            "salary_slip_id": str(discipline.salary_slip_id) if discipline.salary_slip_id else None,
        },
    )

    return discipline


@transaction.atomic
def discipline_record_cancel(
    *,
    discipline_id: str,
    user: User,
    reason: Optional[str] = None,
) -> DisciplineRecord:
    """
    Hủy quyết định kỷ luật của nhân viên.
    """
    PermissionChecker.check_permission(user, "hrm.change_disciplinerecord")

    discipline = DisciplineRecord.objects.select_for_update().filter(id=discipline_id).first()
    if not discipline:
        raise NotFoundException("Quyết định kỷ luật không tồn tại.")

    if discipline.status != "pending_approval":
        raise ValidationException("Chỉ có thể hủy kỷ luật ở trạng thái chờ duyệt.")

    checked_periods = set()
    for dt in [discipline.incident_date, discipline.discipline_date]:
        if dt:
            checked_periods.add(dt.strftime("%Y-%m"))

    from apps.hrm.selectors import is_salary_period_fully_paid

    for period in checked_periods:
        if is_salary_period_fully_paid(period):
            raise ValidationException(f"Kỳ lương {period} đã được thanh toán 100%. Không cho phép hủy kỷ luật.")

    old_status = discipline.status
    discipline.status = "cancelled"
    discipline.cancelled_by = user
    discipline.cancelled_at = timezone.now()
    discipline.save()

    create_system_log(
        user=user,
        action="cancel",
        table_name="discipline_record",
        record_id=str(discipline.id),
        old_value={"status": old_status},
        new_value={
            "status": "cancelled",
            "cancelled_by_id": str(user.id),
            "reason": reason,
        },
    )

    return discipline


@transaction.atomic
def discipline_record_delete(
    *,
    discipline_id: str,
    deleter: User,
) -> None:
    """
    Xóa quyết định kỷ luật của nhân viên.
    """
    PermissionChecker.check_permission(deleter, "hrm.delete_disciplinerecord")

    discipline = DisciplineRecord.objects.select_for_update().filter(id=discipline_id).first()
    if not discipline:
        raise NotFoundException("Quyết định kỷ luật không tồn tại.")

    if discipline.status != "pending_approval":
        raise ValidationException("Chỉ có thể xóa kỷ luật ở trạng thái chờ duyệt.")

    checked_periods = set()
    for dt in [discipline.incident_date, discipline.discipline_date]:
        if dt:
            checked_periods.add(dt.strftime("%Y-%m"))

    from apps.hrm.selectors import is_salary_period_fully_paid

    for period in checked_periods:
        if is_salary_period_fully_paid(period):
            raise ValidationException(f"Kỳ lương {period} đã được thanh toán 100%. Không cho phép xóa kỷ luật.")

    old_value = {
        "incident_date": str(discipline.incident_date),
        "discipline_date": str(discipline.discipline_date),
        "discipline_type": discipline.discipline_type,
        "penalty_amount": str(discipline.penalty_amount) if discipline.penalty_amount is not None else None,
        "description": discipline.description,
        "file_url": discipline.file_url,
        "salary_slip_id": str(discipline.salary_slip_id) if discipline.salary_slip_id else None,
        "status": discipline.status,
    }
    record_id = str(discipline.id)
    discipline.delete()

    create_system_log(
        user=deleter,
        action="delete",
        table_name="discipline_record",
        record_id=record_id,
        old_value=old_value,
        new_value={},
    )
