"""
Serializers for hrm API v1.

Handles validation and transformation of data.
"""

import re

from rest_framework import serializers

from apps.finance.models import SalarySlip
from apps.hrm.models import (
    Attendance,
    DisciplineRecord,
    EmployeeDocument,
    EmploymentContract,
    EmploymentHistory,
    LeaveRequest,
    RewardRecord,
)
from apps.master_data.models import Employee

# =============================================================================
# OUTPUT SERIALIZERS
# =============================================================================


class EmployeeDocumentOutputSerializer(serializers.ModelSerializer):
    """
    Serializer for EmployeeDocument output.
    """

    uploaded_by_username = serializers.CharField(source="uploaded_by.username", read_only=True)

    class Meta:
        model = EmployeeDocument
        fields = [
            "id",
            "doc_type",
            "title",
            "file_url",
            "uploaded_by_id",
            "uploaded_by_username",
            "created_at",
            "updated_at",
        ]


class EmploymentContractOutputSerializer(serializers.ModelSerializer):
    """
    Serializer for EmploymentContract output.
    """

    class Meta:
        model = EmploymentContract
        fields = [
            "id",
            "contract_no",
            "contract_type",
            "start_date",
            "end_date",
            "status",
            "note",
            "file_url",
            "created_at",
            "updated_at",
        ]


class EmploymentHistoryOutputSerializer(serializers.ModelSerializer):
    """
    Serializer for EmploymentHistory output.
    """

    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True)

    class Meta:
        model = EmploymentHistory
        fields = [
            "id",
            "change_type",
            "old_salary_base",
            "new_salary_base",
            "old_title",
            "new_title",
            "old_department",
            "new_department",
            "effective_date",
            "approved_by_id",
            "approved_by_username",
            "reason",
            "created_at",
        ]


class RewardRecordOutputSerializer(serializers.ModelSerializer):
    """
    Serializer for RewardRecord output.
    """

    class Meta:
        model = RewardRecord
        fields = [
            "id",
            "reward_date",
            "reward_type",
            "amount",
            "description",
            "salary_slip_id",
            "created_at",
        ]


class DisciplineRecordOutputSerializer(serializers.ModelSerializer):
    """
    Serializer for DisciplineRecord output.
    """

    class Meta:
        model = DisciplineRecord
        fields = [
            "id",
            "incident_date",
            "discipline_date",
            "discipline_type",
            "description",
            "penalty_amount",
            "salary_slip_id",
            "file_url",
            "created_at",
        ]


class EmployeeOutputSerializer(serializers.ModelSerializer):
    """
    Serializer for Employee basic output.
    """

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_id",
            "full_name",
            "department",
            "position_title",
            "salary_base",
            "is_union_member",
            "email",
            "phone",
            "gender",
            "date_of_birth",
            "address",
            "emergency_contact",
            "join_date",
            "leave_date",
            "employment_status",
            "created_at",
            "updated_at",
        ]


class EmployeeDetailOutputSerializer(EmployeeOutputSerializer):
    """
    Serializer for detailed Employee output including all relations.
    """

    contracts = EmploymentContractOutputSerializer(many=True, read_only=True)
    employment_histories = EmploymentHistoryOutputSerializer(many=True, read_only=True)
    documents = EmployeeDocumentOutputSerializer(many=True, read_only=True)
    rewards = RewardRecordOutputSerializer(many=True, read_only=True)
    disciplines = DisciplineRecordOutputSerializer(many=True, read_only=True)

    class Meta(EmployeeOutputSerializer.Meta):
        fields = EmployeeOutputSerializer.Meta.fields + [
            "contracts",
            "employment_histories",
            "documents",
            "rewards",
            "disciplines",
        ]


class AttendanceOutputSerializer(serializers.ModelSerializer):
    """
    Serializer for Attendance output.
    """

    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "employee_id",
            "employee_code",
            "employee_name",
            "date",
            "status",
            "work_hours",
            "overtime_hours",
            "remarks",
            "created_at",
            "updated_at",
        ]


