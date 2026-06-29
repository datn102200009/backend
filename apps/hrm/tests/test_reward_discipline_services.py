from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import SystemLog
from apps.common.xlib.exceptions import ValidationException
from apps.hrm.models import DisciplineRecord, RewardRecord
from apps.hrm.services import (
    discipline_record_approve,
    discipline_record_cancel,
    discipline_record_create,
    discipline_record_delete,
    discipline_record_update,
    reward_record_approve,
    reward_record_cancel,
    reward_record_create,
    reward_record_delete,
    reward_record_update,
)
from apps.hrm.tests.factories import DisciplineRecordFactory, EmployeeFactory, RewardRecordFactory, SalarySlipFactory
from apps.inventory.tests.factories import UserFactory


@pytest.mark.django_db
class TestRewardDisciplineServices:

    def test_reward_record_create(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP7001")
        admin = UserFactory(username="admin_reward")
        data = {
            "reward_date": date(2026, 5, 15),
            "reward_type": "performance_bonus",
            "amount": Decimal("1500000.00"),
            "description": "Thành tích xuất sắc trong dự án",
        }

        # Act
        reward = reward_record_create(employee_id=employee.id, data=data, creator=admin)

        # Assert
        assert reward is not None
        assert reward.employee == employee
        assert reward.amount == Decimal("1500000.00")
        assert reward.reward_type == "performance_bonus"

        # Verify log
        log = SystemLog.objects.filter(table_name="reward_record", record_id=str(reward.id), user=admin).first()
        assert log is not None
        assert log.action == "create"
        assert Decimal(str(log.new_value["amount"])) == Decimal("1500000.00")

    def test_discipline_record_create(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP7002")
        admin = UserFactory(username="admin_discipline")
        data = {
            "incident_date": date(2026, 5, 10),
            "discipline_date": date(2026, 5, 12),
            "discipline_type": "salary_deduction",
            "penalty_amount": Decimal("500000.00"),
            "description": "Vi phạm quy chế bảo mật thông tin",
            "file_url": "https://example.com/scan_incident.pdf",
        }

        # Act
        discipline = discipline_record_create(employee_id=employee.id, data=data, creator=admin)

        # Assert
        assert discipline is not None
        assert discipline.employee == employee
        assert discipline.penalty_amount == Decimal("500000.00")
        assert discipline.file_url == "https://example.com/scan_incident.pdf"

        # Verify log
        log = SystemLog.objects.filter(table_name="discipline_record", record_id=str(discipline.id), user=admin).first()
        assert log is not None
        assert log.action == "create"

    def test_reward_record_create_blocked_when_period_paid(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_pr_t4_1")
        SalarySlipFactory(employee=employee, salary_period="2026-06", status="paid")

        data = {
            "reward_date": date(2026, 6, 15),
            "reward_type": "bonus",
            "amount": 1000000,
            "description": "Excellence award",
        }
        with pytest.raises(ValidationException, match="Kỳ lương 2026-06 đã được thanh toán 100%"):
            reward_record_create(employee_id=str(employee.id), data=data, creator=admin)

    def test_discipline_record_create_blocked_when_period_paid(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_pr_t4_2")
        SalarySlipFactory(employee=employee, salary_period="2026-06", status="paid")

        data = {
            "incident_date": date(2026, 6, 10),
            "discipline_date": date(2026, 6, 12),
            "discipline_type": "warning",
            "penalty_amount": 500000,
            "description": "Late arrival",
        }
        with pytest.raises(ValidationException, match="Kỳ lương 2026-06 đã được thanh toán 100%"):
            discipline_record_create(employee_id=str(employee.id), data=data, creator=admin)

    def test_reward_record_approve_blocked_when_period_paid(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_pr_t4_3")
        reward = RewardRecordFactory(employee=employee, reward_date=date(2026, 6, 15), status="pending_approval")
        SalarySlipFactory(employee=employee, salary_period="2026-06", status="paid")

        with pytest.raises(ValidationException, match="Kỳ lương 2026-06 đã được thanh toán 100%"):
            reward_record_approve(user=admin, reward_id=str(reward.id))

    def test_discipline_record_approve_blocked_when_period_paid(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_pr_t4_4")
        discipline = DisciplineRecordFactory(
            employee=employee,
            incident_date=date(2026, 6, 10),
            discipline_date=date(2026, 6, 12),
            status="pending_approval",
        )
        SalarySlipFactory(employee=employee, salary_period="2026-06", status="paid")

        with pytest.raises(ValidationException, match="Kỳ lương 2026-06 đã được thanh toán 100%"):
            discipline_record_approve(user=admin, discipline_id=str(discipline.id))


@pytest.mark.django_db
class TestRewardRecordCRUDServices:

    def test_reward_record_update_success_pending(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_crud_1")
        reward = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 10),
            reward_type="performance_bonus",
            amount=Decimal("1000000.00"),
            description="Old desc",
            status="pending_approval",
        )

        data = {
            "amount": Decimal("1500000.00"),
            "description": "New desc",
        }

        updated = reward_record_update(reward_id=str(reward.id), data=data, updater=admin)

        assert updated.amount == Decimal("1500000.00")
        assert updated.description == "New desc"
        assert updated.status == "pending_approval"

    def test_reward_record_update_blocked_when_approved(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_crud_2")
        reward = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 10),
            reward_type="performance_bonus",
            amount=Decimal("1000000.00"),
            description="Old desc",
            status="approved",
        )

        data = {"amount": Decimal("1500000.00")}

        with pytest.raises(ValidationException, match="Chỉ có thể sửa khen thưởng ở trạng thái chờ duyệt"):
            reward_record_update(reward_id=str(reward.id), data=data, updater=admin)

    def test_reward_record_cancel_success_pending(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_crud_3")
        reward = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 10),
            status="pending_approval",
        )

        cancelled = reward_record_cancel(reward_id=str(reward.id), user=admin, reason="No longer valid")

        assert cancelled.status == "cancelled"
        assert cancelled.cancelled_by == admin
        assert cancelled.cancelled_at is not None

    def test_reward_record_cancel_blocked_when_approved(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_crud_4")
        reward = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 10),
            status="approved",
        )

        with pytest.raises(ValidationException, match="Chỉ có thể hủy khen thưởng ở trạng thái chờ duyệt"):
            reward_record_cancel(reward_id=str(reward.id), user=admin)

    def test_reward_record_delete_success_pending(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_crud_5")
        reward = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 10),
            status="pending_approval",
        )

        reward_id = str(reward.id)
        reward_record_delete(reward_id=reward_id, deleter=admin)

        assert not RewardRecord.objects.filter(id=reward_id).exists()

    def test_reward_record_delete_blocked_when_approved(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_crud_6")
        reward = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 10),
            status="approved",
        )

        with pytest.raises(ValidationException, match="Chỉ có thể xóa khen thưởng ở trạng thái chờ duyệt"):
            reward_record_delete(reward_id=str(reward.id), deleter=admin)

    def test_reward_record_update_blocked_when_period_paid(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_crud_7")
        reward = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 10),
            status="pending_approval",
        )

        SalarySlipFactory(employee=employee, salary_period="2026-06", status="paid")

        with pytest.raises(ValidationException, match="Kỳ lương 2026-06 đã được thanh toán 100%"):
            reward_record_update(reward_id=str(reward.id), data={"amount": Decimal("2000000.00")}, updater=admin)


