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
    EmploymentHistory,
    LeaveRequest,
    PublicHoliday,
    RewardRecord,
)
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
    if creator:
        PermissionChecker.check_permission(creator, "hrm.add_employee")

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
    if updater:
        PermissionChecker.check_permission(updater, "hrm.change_employee")

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
    salary_base = employee.salary_base or Decimal("0.00")

    # 1. Kiểm tra nợ kỳ lương trước đó
    current_period = termination_date.strftime("%Y-%m")
    unpaid_slips = SalarySlip.objects.filter(employee=employee, salary_period__lt=current_period).exclude(status="paid")

    if unpaid_slips.exists():
        periods = [slip.salary_period for slip in unpaid_slips]
        raise ValidationException(
            f"Không thể chấm dứt hợp đồng do nhân viên vẫn còn nợ lương kỳ trước chưa thanh toán ({', '.join(periods)}). Vui lòng thanh toán trước."
        )

    # 2. Quyết toán kỳ lương hiện tại
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
            "union_fee_2pct": Decimal("0.00"),
            "gross_pay": Decimal("0.00"),
            "deductions": Decimal("0.00"),
            "net_pay": Decimal("0.00"),
            "status": "draft",
        },
    )

    # 2.1. Tính ngày công thực tế làm việc/hưởng lương trong tháng nghỉ từ ngày 1 đến termination_date
    year = termination_date.year
    month = termination_date.month
    attendances = Attendance.objects.filter(
        employee=employee, date__year=year, date__month=month, date__lte=termination_date
    )

    from django.conf import settings

    weekly_rest_days = getattr(settings, "HRM_WEEKLY_REST_DAYS", [6])
    compensatory_ot_rate = Decimal(str(getattr(settings, "HRM_COMPENSATORY_OVERTIME_RATE", 2.0)))

    # Fetch public holidays and compensatory holidays for the period up to termination_date
    official_holiday_dates, compensatory_holiday_dates = get_holiday_dates_for_period(
        year, month, end_limit_date=termination_date
    )
    all_holiday_dates = official_holiday_dates | compensatory_holiday_dates

    working_days = Decimal("0.00")
    paid_leave_days = Decimal("0.00")
    ot_normal_hours = Decimal("0.00")
    ot_weekend_hours = Decimal("0.00")
    ot_holiday_hours = Decimal("0.00")
    ot_compensatory_hours = Decimal("0.00")

    recorded_dates = set()
    for att in attendances:
        recorded_dates.add(att.date)
        if att.status == "working" and (att.work_hours or 0) > 0:
            working_days += Decimal("1.00")
        elif att.status in ["paid_leave", "holiday"]:
            paid_leave_days += Decimal("1.00")

        ot_h = att.overtime_hours or Decimal("0.00")
        if ot_h > 0:
            if att.date in official_holiday_dates:
                ot_holiday_hours += ot_h
            elif att.date in compensatory_holiday_dates:
                ot_compensatory_hours += ot_h
            elif att.date.weekday() in weekly_rest_days:
                ot_weekend_hours += ot_h
            else:
                ot_normal_hours += ot_h

    # Tự động tính 100% lương cho ngày nghỉ lễ/nghỉ bù nếu chưa có chấm công
    credited_holiday_dates = set()
    for h_date in all_holiday_dates:
        if h_date not in recorded_dates and h_date not in credited_holiday_dates:
            credited_holiday_dates.add(h_date)
            paid_leave_days += Decimal("1.00")

    # 2.2. Xác định ngày công chia lương (divisor) - Cố định Cách 1
    divisor = Decimal(str(standard_working_days))
    if divisor <= 0:
        divisor = Decimal("26.00")

    # 2.3. Lương thực tế làm việc
    base_salary_earned = (salary_base * ((working_days + paid_leave_days) / divisor)).quantize(Decimal("0.01"))

    # 2.4. Tiền phép năm chưa nghỉ
    unused_leave_compensation = (salary_base / divisor * Decimal(str(unused_leave_days))).quantize(Decimal("0.01"))

    # 2.5. Bảo hiểm xã hội tháng nghỉ việc (đóng nếu số ngày làm việc và hưởng lương >= 14 ngày)
    social_insurance_deduction = Decimal("0.00")
    if (working_days + paid_leave_days) >= 14:
        social_insurance_deduction = (salary_base * Decimal("0.105")).quantize(Decimal("0.01"))

    # 2.6. Phạt bồi thường nếu nghỉ việc trái pháp luật (nghỉ ngang)
    resignation_fine = Decimal("0.00")
    fine_half_month = Decimal("0.00")
    fine_unnotified = Decimal("0.00")
    if not is_lawful:
        fine_half_month = (salary_base * Decimal("0.5")).quantize(Decimal("0.01"))
        fine_unnotified = (salary_base / divisor * Decimal(str(unnotified_days))).quantize(Decimal("0.01"))
        resignation_fine = fine_half_month + fine_unnotified

    # 2.7. Tính toán OT, Kinh phí công đoàn, Thưởng & Kỷ luật phạt thông thường
    hourly_rate = salary_base / divisor / Decimal("8.00")
    ot_normal_rate = hourly_rate * Decimal("1.5")
    ot_weekend_rate = hourly_rate * Decimal("2.0")
    ot_holiday_rate = hourly_rate * Decimal("3.0")
    ot_compensatory_rate = hourly_rate * compensatory_ot_rate

    ot_normal_amount = ot_normal_hours * ot_normal_rate
    ot_weekend_amount = ot_weekend_hours * ot_weekend_rate
    ot_holiday_amount = ot_holiday_hours * ot_holiday_rate
    ot_compensatory_amount = ot_compensatory_hours * ot_compensatory_rate

    overtime_amount_earned = ot_normal_amount + ot_weekend_amount + ot_holiday_amount + ot_compensatory_amount
    overtime_amount_earned = overtime_amount_earned.quantize(Decimal("0.01"))

    union_fee = Decimal("0.00")
    if employee.is_union_member:
        union_fee = (salary_base * Decimal("0.02")).quantize(Decimal("0.01"))

    import calendar

    from django.db.models import Q

    last_day = calendar.monthrange(year, month)[1]
    period_end_date = date(year, month, last_day)

    rewards = RewardRecord.objects.filter(employee=employee, reward_date__lte=period_end_date).filter(
        Q(salary_slip__isnull=True) | Q(salary_slip=slip)
    )
    reward_total = Decimal("0.00")
    for r in rewards:
        reward_total += r.amount or Decimal("0.00")
        if r.salary_slip != slip:
            r.salary_slip = slip
            r.save(update_fields=["salary_slip"])

    disciplines = DisciplineRecord.objects.filter(employee=employee, discipline_date__lte=period_end_date).filter(
        Q(salary_slip__isnull=True) | Q(salary_slip=slip)
    )
    discipline_total = Decimal("0.00")
    for d in disciplines:
        discipline_total += d.penalty_amount or Decimal("0.00")
        if d.salary_slip != slip:
            d.salary_slip = slip
            d.save(update_fields=["salary_slip"])

    allowance_amount = Decimal("0.00")

    # 2.8. Tổng quyết toán
    gross_pay = base_salary_earned + overtime_amount_earned + allowance_amount + unused_leave_compensation
    deductions = union_fee + discipline_total + social_insurance_deduction + resignation_fine
    net_pay = gross_pay + reward_total - deductions

    remarks = (
        f"Quyết toán thôi việc ngày {termination_date} ({'Đúng luật' if is_lawful else 'Nghỉ ngang/Trái luật'}).\n"
        f"- Ngày công thực tế/hưởng lương: {working_days + paid_leave_days} ngày.\n"
        f"- Lương ngày công: {base_salary_earned:,.2f}đ (Tính theo ngày công chuẩn cố định với công chuẩn {divisor}).\n"
        f"- Phép năm chưa nghỉ ({unused_leave_days} ngày): {unused_leave_compensation:,.2f}đ.\n"
        f"- Khấu trừ BHXH (10.5%): {social_insurance_deduction:,.2f}đ ({'Có trích đóng' if social_insurance_deduction > 0 else 'Không đóng do làm < 14 ngày'}).\n"
    )
    if not is_lawful:
        remarks += (
            f"- Bồi thường nghỉ ngang: {resignation_fine:,.2f}đ (Gồm 0.5 tháng lương: {fine_half_month:,.2f}đ "
            f"và {unnotified_days} ngày không báo trước: {fine_unnotified:,.2f}đ).\n"
        )

    slip.base_salary = base_salary_earned
    slip.overtime_amount = overtime_amount_earned
    slip.allowance_amount = allowance_amount
    slip.reward_amount_total = reward_total
    slip.discipline_deduction_total = discipline_total
    slip.union_fee_2pct = union_fee
    slip.gross_pay = gross_pay
    slip.deductions = deductions
    slip.net_pay = net_pay
    slip.remarks = remarks.strip()
    slip.status = "paid"

    total_days_str = f"{float(working_days + paid_leave_days):g}"
    unused_leave_str = f"{float(unused_leave_days):g}"

    incomes = [
        {
            "name": f"Lương theo ngày công thực tế ({total_days_str}/{standard_working_days} ngày)",
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
            {
                "name": f"Bồi thường phép năm chưa nghỉ ({unused_leave_str} ngày)",
                "amount": float(unused_leave_compensation),
            },
            {"name": "Khen thưởng/Thưởng thêm", "amount": float(reward_total)},
        ]
    )

    slip.breakdown = {
        "standard_working_days": int(standard_working_days),
        "incomes": incomes,
        "deductions": [
            {"name": "Phạt kỷ luật/Khấu trừ", "amount": float(discipline_total)},
            {"name": "Phí công đoàn (2%)", "amount": float(union_fee)},
            {"name": "Khấu trừ BHXH (10.5% lương)", "amount": float(social_insurance_deduction)},
        ],
    }
    if not is_lawful and resignation_fine > 0:
        slip.breakdown["deductions"].append(
            {
                "name": f"Bồi thường nghỉ ngang (0.5 tháng + {unnotified_days} ngày không báo trước)",
                "amount": float(resignation_fine),
            }
        )

    slip.save()

    # 2.9. Tự động sinh ra bút toán chi/thu tiền tại finance dựa trên net_pay
    from apps.finance.models import CashFlowTransaction

    net_pay = slip.net_pay
    tx = None
    tx_created = False

    if net_pay > Decimal("0.00"):
        tx_name = f"PAY-FINAL-SALARY-{employee.employee_id}-{current_period}"
        tx, tx_created = CashFlowTransaction.objects.get_or_create(
            name=tx_name,
            defaults={
                "payment_type": "pay",
                "category": "Chi trả lương nhân viên thôi việc",
                "payment_method": "bank_transfer",
                "amount": net_pay,
                "payment_date": date.today(),
                "remarks": f"Quyết toán thôi việc và chi trả lương cuối cùng cho nhân viên {employee.full_name} ({employee.employee_id}) ngày nghỉ việc {termination_date}. Số tiền: {net_pay:,.2f}đ.",
            },
        )
    elif net_pay < Decimal("0.00"):
        tx_name = f"COLLECT-FINAL-SALARY-{employee.employee_id}-{current_period}"
        tx, tx_created = CashFlowTransaction.objects.get_or_create(
            name=tx_name,
            defaults={
                "payment_type": "receive",
                "category": "Thu hồi bồi thường nhân viên thôi việc",
                "payment_method": "bank_transfer",
                "amount": abs(net_pay),
                "payment_date": date.today(),
                "remarks": f"Quyết toán thôi việc và thu hồi bồi thường từ nhân viên {employee.full_name} ({employee.employee_id}) ngày nghỉ việc {termination_date}. Số tiền: {abs(net_pay):,.2f}đ.",
            },
        )

    if tx and tx_created and terminator:
        create_system_log(
            user=terminator,
            action="create",
            table_name="cash_flow_transaction",
            record_id=str(tx.id),
            new_value={
                "name": tx.name,
                "payment_type": tx.payment_type,
                "category": tx.category,
                "amount": str(tx.amount),
                "payment_date": str(tx.payment_date),
            },
        )

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

    # 5. Vô hiệu hóa tài khoản User liên kết qua employee_id
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
def employee_update_salary_or_title(
    *,
    employee_id: str,
    change_data: Dict[str, Any],
    approved_by_user_id: str,
    approved_by: Optional[User] = None,
) -> Employee:
    """
    Cập nhật lương cơ bản, chức danh hoặc phòng ban của nhân viên và tự động ghi nhận vào EmploymentHistory.
    """
    try:
        employee = Employee.objects.get(id=employee_id)
    except Employee.DoesNotExist:
        raise ValidationException("Nhân viên không tồn tại")

    if not approved_by:
        try:
            approved_by = User.objects.get(id=approved_by_user_id)
        except User.DoesNotExist:
            raise ValidationException("Người phê duyệt không tồn tại")

    PermissionChecker.check_permission(approved_by, "hrm.change_employee")

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
                    base_salary=employee.salary_base or Decimal("0.00"),
                    overtime_amount=Decimal("0.00"),
                    allowance_amount=Decimal("0.00"),
                    reward_amount_total=Decimal("0.00"),
                    discipline_deduction_total=Decimal("0.00"),
                    union_fee_2pct=Decimal("0.00"),
                    gross_pay=Decimal("0.00"),
                    deductions=Decimal("0.00"),
                    net_pay=Decimal("0.00"),
                    status="draft",
                )
            )

    if new_slips:
        # bulk create slips
        created_slips = SalarySlip.objects.bulk_create(new_slips, ignore_conflicts=True)

        # bulk create logs
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

    return list(SalarySlip.objects.filter(salary_period=salary_period).select_related("employee"))