class LeaveRequestOutputSerializer(serializers.ModelSerializer):
    """
    Serializer for LeaveRequest output.
    """

    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee_id",
            "employee_code",
            "employee_name",
            "leave_type",
            "start_date",
            "end_date",
            "days",
            "reason",
            "status",
            "approved_by_id",
            "approved_by_username",
            "approved_at",
            "created_at",
            "updated_at",
        ]


class SalarySlipOutputSerializer(serializers.ModelSerializer):
    """
    Serializer for SalarySlip output.
    """

    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = SalarySlip
        fields = [
            "id",
            "name",
            "employee_id",
            "employee_code",
            "employee_name",
            "salary_period",
            "base_salary",
            "overtime_amount",
            "allowance_amount",
            "reward_amount_total",
            "discipline_deduction_total",
            "union_fee_2pct",
            "gross_pay",
            "deductions",
            "net_pay",
            "payment_method",
            "status",
            "remarks",
            "created_at",
            "updated_at",
        ]


# =============================================================================
# INPUT SERIALIZERS
# =============================================================================


class EmployeeCreateInputSerializer(serializers.Serializer):
    """
    Serializer for validating employee creation input.
    """

    employee_id = serializers.CharField(max_length=50)
    full_name = serializers.CharField(max_length=255)
    department = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    position_title = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    salary_base = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    is_union_member = serializers.BooleanField(default=False)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)
    gender = serializers.ChoiceField(
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")], required=False, allow_null=True
    )
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    emergency_contact = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    join_date = serializers.DateField(required=False, allow_null=True)
    leave_date = serializers.DateField(required=False, allow_null=True)
    employment_status = serializers.ChoiceField(
        choices=[("active", "Active"), ("inactive", "Inactive")], default="active"
    )

    # User accounts fields
    create_user = serializers.BooleanField(default=False)
    username = serializers.CharField(max_length=150, required=False)
    password = serializers.CharField(max_length=128, required=False)
    role_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs.get("create_user"):
            if not attrs.get("username") or not attrs.get("password"):
                raise serializers.ValidationError(
                    {"username": "Username và password là bắt buộc khi create_user là True."}
                )
        return attrs


class EmployeeUpdateInputSerializer(serializers.Serializer):
    """
    Serializer for validating employee update input.
    """

    full_name = serializers.CharField(max_length=255, required=False)
    department = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    position_title = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    salary_base = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    is_union_member = serializers.BooleanField(required=False)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)
    gender = serializers.ChoiceField(
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")], required=False, allow_null=True
    )
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    emergency_contact = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    join_date = serializers.DateField(required=False, allow_null=True)
    leave_date = serializers.DateField(required=False, allow_null=True)
    employment_status = serializers.ChoiceField(
        choices=[("active", "Active"), ("inactive", "Inactive")], required=False
    )


class EmployeeUpdateSalaryTitleInputSerializer(serializers.Serializer):
    """
    Serializer for validating salary/title change input.
    """

    change_type = serializers.ChoiceField(
        choices=[
            ("salary_change", "Thay đổi lương"),
            ("title_change", "Thay đổi chức danh"),
            ("department_transfer", "Điều chuyển phòng ban"),
            ("other", "Khác"),
        ]
    )
    new_salary_base = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    new_title = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    new_department = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    effective_date = serializers.DateField()
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class ContractCreateOrRenewInputSerializer(serializers.Serializer):
    """
    Serializer for validating contract creation or renewal input.
    """

    employee_id = serializers.UUIDField()
    contract_no = serializers.CharField(max_length=100)
    contract_type = serializers.ChoiceField(
        choices=[
            ("probation", "Thử việc"),
            ("definite_term", "Xác định thời hạn"),
            ("indefinite_term", "Không xác định thời hạn"),
            ("other", "Khác"),
        ]
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    file_url = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)


