"""
Selectors for hrm app.

All read operations and complex queries should be defined here.
Always optimize with select_related() and prefetch_related() to avoid N+1 queries.
"""

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