@transaction.atomic
def payroll_calculate_salary(
    *,
    salary_slip_id: str,
    creator: Optional[User] = None,
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

    employee = slip.employee
    salary_base = employee.salary_base or Decimal("0.00")

    # 1. Tính toán ngày công từ Attendance trong kỳ
    year, month = map(int, slip.salary_period.split("-"))
    import calendar

    last_day = calendar.monthrange(year, month)[1]
    period_end_date = date(year, month, last_day)

    attendances = Attendance.objects.filter(employee=employee, date__year=year, date__month=month)

    # Fetch public holidays and compensatory holidays for this period
    official_holiday_dates, compensatory_holiday_dates = get_holiday_dates_for_period(year, month)
    all_holiday_dates = official_holiday_dates | compensatory_holiday_dates

    working_days = Decimal("0.00")
    paid_leave_days = Decimal("0.00")
    ot_normal_hours = Decimal("0.00")
    ot_weekend_hours = Decimal("0.00")
    ot_holiday_hours = Decimal("0.00")
    ot_compensatory_hours = Decimal("0.00")

    recorded_dates = set()
    for att in attendances:
        recorded_dates.add(att.date)
        if att.status == "working" and (att.work_hours or 0) > 0:
            working_days += Decimal("1.00")
        elif att.status in ["paid_leave", "holiday"]:
            paid_leave_days += Decimal("1.00")

        ot_h = att.overtime_hours or Decimal("0.00")
        if ot_h > 0:
            if att.date in official_holiday_dates:
                ot_holiday_hours += ot_h
            elif att.date in compensatory_holiday_dates:
                ot_compensatory_hours += ot_h
            elif att.date.weekday() in weekly_rest_days:
                ot_weekend_hours += ot_h
            else:
                ot_normal_hours += ot_h

    # Tự động tính 100% lương cho ngày nghỉ lễ/nghỉ bù nếu chưa có chấm công
    credited_holiday_dates = set()
    for h_date in all_holiday_dates:
        if h_date not in recorded_dates and h_date not in credited_holiday_dates:
            credited_holiday_dates.add(h_date)
            paid_leave_days += Decimal("1.00")

    if standard_days > 0:
        base_salary_earned = salary_base * ((working_days + paid_leave_days) / Decimal(str(standard_days)))
    else:
        base_salary_earned = Decimal("0.00")
    base_salary_earned = base_salary_earned.quantize(Decimal("0.01"))

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

    union_fee = Decimal("0.00")
    if employee.is_union_member:
        union_fee = (salary_base * Decimal("0.02")).quantize(Decimal("0.01"))

    from django.db.models import Q

    # Định nghĩa ngày bắt đầu của kỳ lương
    period_start_date = date(year, month, 1)

    # 2. Thưởng & Phạt trong kỳ (không gom bù)
    rewards = RewardRecord.objects.filter(
        employee=employee,
        reward_date__gte=period_start_date,
        reward_date__lte=period_end_date,
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
    deductions = union_fee + discipline_total
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
        "union_fee_2pct": str(slip.union_fee_2pct),
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
    slip.union_fee_2pct = union_fee
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
            {"name": "Phí công đoàn (2%)", "amount": float(union_fee)},
        ],
    }
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
            "union_fee_2pct": str(slip.union_fee_2pct),
            "gross_pay": str(slip.gross_pay),
            "deductions": str(slip.deductions),
            "net_pay": str(slip.net_pay),
            "remarks": slip.remarks,
        },
    )

    return slip


