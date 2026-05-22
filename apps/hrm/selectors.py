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
