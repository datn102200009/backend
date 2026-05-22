from decimal import Decimal

import factory

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