@pytest.mark.django_db
class TestDisciplineRecordCRUDServices:

    def test_discipline_record_update_success_pending(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_disc_1")
        discipline = DisciplineRecordFactory(
            employee=employee,
            incident_date=date(2026, 6, 10),
            discipline_date=date(2026, 6, 12),
            discipline_type="warning",
            penalty_amount=Decimal("500000.00"),
            description="Old violation",
            status="pending_approval",
        )

        data = {
            "penalty_amount": Decimal("600000.00"),
            "description": "New violation description",
        }

        updated = discipline_record_update(discipline_id=str(discipline.id), data=data, updater=admin)

        assert updated.penalty_amount == Decimal("600000.00")
        assert updated.description == "New violation description"
        assert updated.status == "pending_approval"

    def test_discipline_record_update_blocked_when_approved(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_disc_2")
        discipline = DisciplineRecordFactory(
            employee=employee,
            incident_date=date(2026, 6, 10),
            discipline_date=date(2026, 6, 12),
            status="approved",
        )

        data = {"penalty_amount": Decimal("600000.00")}

        with pytest.raises(ValidationException, match="Chỉ có thể sửa kỷ luật ở trạng thái chờ duyệt"):
            discipline_record_update(discipline_id=str(discipline.id), data=data, updater=admin)

    def test_discipline_record_cancel_success_pending(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_disc_3")
        discipline = DisciplineRecordFactory(
            employee=employee,
            incident_date=date(2026, 6, 10),
            discipline_date=date(2026, 6, 12),
            status="pending_approval",
        )

        cancelled = discipline_record_cancel(discipline_id=str(discipline.id), user=admin, reason="False alarm")

        assert cancelled.status == "cancelled"
        assert cancelled.cancelled_by == admin
        assert cancelled.cancelled_at is not None

    def test_discipline_record_cancel_blocked_when_approved(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_disc_4")
        discipline = DisciplineRecordFactory(
            employee=employee,
            incident_date=date(2026, 6, 10),
            discipline_date=date(2026, 6, 12),
            status="approved",
        )

        with pytest.raises(ValidationException, match="Chỉ có thể hủy kỷ luật ở trạng thái chờ duyệt"):
            discipline_record_cancel(discipline_id=str(discipline.id), user=admin)

    def test_discipline_record_delete_success_pending(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_disc_5")
        discipline = DisciplineRecordFactory(
            employee=employee,
            incident_date=date(2026, 6, 10),
            discipline_date=date(2026, 6, 12),
            status="pending_approval",
        )

        disc_id = str(discipline.id)
        discipline_record_delete(discipline_id=disc_id, deleter=admin)

        assert not DisciplineRecord.objects.filter(id=disc_id).exists()

    def test_discipline_record_delete_blocked_when_approved(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_disc_6")
        discipline = DisciplineRecordFactory(
            employee=employee,
            incident_date=date(2026, 6, 10),
            discipline_date=date(2026, 6, 12),
            status="approved",
        )

        with pytest.raises(ValidationException, match="Chỉ có thể xóa kỷ luật ở trạng thái chờ duyệt"):
            discipline_record_delete(discipline_id=str(discipline.id), deleter=admin)


@pytest.mark.django_db
class TestRewardDisciplineStandardizedLabels:

    def test_reward_type_choices_use_standard_labels(self):
        expected_choices = [
            ("performance_bonus", "Thưởng hiệu quả công việc"),
            ("initiative", "Thưởng sáng kiến"),
            ("holiday_bonus", "Thưởng lễ tết"),
            ("other", "Thưởng khác"),
        ]
        assert RewardRecord.REWARD_TYPES == expected_choices

    def test_discipline_type_choices_use_standard_labels(self):
        expected_choices = [
            ("reprimand", "Khiển trách"),
            ("warning", "Cảnh cáo"),
            ("salary_deduction", "Khấu trừ lương"),
            ("termination", "Sa thải"),
            ("other", "Khác"),
        ]
        assert DisciplineRecord.DISCIPLINE_TYPES == expected_choices

    def test_serializer_create_input_uses_standard_labels(self):
        from apps.hrm.api.v1.serializers import RewardRecordCreateInputSerializer

        serializer = RewardRecordCreateInputSerializer()
        choices = serializer.fields["reward_type"].choices
        assert choices["initiative"] == "Thưởng sáng kiến"
        assert choices["other"] == "Thưởng khác"

    def test_serializer_create_input_discipline_uses_standard_labels(self):
        from apps.hrm.api.v1.serializers import DisciplineRecordCreateInputSerializer

        serializer = DisciplineRecordCreateInputSerializer()
        choices = serializer.fields["discipline_type"].choices
        assert choices["warning"] == "Cảnh cáo"
        assert choices["reprimand"] == "Khiển trách"
