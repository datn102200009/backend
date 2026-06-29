from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.accounts.models import SystemLog, User
from apps.common.xlib.exceptions import ValidationException
from apps.hrm.models import DisciplineRecord, EmployeeDocument, EmploymentContract
from apps.hrm.services import contract_create_or_renew, contract_renew, contract_terminate, discipline_record_approve
from apps.hrm.tests.factories import (
    DisciplineRecordFactory,
    EmployeeFactory,
    EmploymentContractFactory,
    SalarySlipFactory,
)
from apps.inventory.tests.factories import UserFactory


@pytest.mark.django_db
class TestContractServices:

    def test_contract_create_first_contract(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP0001", full_name="John Doe")
        admin = UserFactory(username="admin_creator")
        contract_data = {
            "contract_no": "HDLD-2026-0001",
            "contract_type": "definite_term",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "note": "Hợp đồng lao động năm 2026",
            "file_url": "https://example.com/scan_contract.pdf",
        }

        # Act
        contract = contract_create_or_renew(employee_id=employee.id, contract_data=contract_data, creator=admin)

        # Assert
        assert contract is not None
        assert contract.contract_no == "HDLD-2026-0001"
        assert contract.status == "active"
        assert contract.employee == employee

        # Verify EmployeeDocument was created for the scan
        doc = EmployeeDocument.objects.filter(employee=employee, doc_type="contract_scan").first()
        assert doc is not None
        assert doc.file_url == "https://example.com/scan_contract.pdf"
        assert doc.uploaded_by == admin

        # Verify SystemLog for contract creation
        log = SystemLog.objects.filter(table_name="employment_contract", record_id=str(contract.id), user=admin).first()
        assert log is not None
        assert log.action == "create"

    def test_contract_renew_expires_old_contract(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP0002", full_name="Jane Doe")
        admin = UserFactory(username="admin_creator")
        old_contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-OLD", status="active")

        new_contract_data = {
            "contract_no": "HDLD-NEW",
            "contract_type": "indefinite_term",
            "start_date": date(2027, 1, 1),
            "note": "Gia hạn hợp đồng vô thời hạn",
        }

        # Act
        new_contract = contract_create_or_renew(employee_id=employee.id, contract_data=new_contract_data, creator=admin)

        # Assert
        # Refresh old contract from DB
        old_contract.refresh_from_db()
        assert old_contract.status == "expired"
        assert new_contract.contract_no == "HDLD-NEW"
        assert new_contract.status == "active"

        # Verify SystemLogs for both old contract update (to expired) and new contract create
        old_log = SystemLog.objects.filter(
            table_name="employment_contract", record_id=str(old_contract.id), action="update", user=admin
        ).first()
        assert old_log is not None
        assert old_log.new_value["status"] == "expired"

        new_log = SystemLog.objects.filter(
            table_name="employment_contract", record_id=str(new_contract.id), action="create", user=admin
        ).first()
        assert new_log is not None

    def test_contract_terminate_disables_user_and_employee(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP0003", full_name="Bob Smith", employment_status="active")
        # Create an associated user
        user = UserFactory(username="bobsmith", employee_id="EMP0003", is_active=True)
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-BOB", status="active")
        admin = UserFactory(username="admin_creator")

        # Act
        terminated_contract = contract_terminate(
            contract_id=contract.id,
            termination_date=date(2026, 6, 30),
            reason="Sa thải do vi phạm kỷ luật",
            terminator=admin,
            file_url="https://example.com/quyet_dinh_thoi_viec.pdf",
        )

        # Assert
        terminated_contract.refresh_from_db()
        employee.refresh_from_db()

        assert terminated_contract.status == "terminated"
        assert terminated_contract.end_date == date(2026, 6, 30)
        assert employee.employment_status == "inactive"
        assert employee.leave_date == date(2026, 6, 30)
        assert not User.objects.filter(id=user.id).exists()

        # Verify Document was created
        doc = EmployeeDocument.objects.filter(employee=employee, doc_type="resignation_letter").first()
        assert doc is not None
        assert doc.file_url == "https://example.com/quyet_dinh_thoi_viec.pdf"

        # Verify Logs
        contract_log = SystemLog.objects.filter(
            table_name="employment_contract", record_id=str(contract.id), action="update", user=admin
        ).first()
        assert contract_log is not None
        assert contract_log.new_value["status"] == "terminated"

        employee_log = SystemLog.objects.filter(
            table_name="employee", record_id=str(employee.id), action="update", user=admin
        ).first()
        assert employee_log is not None
        assert employee_log.new_value["employment_status"] == "inactive"

        user_log = SystemLog.objects.filter(
            table_name="user", record_id=str(user.id), action="delete", user=admin
        ).first()
        assert user_log is not None
        assert user_log.old_value["username"] == "bobsmith"

    def test_contract_create_or_renew_overlap(self):
        employee = EmployeeFactory(salary_base=Decimal("10000000.00"))
        admin = UserFactory(username="admin_pr4_test1")

        # HĐLĐ cũ
        contract1 = EmploymentContractFactory(
            employee=employee,
            contract_no="CON-001",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            status="active",
        )

        # Tái ký sớm: HĐLĐ mới bắt đầu từ 15/06
        contract2 = contract_create_or_renew(
            employee_id=str(employee.id),
            contract_data={
                "contract_no": "CON-002",
                "contract_type": "definite_term",
                "start_date": date(2026, 6, 15),
                "end_date": date(2026, 12, 31),
            },
            creator=admin,
        )

        # Verify old contract's end_date adjusted
        contract1.refresh_from_db()
        assert contract1.end_date == date(2026, 6, 14)
        assert contract2.status == "active"

        # Validate start_date mới phải >= start_date HĐLĐ cũ
        with pytest.raises(ValidationException) as exc_info:
            contract_create_or_renew(
                employee_id=str(employee.id),
                contract_data={
                    "contract_no": "CON-003",
                    "contract_type": "definite_term",
                    "start_date": date(2026, 6, 10),
                },
                creator=admin,
            )
        assert "phải >= start_date HĐLĐ cũ" in str(exc_info.value)

    def test_contract_renew_basic(self):
        employee = EmployeeFactory(salary_base=Decimal("10000000.00"))
        admin = UserFactory(username="admin_pr4_renew1")
        contract = EmploymentContractFactory(
            employee=employee,
            contract_no="CON-EXP-1",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
            status="active",
        )

        result = contract_renew(
            contract_id=str(contract.id),
            new_contract_no="CON-EXP-1-RENEW",
            new_contract_type="definite_term",
            start_date=date(2026, 6, 1),
            renewer=admin,
        )

        new_contract = result["contract"]

        assert new_contract is not None
        assert new_contract.contract_no == "CON-EXP-1-RENEW"
        assert new_contract.start_date == date(2026, 6, 1)
        assert new_contract.status == "active"

        # Verify old contract is expired
        contract.refresh_from_db()
        assert contract.status == "expired"

    def test_contract_renew_with_salary_change(self):
        employee = EmployeeFactory(salary_base__create_contract=False)
        admin = UserFactory(username="admin_pr4_renew2")
        contract = EmploymentContractFactory(
            employee=employee,
            contract_no="CON-EXP-2",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
            status="active",
            salary_base=Decimal("10000000.00"),
        )

        result = contract_renew(
            contract_id=str(contract.id),
            new_contract_no="CON-EXP-2-RENEW",
            new_contract_type="definite_term",
            start_date=date(2026, 6, 1),
            new_salary_base=Decimal("12000000.00"),
            renewer=admin,
        )

        new_contract = result["contract"]

        assert new_contract is not None
        assert new_contract.contract_no == "CON-EXP-2-RENEW"
        assert new_contract.salary_base == Decimal("12000000.00")

        # Verify employee's salary updated immediately
        from apps.hrm.selectors import get_salary_at_date

        assert get_salary_at_date(employee, date(2026, 6, 1)) == Decimal("12000000.00")


@pytest.mark.django_db
class TestDisciplineRecordTerminationSideEffects:

    def test_discipline_approve_termination_terminates_active_contract(self):
        employee = EmployeeFactory(
            employee_id="EMP_TERM_1", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-TERM-1", status="active")
        admin = UserFactory(username="admin_term_1")
        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            status="pending_approval",
        )

        discipline_record_approve(user=admin, discipline_id=str(discipline.id))

        contract.refresh_from_db()
        employee.refresh_from_db()
        discipline.refresh_from_db()

        assert discipline.status == "approved"
        assert contract.status == "terminated"
        assert contract.end_date == date(2026, 6, 15)

    def test_discipline_approve_termination_disables_user(self):
        employee = EmployeeFactory(
            employee_id="EMP_TERM_2", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-TERM-2", status="active")
        user = UserFactory(username="term_user_2", employee_id="EMP_TERM_2", is_active=True)
        admin = UserFactory(username="admin_term_2")
        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            status="pending_approval",
        )

        discipline_record_approve(user=admin, discipline_id=str(discipline.id))

        assert not User.objects.filter(id=user.id).exists()

    def test_discipline_approve_termination_sets_employee_inactive(self):
        employee = EmployeeFactory(
            employee_id="EMP_TERM_3", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-TERM-3", status="active")
        admin = UserFactory(username="admin_term_3")
        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            status="pending_approval",
        )

        discipline_record_approve(user=admin, discipline_id=str(discipline.id))

        employee.refresh_from_db()
        assert employee.employment_status == "inactive"
        assert employee.leave_date == date(2026, 6, 15)

    def test_discipline_approve_termination_creates_final_salary_slip(self):
        from apps.finance.models import SalarySlip

        employee = EmployeeFactory(
            employee_id="EMP_TERM_4", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-TERM-4", status="active")
        admin = UserFactory(username="admin_term_4")
        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            status="pending_approval",
        )

        discipline_record_approve(user=admin, discipline_id=str(discipline.id))

        assert SalarySlip.objects.filter(employee=employee, salary_period="2026-06").exists()

    def test_discipline_approve_termination_creates_employee_document(self):
        employee = EmployeeFactory(
            employee_id="EMP_TERM_5", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-TERM-5", status="active")
        admin = UserFactory(username="admin_term_5")
        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            file_url="https://example.com/dec.pdf",
            status="pending_approval",
        )

        discipline_record_approve(user=admin, discipline_id=str(discipline.id))

        doc = EmployeeDocument.objects.filter(employee=employee).first()
        assert doc is not None
        assert doc.file_url == "https://example.com/dec.pdf"

    def test_discipline_approve_termination_no_active_contract_handles_gracefully(self):
        employee = EmployeeFactory(
            employee_id="NV_TERM_6", salary_base__create_contract=False, employment_status="active"
        )
        admin = UserFactory(username="admin_term_6")
        user = UserFactory(username="term_user_6", employee_id="NV_TERM_6", is_active=True)
        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            file_url="https://example.com/dec6.pdf",
            status="pending_approval",
        )

        discipline_record_approve(user=admin, discipline_id=str(discipline.id))

        employee.refresh_from_db()
        discipline.refresh_from_db()

        assert discipline.status == "approved"
        assert employee.employment_status == "inactive"
        assert employee.leave_date == date(2026, 6, 15)
        assert not User.objects.filter(id=user.id).exists()

        doc = EmployeeDocument.objects.filter(employee=employee, doc_type="disciplinary_minutes").first()
        assert doc is not None
        assert doc.file_url == "https://example.com/dec6.pdf"

    def test_discipline_approve_termination_with_no_linked_user(self):
        employee = EmployeeFactory(employee_id="EMP_TERM_7", employment_status="active")
        admin = UserFactory(username="admin_term_7")
        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            status="pending_approval",
        )

        discipline_record_approve(user=admin, discipline_id=str(discipline.id))

        discipline.refresh_from_db()
        employee.refresh_from_db()
        assert discipline.status == "approved"
        assert employee.employment_status == "inactive"

    def test_discipline_approve_termination_fails_if_unpaid_previous_payroll(self):
        employee = EmployeeFactory(
            employee_id="EMP_TERM_8", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-TERM-8", status="active")
        admin = UserFactory(username="admin_term_8")

        from apps.finance.models import SalarySlip

        SalarySlipFactory(employee=employee, salary_period="2026-05", status="draft")

        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            status="pending_approval",
        )

        with pytest.raises(ValidationException) as exc_info:
            discipline_record_approve(user=admin, discipline_id=str(discipline.id))
        assert "vẫn còn nợ lương kỳ trước chưa thanh toán" in str(exc_info.value)

        discipline.refresh_from_db()
        assert discipline.status == "pending_approval"

    def test_discipline_approve_termination_rolls_back_on_contract_terminate_failure(self):
        employee = EmployeeFactory(
            employee_id="EMP_TERM_9", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-TERM-9", status="active")
        admin = UserFactory(username="admin_term_9")

        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            status="pending_approval",
        )

        with patch("apps.hrm.services.contract_terminate", side_effect=ValidationException("Mocked failure")):
            with pytest.raises(ValidationException, match="Không thể sa thải nhân viên: Mocked failure"):
                discipline_record_approve(user=admin, discipline_id=str(discipline.id))

        discipline.refresh_from_db()
        assert discipline.status == "pending_approval"

    def test_discipline_approve_non_termination_does_not_terminate_employee(self):
        employee = EmployeeFactory(
            employee_id="EMP_TERM_10", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-TERM-10", status="active")
        user = UserFactory(username="term_user_10", employee_id="EMP_TERM_10", is_active=True)
        admin = UserFactory(username="admin_term_10")
        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="warning",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            status="pending_approval",
        )

        discipline_record_approve(user=admin, discipline_id=str(discipline.id))

        discipline.refresh_from_db()
        contract.refresh_from_db()
        employee.refresh_from_db()
        user.refresh_from_db()

        assert discipline.status == "approved"
        assert contract.status == "active"
        assert employee.employment_status == "active"
        assert user.is_active is True

    def test_discipline_approve_termination_creates_system_logs(self):
        employee = EmployeeFactory(
            employee_id="EMP_TERM_11", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-TERM-11", status="active")
        user = UserFactory(username="term_user_11", employee_id="EMP_TERM_11", is_active=True)
        admin = UserFactory(username="admin_term_11")
        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            status="pending_approval",
        )

        discipline_record_approve(user=admin, discipline_id=str(discipline.id))

        assert SystemLog.objects.filter(
            table_name="discipline_record", record_id=str(discipline.id), action="approve"
        ).exists()
        assert SystemLog.objects.filter(
            table_name="discipline_record", record_id=str(discipline.id), action="terminated_by_discipline"
        ).exists()
        assert SystemLog.objects.filter(
            table_name="employment_contract", record_id=str(contract.id), action="update"
        ).exists()
        assert SystemLog.objects.filter(table_name="employee", record_id=str(employee.id), action="update").exists()
        assert SystemLog.objects.filter(table_name="user", record_id=str(user.id), action="delete").exists()

    def test_discipline_approve_termination_transaction_atomic(self):
        employee = EmployeeFactory(
            employee_id="EMP_TERM_12", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-TERM-12", status="active")
        admin = UserFactory(username="admin_term_12")

        from apps.finance.models import SalarySlip

        SalarySlipFactory(employee=employee, salary_period="2026-05", status="draft")

        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            status="pending_approval",
        )

        initial_logs_count = SystemLog.objects.count()

        with pytest.raises(ValidationException):
            discipline_record_approve(user=admin, discipline_id=str(discipline.id))

        assert SystemLog.objects.count() == initial_logs_count
        discipline.refresh_from_db()
        assert discipline.status == "pending_approval"
