from decimal import Decimal

import factory

from apps.finance.models import SalarySlip
from apps.hrm.models import (
    Attendance,
    DisciplineRecord,
    EmployeeDocument,
    EmploymentContract,
    LeaveRequest,
    RewardRecord,
)
from apps.master_data.models import Employee


class EmployeeFactory(factory.django.DjangoModelFactory):
    """Factory để tạo Employee phục vụ kiểm thử."""

    class Meta:
        model = Employee
        django_get_or_create = ("employee_id",)

    employee_id = factory.Sequence(lambda n: f"NV{n:04d}")
    full_name = factory.Faker("name")
    email = factory.Sequence(lambda n: f"emp{n}@example.com")
    phone = "0987654321"
    gender = "male"
    employment_status = "active"

    @factory.post_generation
    def salary_base(obj, create, extracted, **kwargs):
        if not create:
            return

        create_contract = kwargs.get("create_contract", True)
        if not create_contract:
            return

        salary = extracted if extracted is not None else Decimal("10000000.00")

        from apps.hrm.models import EmploymentContract

        # Tạo hợp đồng mặc định cho nhân viên để test
        EmploymentContract.objects.create(
            employee=obj,
            contract_no=f"HDLD-{obj.employee_id}",
            contract_type="definite_term",
            start_date="2026-01-01",
            end_date="2026-12-31",
            status="active",
            salary_base=salary,
        )


class EmploymentContractFactory(factory.django.DjangoModelFactory):
    """Factory để tạo EmploymentContract phục vụ kiểm thử."""

    class Meta:
        model = EmploymentContract

    employee = factory.SubFactory(EmployeeFactory, salary_base__create_contract=False)
    contract_no = factory.Sequence(lambda n: f"HDLD-{n:04d}")
    contract_type = "definite_term"
    start_date = "2026-01-01"
    end_date = "2026-12-31"
    status = "active"
    salary_base = Decimal("10000000.00")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        employee = kwargs.get("employee")
        status_val = kwargs.get("status", "active")
        if employee and status_val == "active":
            model_class.objects.filter(employee=employee, status="active").update(status="expired")
        return super()._create(model_class, *args, **kwargs)


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
    leave_type = "paid"
    start_date = "2026-05-01"
    end_date = "2026-05-03"
    days = Decimal("3.0")
    reason = "Nghỉ mát gia đình"
    status = "pending"


class SalarySlipFactory(factory.django.DjangoModelFactory):
    """Factory để tạo SalarySlip phục vụ kiểm thử."""

    class Meta:
        model = SalarySlip

    name = factory.Sequence(lambda n: f"SLIP-{n:04d}")
    employee = factory.SubFactory(EmployeeFactory)
    salary_period = "2026-05"
    base_salary = Decimal("0.00")
    overtime_amount = Decimal("0.00")
    allowance_amount = Decimal("0.00")
    reward_amount_total = Decimal("0.00")
    discipline_deduction_total = Decimal("0.00")
    gross_pay = Decimal("0.00")
    deductions = Decimal("0.00")
    net_pay = Decimal("0.00")
    payment_method = "bank_transfer"
    status = "draft"


class RewardRecordFactory(factory.django.DjangoModelFactory):
    """Factory để tạo RewardRecord phục vụ kiểm thử."""

    class Meta:
        model = RewardRecord

    employee = factory.SubFactory(EmployeeFactory)
    reward_date = "2026-05-15"
    reward_type = "performance_bonus"
    amount = Decimal("1000000.00")
    description = "Thành tích xuất sắc tháng"
    status = "approved"


class DisciplineRecordFactory(factory.django.DjangoModelFactory):
    """Factory để tạo DisciplineRecord phục vụ kiểm thử."""

    class Meta:
        model = DisciplineRecord

    employee = factory.SubFactory(EmployeeFactory)
    incident_date = "2026-05-10"
    discipline_date = "2026-05-12"
    discipline_type = "warning"
    penalty_amount = Decimal("500000.00")
    description = "Đi muộn nhiều lần"
    status = "approved"
