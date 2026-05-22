from decimal import Decimal

import factory

from apps.hrm.models import Attendance, EmployeeDocument, EmploymentContract, EmploymentHistory, LeaveRequest
from apps.master_data.models import Employee


class EmployeeFactory(factory.django.DjangoModelFactory):
    """Factory để tạo Employee phục vụ kiểm thử."""

    class Meta:
        model = Employee
        django_get_or_create = ("employee_id",)

    employee_id = factory.Sequence(lambda n: f"EMP{n:04d}")
    full_name = factory.Faker("name")
    department = "HR"
    position_title = "Staff"
    salary_base = Decimal("10000000.00")
    is_union_member = False
    email = factory.Sequence(lambda n: f"emp{n}@example.com")
    phone = "0987654321"
    gender = "male"
    employment_status = "active"


class EmploymentContractFactory(factory.django.DjangoModelFactory):
    """Factory để tạo EmploymentContract phục vụ kiểm thử."""

    class Meta:
        model = EmploymentContract

    employee = factory.SubFactory(EmployeeFactory)
    contract_no = factory.Sequence(lambda n: f"HDLD-{n:04d}")
    contract_type = "definite_term"
    start_date = "2026-01-01"
    end_date = "2026-12-31"
    status = "active"


class EmploymentHistoryFactory(factory.django.DjangoModelFactory):
    """Factory để tạo EmploymentHistory phục vụ kiểm thử."""

    class Meta:
        model = EmploymentHistory

    employee = factory.SubFactory(EmployeeFactory)
    change_type = "salary_change"
    old_salary_base = Decimal("10000000.00")
    new_salary_base = Decimal("12000000.00")
    effective_date = "2026-06-01"
    reason = "Tăng lương định kỳ"


class AttendanceFactory(factory.django.DjangoModelFactory):
    """Factory để tạo Attendance phục vụ kiểm thử."""

    class Meta:
        model = Attendance

    employee = factory.SubFactory(EmployeeFactory)
    date = "2026-05-01"
    status = "working"
    work_hours = Decimal("8.00")
    overtime_hours = Decimal("0.00")


class LeaveRequestFactory(factory.django.DjangoModelFactory):
    """Factory để tạo LeaveRequest phục vụ kiểm thử."""

    class Meta:
        model = LeaveRequest

    employee = factory.SubFactory(EmployeeFactory)
    leave_type = "annual"
    start_date = "2026-05-01"
    end_date = "2026-05-03"
    days = Decimal("3.0")
    reason = "Nghỉ mát gia đình"
    status = "pending"
