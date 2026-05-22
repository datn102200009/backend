from django.db import models

from apps.accounts.models import User
from apps.common.models import BaseModel
from apps.master_data.models import Employee


class Attendance(BaseModel):
    """
    Employee attendance record.
    """

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendances")
    date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("present", "Present"),
            ("absent", "Absent"),
            ("late", "Late"),
            ("leave", "Leave"),
            ("holiday", "Holiday"),
        ],
    )
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "attendance"
        verbose_name = "Attendance"
        verbose_name_plural = "Attendances"
        unique_together = ("employee", "date")
        indexes = [models.Index(fields=["employee", "date"])]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.date}"


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

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="contracts")
    contract_no = models.CharField(max_length=100, unique=True)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    note = models.TextField(null=True, blank=True)
    file_url = models.CharField(max_length=255, null=True, blank=True)

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

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="documents")
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


class EmploymentHistory(BaseModel):
    """
    Ghi vết tất cả những thay đổi quan trọng về chức vụ, bộ phận hoặc lương cơ bản của nhân viên.
    """

    CHANGE_TYPES = [
        ("salary_change", "Thay đổi lương"),
        ("title_change", "Thay đổi chức danh"),
        ("department_transfer", "Điều chuyển phòng ban"),
        ("other", "Khác"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="employment_histories")
    change_type = models.CharField(max_length=50, choices=CHANGE_TYPES)
    old_salary_base = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    new_salary_base = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    old_title = models.CharField(max_length=100, null=True, blank=True)
    new_title = models.CharField(max_length=100, null=True, blank=True)
    old_department = models.CharField(max_length=100, null=True, blank=True)
    new_department = models.CharField(max_length=100, null=True, blank=True)
    effective_date = models.DateField()
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="approved_histories", null=True, blank=True
    )
    reason = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "employment_history"
        verbose_name = "Employment History"
        verbose_name_plural = "Employment Histories"
        ordering = ["-effective_date", "-created_at"]

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_change_type_display()} ({self.effective_date})"
