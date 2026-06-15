"""
Selectors for hrm app.

All read operations and complex queries should be defined here.
Always optimize with select_related() and prefetch_related() to avoid N+1 queries.
"""

from datetime import timedelta

from django.db import models

from apps.hrm.models import EmploymentContract, EmploymentHistory, LeaveRequest
from apps.master_data.models import Employee


def employee_get_detail_with_relations(employee_id: str) -> Employee:
    """
    Lấy thông tin chi tiết nhân viên cùng các quan hệ:
    Hợp đồng, Lịch sử thay đổi, Tài liệu, Khen thưởng, Kỷ luật.
    """
    return Employee.objects.prefetch_related(
        "contracts",
        "employment_histories",
        "documents",
        "rewards",
        "disciplines",
    ).get(id=employee_id)


def is_salary_period_fully_paid(salary_period: str) -> bool:
    """
    Kiểm tra xem kỳ lương đã được thanh toán 100% chưa.
    Một kỳ lương được coi là thanh toán 100% nếu có ít nhất một phiếu lương và tất cả phiếu lương đều ở trạng thái 'paid'.
    """
    from apps.finance.models import SalarySlip

    slips = SalarySlip.objects.filter(salary_period=salary_period)
    if not slips.exists():
        return False
    return not slips.exclude(status="paid").exists()


def get_salary_timeline(employee, period_start, period_end):
    """Trả về [(date, salary_base)] - các điểm thay đổi lương trong kỳ."""
    histories = EmploymentHistory.objects.filter(
        employee=employee,
        status="approved",
        effective_date__lte=period_end,
    ).order_by("effective_date")
    earliest = histories.filter(effective_date__lt=period_start).order_by("-effective_date").first()
    base_at_start = earliest.new_salary_base if earliest else employee.salary_base
    timeline = [(period_start, base_at_start)]
    for h in histories:
        if period_start < h.effective_date <= period_end:
            timeline.append((h.effective_date, h.new_salary_base))
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
    history = (
        EmploymentHistory.objects.filter(
            employee=employee,
            status="approved",
            effective_date__lte=target_date,
        )
        .order_by("-effective_date")
        .first()
    )
    return history.new_salary_base if history else employee.salary_base
