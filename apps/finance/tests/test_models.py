import pytest

from apps.finance.models import CashFlowTransaction
from apps.finance.tests.factories import CashFlowTransactionFactory

pytestmark = pytest.mark.django_db


class TestCashFlowModel:
    def test_cash_flow_creation(self):
        transaction = CashFlowTransactionFactory(payment_type="receive", amount=150.0)
        assert transaction.id is not None
        assert transaction.payment_type == "receive"
        assert transaction.amount == 150.0
        assert str(transaction).startswith("CF-")


class TestSalarySlipModel:
    def test_unique_salary_slip_per_period_constraint(self):
        from django.db.utils import IntegrityError

        from apps.hrm.tests.factories import EmployeeFactory, SalarySlipFactory

        employee = EmployeeFactory()

        # Tạo phiếu lương đầu tiên thành công
        SalarySlipFactory(employee=employee, salary_period="2026-06")

        # Tạo phiếu lương thứ hai trùng lặp nhân viên và kỳ lương phải ném IntegrityError
        with pytest.raises(IntegrityError):
            SalarySlipFactory(employee=employee, salary_period="2026-06")