class ContractTerminateInputSerializer(serializers.Serializer):
    """
    Serializer for validating contract termination input.
    """

    termination_date = serializers.DateField()
    reason = serializers.CharField()
    file_url = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)


class AttendanceRecordInputSerializer(serializers.Serializer):
    """
    Serializer for nested attendance items in batch operation.
    """

    employee_id = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=[
            ("working", "Đi làm"),
            ("paid_leave", "Nghỉ phép có lương"),
            ("unpaid_leave", "Nghỉ không lương"),
            ("sick_leave", "Nghỉ ốm"),
            ("holiday", "Nghỉ lễ"),
            ("other", "Khác"),
        ]
    )
    work_hours = serializers.DecimalField(max_digits=4, decimal_places=2, default=8.00)
    overtime_hours = serializers.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    remarks = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class AttendanceBatchInputSerializer(serializers.Serializer):
    """
    Serializer for validating batch attendance input.
    """

    date = serializers.DateField()
    records = AttendanceRecordInputSerializer(many=True)


class LeaveRequestCreateInputSerializer(serializers.Serializer):
    """
    Serializer for validating leave request creation input.
    """

    employee_id = serializers.UUIDField()
    leave_type = serializers.ChoiceField(
        choices=[
            ("annual", "Nghỉ phép năm"),
            ("sick", "Nghỉ ốm"),
            ("unpaid", "Nghỉ không lương"),
            ("maternity", "Nghỉ thai sản"),
            ("personal", "Nghỉ việc riêng"),
            ("other", "Khác"),
        ]
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    days = serializers.DecimalField(max_digits=4, decimal_places=1)
    reason = serializers.CharField()


class LeaveRequestApproveInputSerializer(serializers.Serializer):
    """
    Serializer for validating leave request approval/rejection decision.
    """

    action = serializers.ChoiceField(choices=[("approve", "Approve"), ("reject", "Reject")])


class SalarySlipInitializeInputSerializer(serializers.Serializer):
    """
    Serializer for validating salary slip initialization.
    """

    salary_period = serializers.CharField(max_length=10)

    def validate_salary_period(self, value):
        if not re.match(r"^\d{4}-\d{2}$", value):
            raise serializers.ValidationError("Kỳ lương phải ở định dạng YYYY-MM.")
        return value


class SalarySlipConfirmInputSerializer(serializers.Serializer):
    """
    Serializer for validating salary slip confirmation.
    """

    payment_method = serializers.ChoiceField(choices=[("cash", "Cash"), ("bank_transfer", "Bank Transfer")])


class RewardRecordCreateInputSerializer(serializers.Serializer):
    """
    Serializer for validating reward record creation.
    """

    employee_id = serializers.UUIDField()
    reward_date = serializers.DateField()
    reward_type = serializers.ChoiceField(
        choices=[
            ("performance_bonus", "Thưởng hiệu quả công việc"),
            ("initiative", "Sáng kiến"),
            ("holiday_bonus", "Thưởng lễ tết"),
            ("other", "Khác"),
        ]
    )
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    description = serializers.CharField()
    salary_slip_id = serializers.UUIDField(required=False, allow_null=True)


class DisciplineRecordCreateInputSerializer(serializers.Serializer):
    """
    Serializer for validating discipline record creation.
    """

    employee_id = serializers.UUIDField()
    incident_date = serializers.DateField()
    discipline_date = serializers.DateField()
    discipline_type = serializers.ChoiceField(
        choices=[
            ("reprimand", "Khiển trách"),
            ("warning", "Cảnh cáo"),
            ("salary_deduction", "Khấu trừ lương"),
            ("termination", "Sa thải"),
            ("other", "Khác"),
        ]
    )
    description = serializers.CharField()
    penalty_amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    salary_slip_id = serializers.UUIDField(required=False, allow_null=True)
    file_url = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
