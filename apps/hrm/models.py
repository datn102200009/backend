from django.db import models

from apps.accounts.models import User
from apps.common.models import BaseModel
from apps.finance.models import SalarySlip
from apps.master_data.models import Employee


class Attendance(BaseModel):
    """
    Bản ghi chấm công của nhân viên.
    """

    STATUS_CHOICES = [
        ("working", "Đi làm"),
        ("paid_leave", "Nghỉ phép có lương"),
        ("unpaid_leave", "Nghỉ không lương"),
        ("holiday", "Nghỉ lễ"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="attendances")
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    work_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8.00)
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "attendance"
        verbose_name = "Attendance"
        verbose_name_plural = "Attendances"
        unique_together = (("employee", "date"),)
        ordering = ["-date"]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.date} ({self.get_status_display()})"


class LeaveRequest(BaseModel):
    """
    Quản lý đơn xin nghỉ phép của nhân viên.
    """

    LEAVE_TYPES = [
        ("paid", "Nghỉ có lương"),
        ("unpaid", "Nghỉ không lương"),
    ]

    STATUS_CHOICES = [
        ("pending", "Chờ duyệt"),
        ("approved", "Đã duyệt"),
        ("rejected", "Từ chối"),
        ("cancelled", "Đã hủy"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="leave_requests")
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.DecimalField(max_digits=4, decimal_places=1)
    reason = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="approved_leaves", null=True, blank=True
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "leave_request"
        verbose_name = "Leave Request"
        verbose_name_plural = "Leave Requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_leave_type_display()} ({self.start_date} -> {self.end_date})"


class EmploymentContract(BaseModel):
    """
    Hợp đồng lao động của nhân viên.
    """

    CONTRACT_TYPES = [
        ("probation", "Thử việc"),
        ("definite_term", "Xác định thời hạn"),
        ("indefinite_term", "Không xác định thời hạn"),
        ("other", "Khác"),
    ]

    STATUS_CHOICES = [
        ("draft", "Nháp"),
        ("active", "Đang hoạt động"),
        ("expired", "Hết hạn"),
        ("terminated", "Chấm dứt"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="contracts")
    contract_no = models.CharField(max_length=100, unique=True)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    note = models.TextField(null=True, blank=True)
    file_url = models.CharField(max_length=255, null=True, blank=True)
    salary_base = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "employment_contract"
        verbose_name = "Employment Contract"
        verbose_name_plural = "Employment Contracts"

    def __str__(self):
        return f"{self.contract_no} - {self.employee.full_name}"


class EmployeeDocument(BaseModel):
    """
    Tài liệu hồ sơ đính kèm của nhân viên.
    """

    DOC_TYPES = [
        ("contract_scan", "Scan hợp đồng"),
        ("id_copy", "Bản sao CCCD/CMND"),
        ("certification", "Bằng cấp/Chứng chỉ"),
        ("resignation_letter", "Đơn xin nghỉ việc"),
        ("disciplinary_minutes", "Biên bản kỷ luật"),
        ("medical_doc", "Giấy khám sức khỏe"),
        ("other", "Khác"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="documents")
    doc_type = models.CharField(max_length=50, choices=DOC_TYPES)
    title = models.CharField(max_length=255)
    file_url = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "employee_document"
        verbose_name = "Employee Document"
        verbose_name_plural = "Employee Documents"

    def __str__(self):
        return f"{self.title} ({self.get_doc_type_display()}) - {self.employee.full_name}"


class RewardRecord(BaseModel):
    """
    Khen thưởng nhân viên.
    """

    REWARD_TYPES = [
        ("performance_bonus", "Thưởng hiệu quả công việc"),
        ("initiative", "Thưởng sáng kiến"),
        ("holiday_bonus", "Thưởng lễ tết"),
        ("other", "Thưởng khác"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="rewards")
    reward_date = models.DateField()
    reward_type = models.CharField(max_length=50, choices=REWARD_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    description = models.TextField()
    salary_slip = models.ForeignKey(
        SalarySlip, on_delete=models.SET_NULL, null=True, blank=True, related_name="rewards"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        default="pending_approval",
        db_index=True,
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="approved_rewards", null=True, blank=True
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="cancelled_rewards", null=True, blank=True
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "reward_record"
        verbose_name = "Reward Record"
        verbose_name_plural = "Reward Records"
        ordering = ["-reward_date"]
        indexes = [
            models.Index(fields=["status", "reward_date"]),
        ]

    def __str__(self):
        return f"Reward {self.employee.full_name} - {self.get_reward_type_display()} ({self.reward_date})"


class DisciplineRecord(BaseModel):
    """
    Kỷ luật nhân viên.
    """

    DISCIPLINE_TYPES = [
        ("reprimand", "Khiển trách"),
        ("warning", "Cảnh cáo"),
        ("salary_deduction", "Khấu trừ lương"),
        ("termination", "Sa thải"),
        ("other", "Khác"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="disciplines")
    incident_date = models.DateField()
    discipline_date = models.DateField()
    discipline_type = models.CharField(max_length=50, choices=DISCIPLINE_TYPES)
    description = models.TextField()
    penalty_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    salary_slip = models.ForeignKey(
        SalarySlip, on_delete=models.SET_NULL, null=True, blank=True, related_name="disciplines"
    )
    file_url = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        default="pending_approval",
        db_index=True,
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="approved_disciplines", null=True, blank=True
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="cancelled_disciplines", null=True, blank=True
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "discipline_record"
        verbose_name = "Discipline Record"
        verbose_name_plural = "Discipline Records"
        ordering = ["-discipline_date"]
        indexes = [
            models.Index(fields=["status", "discipline_date"]),
        ]

    def __str__(self):
        return f"Discipline {self.employee.full_name} - {self.get_discipline_type_display()} ({self.discipline_date})"


class PublicHoliday(BaseModel):
    """
    Quản lý danh sách ngày nghỉ Lễ/Tết được cấu hình linh hoạt.
    """

    name = models.CharField(max_length=255)
    start_date = models.DateField(unique=True)
    days = models.IntegerField(default=1)
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "public_holiday"
        verbose_name = "Public Holiday"
        verbose_name_plural = "Public Holidays"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} ({self.start_date} +{self.days}d)"
