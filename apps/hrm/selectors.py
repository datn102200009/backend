"""
Selectors for hrm app.

All read operations and complex queries should be defined here.
Always optimize with select_related() and prefetch_related() to avoid N+1 queries.
"""

from datetime import timedelta
from typing import Optional

from django.db import models

from apps.hrm.models import EmploymentContract, LeaveRequest
from apps.master_data.models import Employee


def employee_get_detail_with_relations(employee_id: str) -> Employee:
    """
    Lấy thông tin chi tiết nhân viên cùng các quan hệ:
    Hợp đồng, Tài liệu, Khen thưởng, Kỷ luật.
    """
    return Employee.objects.prefetch_related(
        "contracts",
        "documents",
        "rewards",
        "disciplines",
    ).get(id=employee_id)


def is_salary_period_fully_paid(salary_period: str) -> bool:
    """Kỳ đã chốt = có ít nhất 1 slip vượt khỏi 'calculated' (đã gửi duyệt, đã duyệt, hoặc đã trả)."""
    from apps.finance.models import SalarySlip

    return SalarySlip.objects.filter(
        salary_period=salary_period,
        status__in=["pending_finance_review", "approved", "paid"],
    ).exists()


def get_active_contract_at_date(employee, target_date) -> Optional[EmploymentContract]:
    """Trả về EmploymentContract đang active tại target_date, hoặc None.
    Quy tắc "mới nhất thắng": nếu có nhiều HĐ overlap, lấy HĐ có start_date lớn nhất.
    """
    return (
        EmploymentContract.objects.filter(
            employee=employee,
            start_date__lte=target_date,
        )
        .filter(models.Q(end_date__isnull=True) | models.Q(end_date__gte=target_date))
        .order_by("-start_date")
        .first()
    )


def get_salary_timeline(employee, period_start, period_end):
    """
    Trả về [(date, salary_base)] - các điểm thay đổi lương trong kỳ.
    NGUỒN CHÂN LÝ: EmploymentContract. KHÔNG dùng EmploymentHistory.
    """
    contracts = (
        EmploymentContract.objects.filter(
            employee=employee,
            start_date__lte=period_end,
        )
        .filter(models.Q(end_date__isnull=True) | models.Q(end_date__gte=period_start))
        .order_by("start_date")
    )

    timeline = []
    for contract in contracts:
        effective_start = max(contract.start_date, period_start)
        timeline.append((effective_start, contract.salary_base))
    return timeline


def split_into_segments(timeline, period_start, period_end):
    """Từ timeline → list [(start, end, salary)]."""
    segments = []
    sorted_tl = sorted(timeline, key=lambda x: x[0])
    for i, (change_date, salary) in enumerate(sorted_tl):
        seg_start = max(change_date, period_start)
        seg_end = min(sorted_tl[i + 1][0] - timedelta(days=1) if i + 1 < len(sorted_tl) else period_end, period_end)
        if seg_start <= seg_end:
            segments.append((seg_start, seg_end, salary))
    return segments


def get_salary_for_day(employee, target_date):
    """Lookup lương cho 1 ngày cụ thể. Xử lý khoảng cách HĐLĐ (TH4 mở rộng)."""
    if not EmploymentContract.objects.filter(employee=employee).exists():
        return (get_salary_at_date(employee, target_date), "dummy_contract")

    contract = (
        EmploymentContract.objects.filter(
            employee=employee,
            start_date__lte=target_date,
        )
        .filter(models.Q(end_date__isnull=True) | models.Q(end_date__gte=target_date))
        .order_by("-start_date")
        .first()
    )
    if contract:
        return (get_salary_at_date(employee, target_date), contract)
    # Không có HĐLĐ → kiểm tra LeaveRequest
    leave = LeaveRequest.objects.filter(
        employee=employee,
        start_date__lte=target_date,
        end_date__gte=target_date,
        status="approved",
    ).first()
    if leave:
        prev_contract = (
            EmploymentContract.objects.filter(
                employee=employee,
                end_date__lt=target_date,
            )
            .order_by("-end_date")
            .first()
        )
        if prev_contract:
            return (get_salary_at_date(employee, prev_contract.end_date), prev_contract)
    return (None, None)


def get_salary_at_date(employee, target_date):
    """
    Trả về mức lương cơ bản tại một ngày cụ thể.
    NGUỒN CHÂN LÝ: EmploymentContract active tại target_date.
    """
    contract = get_active_contract_at_date(employee, target_date)
    from decimal import Decimal

    return contract.salary_base if (contract and contract.salary_base is not None) else Decimal("0.00")


def count_active_contracts(employee, exclude_contract_id: Optional[str] = None) -> int:
    """Đếm số hợp đồng đang active cho một nhân viên."""
    qs = EmploymentContract.objects.filter(employee=employee, status="active")
    if exclude_contract_id:
        qs = qs.exclude(id=exclude_contract_id)
    return qs.count()


def is_current_salary_period(salary_period: str, reference_date: Optional[object] = None) -> bool:
    """
    Kiểm tra kỳ lương (YYYY-MM) có phải tháng hiện tại hay không.
    Mặc định tham chiếu theo timezone.now().date() của server.
    """
    from datetime import date

    from django.utils import timezone

    ref = reference_date or timezone.now().date()
    return salary_period == f"{ref.year:04d}-{ref.month:02d}"