@transaction.atomic
def payroll_approve_salary(
    *,
    user: User,
    salary_slip_id: str,
) -> SalarySlip:
    """
    Phê duyệt phiếu lương sau khi đã tính toán (calculated).
    Yêu cầu quyền hrm.payroll_approve.
    """
    PermissionChecker.check_permission(user, "hrm.payroll_approve")

    slip = SalarySlip.objects.select_for_update().filter(id=salary_slip_id).first()
    if not slip:
        raise NotFoundException(f"Phiếu lương với ID {salary_slip_id} không tồn tại")

    if slip.status != "calculated":
        raise ValidationException("Chỉ có thể phê duyệt phiếu lương ở trạng thái 'Calculated'")

    slip.status = "approved"
    slip.approved_by = user
    slip.approved_at = timezone.now()
    slip.save()

    create_system_log(
        user=user,
        action="update",
        table_name="salary_slip",
        record_id=str(slip.id),
        old_value={"status": "calculated"},
        new_value={
            "status": "approved",
            "approved_by_id": str(user.id),
            "approved_at": str(slip.approved_at),
        },
    )

    return slip


@transaction.atomic
def payroll_bulk_confirm_and_pay(
    *,
    salary_period: str,
    payment_method: str,
    creator: Optional[User] = None,
) -> list[SalarySlip]:
    """
    Xác nhận chi trả lương nhanh cho toàn bộ phiếu lương chưa thanh toán của kỳ lương được chọn.
    Tối ưu hóa bulk operations để giảm số truy cập DB từ O(N) xuống O(1).
    """
    if creator:
        PermissionChecker.check_permission(creator, "finance.change_salaryslip")

    # 1. Lấy danh sách các slip chưa paid trong kỳ kèm employee để tránh N+1
    slips = list(SalarySlip.objects.filter(salary_period=salary_period, status="approved").select_related("employee"))
    if not slips:
        return []

    from apps.accounts.models import SystemLog
    from apps.finance.models import CashFlowTransaction

    # 2. Lấy danh sách các giao dịch CashFlowTransaction đã tồn tại cho các nhân viên này trong kỳ
    tx_names = [f"PAY-SALARY-{slip.employee.employee_id}-{salary_period}" for slip in slips]
    existing_tx_names = set(CashFlowTransaction.objects.filter(name__in=tx_names).values_list("name", flat=True))

    slips_to_update = []
    txs_to_create = []
    logs_to_create = []

    for slip in slips:
        old_status = slip.status
        old_method = slip.payment_method

        # Cập nhật thông tin trên bộ nhớ
        slip.status = "paid"
        slip.payment_method = payment_method
        slips_to_update.append(slip)

        # Tạo log thay đổi trạng thái và payment_method của SalarySlip
        logs_to_create.append(
            SystemLog(
                user=creator,
                action="update",
                table_name="salary_slip",
                record_id=str(slip.id),
                old_value={"status": old_status, "payment_method": old_method},
                new_value={"status": "paid", "payment_method": payment_method},
            )
        )

        # Chuẩn bị giao dịch CashFlowTransaction nếu chưa tồn tại
        tx_name = f"PAY-SALARY-{slip.employee.employee_id}-{salary_period}"
        if tx_name not in existing_tx_names:
            try:
                parts = salary_period.split("-")
                period_year = parts[0]
                period_month = parts[1]
            except Exception:
                period_year = ""
                period_month = salary_period

            if slip.net_pay > 0:
                txs_to_create.append(
                    CashFlowTransaction(
                        name=tx_name,
                        payment_type="pay",
                        category="Chi trả lương nhân viên",
                        payment_method=payment_method,
                        amount=slip.net_pay,
                        payment_date=date.today(),
                        remarks=f"Chi trả lương tháng {period_month}/{period_year} cho nhân viên {slip.employee.full_name} ({slip.employee.employee_id}). Thực lĩnh: {slip.net_pay:,.2f}đ. Phương thức: Chuyển khoản.",
                    )
                )
            elif slip.net_pay < 0:
                txs_to_create.append(
                    CashFlowTransaction(
                        name=tx_name,
                        payment_type="receive",
                        category="Chi trả lương nhân viên",
                        payment_method=payment_method,
                        amount=abs(slip.net_pay),
                        payment_date=date.today(),
                        remarks=f"Thu hồi lương âm tháng {period_month}/{period_year} của nhân viên {slip.employee.full_name} ({slip.employee.employee_id}). Số tiền: {abs(slip.net_pay):,.2f}đ.",
                    )
                )

    # 3. Thực thi bulk update các phiếu lương
    SalarySlip.objects.bulk_update(slips_to_update, fields=["status", "payment_method"])

    # 4. Thực thi bulk create các giao dịch dòng tiền
    if txs_to_create:
        created_txs = CashFlowTransaction.objects.bulk_create(txs_to_create)
        # Tạo log cho các giao dịch dòng tiền mới được tạo
        for tx in created_txs:
            logs_to_create.append(
                SystemLog(
                    user=creator,
                    action="create",
                    table_name="cash_flow_transaction",
                    record_id=str(tx.id),
                    new_value={
                        "name": tx.name,
                        "payment_type": tx.payment_type,
                        "category": tx.category,
                        "amount": str(tx.amount),
                        "payment_date": str(tx.payment_date),
                    },
                )
            )

    # 5. Thực thi bulk create tất cả log hệ thống
    if logs_to_create:
        SystemLog.objects.bulk_create(logs_to_create)

    return slips


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
