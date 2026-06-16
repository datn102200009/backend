from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import SystemLog
from apps.common.xlib.exceptions import NotFoundException, PermissionException, ValidationException
from apps.finance.models import CashFlowTransaction, SalarySlip
from apps.finance.services import (
    payroll_approve_slip,
    payroll_bulk_approve,
    payroll_bulk_approve_and_pay,
    payroll_bulk_pay,
    payroll_pay_slip,
    payroll_reject_slip,
)
from apps.hrm.services import contract_terminate
from apps.hrm.tests.factories import EmployeeFactory, EmploymentContractFactory, SalarySlipFactory
from apps.inventory.tests.factories import UserFactory


@pytest.mark.django_db
class TestFinancePayrollServices:

    def test_payroll_approve_slip_success(self, mock_permission_checker):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_APR_1")
        user = UserFactory(username="finance_user_1")
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="pending_finance_review")

        # Act
        approved_slip = payroll_approve_slip(user=user, salary_slip_id=str(slip.id))

        # Assert
        assert approved_slip.status == "approved"
        assert approved_slip.approved_by == user
        assert approved_slip.approved_at is not None
        mock_permission_checker.assert_called_with(user, "finance.payroll_approve")

        # Check log
        log = SystemLog.objects.filter(table_name="salary_slip", record_id=str(slip.id), user=user).first()
        assert log is not None
        assert log.action == "update"
        assert log.old_value == {"status": "pending_finance_review"}
        assert log.new_value["status"] == "approved"

    def test_payroll_approve_slip_invalid_status(self, mock_permission_checker):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_APR_2")
        user = UserFactory(username="finance_user_2")
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="paid")

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            payroll_approve_slip(user=user, salary_slip_id=str(slip.id))
        assert "Chỉ có thể phê duyệt" in str(exc_info.value)

    def test_payroll_reject_slip_success(self, mock_permission_checker):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_REJ_1")
        user = UserFactory(username="finance_user_3")
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="pending_finance_review")
        reason = "Lý do từ chối phiếu lương dài hơn 10 ký tự"

        # Act
        rejected_slip = payroll_reject_slip(user=user, salary_slip_id=str(slip.id), reason=reason)

        # Assert
        assert rejected_slip.status == "calculated"
        assert rejected_slip.remarks == reason
        mock_permission_checker.assert_called_with(user, "finance.payroll_approve")

        # Check log
        log = SystemLog.objects.filter(table_name="salary_slip", record_id=str(slip.id), user=user).first()
        assert log is not None
        assert log.new_value == {"status": "calculated", "remarks": reason}

    def test_payroll_reject_slip_invalid_status(self, mock_permission_checker):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_REJ_2")
        user = UserFactory(username="finance_user_4")
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="draft")

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            payroll_reject_slip(user=user, salary_slip_id=str(slip.id), reason="Lý do từ chối phiếu lương")
        assert "Chỉ có thể từ chối" in str(exc_info.value)

    def test_payroll_reject_slip_short_reason(self, mock_permission_checker):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_REJ_3")
        user = UserFactory(username="finance_user_5")
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="pending_finance_review")

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            payroll_reject_slip(user=user, salary_slip_id=str(slip.id), reason="Ngắn")
        assert "từ 10 ký tự" in str(exc_info.value)

    def test_payroll_pay_slip_creates_cashflow(self, mock_permission_checker):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_PAY_1")
        user = UserFactory(username="finance_user_6")
        slip = SalarySlipFactory(
            employee=employee,
            salary_period="2026-05",
            status="approved",
            net_pay=Decimal("15000000.00"),
        )

        # Act
        paid_slip = payroll_pay_slip(user=user, salary_slip_id=str(slip.id), payment_method="bank_transfer")

        # Assert
        assert paid_slip.status == "paid"
        assert paid_slip.payment_method == "bank_transfer"
        mock_permission_checker.assert_called_with(user, "finance.change_salaryslip")

        # Verify CashFlowTransaction created
        tx = CashFlowTransaction.objects.filter(name="PAY-SALARY-EMP_PAY_1-2026-05").first()
        assert tx is not None
        assert tx.payment_type == "pay"
        assert tx.amount == Decimal("15000000.00")
        assert tx.category == "Chi trả lương nhân viên"

    def test_payroll_pay_slip_negative_amount(self, mock_permission_checker):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_PAY_2")
        user = UserFactory(username="finance_user_7")
        slip = SalarySlipFactory(
            employee=employee,
            salary_period="2026-05",
            status="approved",
            net_pay=Decimal("-500000.00"),
        )

        # Act
        paid_slip = payroll_pay_slip(user=user, salary_slip_id=str(slip.id), payment_method="cash")

        # Assert
        assert paid_slip.status == "paid"
        assert paid_slip.payment_method == "cash"

        # Verify CashFlowTransaction created (receive positive absolute amount)
        tx = CashFlowTransaction.objects.filter(name="COLLECT-SALARY-EMP_PAY_2-2026-05").first()
        assert tx is not None
        assert tx.payment_type == "receive"
        assert tx.amount == Decimal("500000.00")
        assert tx.category == "Thu hồi lương âm"

    def test_payroll_bulk_approve_and_pay(self, mock_permission_checker):
        # Arrange
        emp1 = EmployeeFactory(employee_id="EMP_BULK_1")
        emp2 = EmployeeFactory(employee_id="EMP_BULK_2")
        emp3 = EmployeeFactory(employee_id="EMP_BULK_3")
        user = UserFactory(username="finance_user_8")
        slip1 = SalarySlipFactory(
            employee=emp1,
            salary_period="2026-06",
            status="pending_finance_review",
            net_pay=Decimal("10000000.00"),
        )
        slip2 = SalarySlipFactory(
            employee=emp2,
            salary_period="2026-06",
            status="calculated",
            net_pay=Decimal("-100000.00"),
        )
        slip3 = SalarySlipFactory(
            employee=emp3,
            salary_period="2026-06",
            status="approved",
            net_pay=Decimal("5000000.00"),
        )

        # Act
        updated_slips = payroll_bulk_approve_and_pay(
            salary_period="2026-06",
            payment_method="bank_transfer",
            creator=user,
        )

        # Assert
        assert len(updated_slips) == 2
        slip1.refresh_from_db()
        slip2.refresh_from_db()
        slip3.refresh_from_db()
        assert slip1.status == "paid"
        assert slip2.status == "calculated"
        assert slip3.status == "paid"

        # Check transactions
        tx1 = CashFlowTransaction.objects.filter(name="PAY-SALARY-EMP_BULK_1-2026-06").first()
        tx2 = CashFlowTransaction.objects.filter(name="COLLECT-SALARY-EMP_BULK_2-2026-06").first()
        tx3 = CashFlowTransaction.objects.filter(name="PAY-SALARY-EMP_BULK_3-2026-06").first()
        assert tx1 is not None
        assert tx1.amount == Decimal("10000000.00")
        assert tx2 is None
        assert tx3 is not None
        assert tx3.amount == Decimal("5000000.00")

    def test_hrm_no_cashflow_on_terminate(self, mock_permission_checker):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_TERM_1", salary_base=Decimal("10000000.00"))
        admin = UserFactory(username="hrm_admin")
        contract = EmploymentContractFactory(employee=employee, status="active")

        # Act
        contract_terminate(
            contract_id=str(contract.id),
            termination_date=date.today(),
            reason="Nghỉ việc",
            terminator=admin,
        )

        # Assert
        tx_pay = CashFlowTransaction.objects.filter(name__contains=f"SALARY-{employee.employee_id}").first()
        assert tx_pay is None

    def test_payroll_approve_slip_permission_denied(self, mock_permission_checker):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_APR_PERM")
        user = UserFactory(username="no_permission_user")
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="pending_finance_review")

        mock_permission_checker.side_effect = PermissionException("Không có quyền")

        # Act & Assert
        with pytest.raises(PermissionException):
            payroll_approve_slip(user=user, salary_slip_id=str(slip.id))

    def test_payroll_bulk_approve(self, mock_permission_checker):
        # Arrange
        emp1 = EmployeeFactory(employee_id="EMP_BULK_APP_1")
        emp2 = EmployeeFactory(employee_id="EMP_BULK_APP_2")
        user = UserFactory(username="finance_user_app")
        slip1 = SalarySlipFactory(
            employee=emp1,
            salary_period="2026-06",
            status="pending_finance_review",
        )
        slip2 = SalarySlipFactory(
            employee=emp2,
            salary_period="2026-06",
            status="calculated",
        )

        # Act
        approved_slips = payroll_bulk_approve(
            salary_period="2026-06",
            creator=user,
        )

        # Assert
        assert len(approved_slips) == 1
        slip1.refresh_from_db()
        slip2.refresh_from_db()
        assert slip1.status == "approved"
        assert slip1.approved_by == user
        assert slip2.status == "calculated"

    def test_payroll_bulk_pay(self, mock_permission_checker):
        # Arrange
        emp1 = EmployeeFactory(employee_id="EMP_BULK_PAY_1")
        emp2 = EmployeeFactory(employee_id="EMP_BULK_PAY_2")
        user = UserFactory(username="finance_user_pay")
        slip1 = SalarySlipFactory(
            employee=emp1,
            salary_period="2026-06",
            status="approved",
            net_pay=Decimal("4000000.00"),
        )
        slip2 = SalarySlipFactory(
            employee=emp2,
            salary_period="2026-06",
            status="pending_finance_review",
            net_pay=Decimal("3000000.00"),
        )

        # Act
        paid_slips = payroll_bulk_pay(
            salary_period="2026-06",
            payment_method="bank_transfer",
            creator=user,
        )

        # Assert
        assert len(paid_slips) == 1
        slip1.refresh_from_db()
        slip2.refresh_from_db()
        assert slip1.status == "paid"
        assert slip1.payment_method == "bank_transfer"
        assert slip2.status == "pending_finance_review"

        # Check transaction
        tx = CashFlowTransaction.objects.filter(name="PAY-SALARY-EMP_BULK_PAY_1-2026-06").first()
        assert tx is not None
        assert tx.amount == Decimal("4000000.00")
