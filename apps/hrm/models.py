from django.db import models

from apps.common.models import BaseModel
from apps.master_data.models import Employee


class Attendance(BaseModel):
    """
    Employee attendance record.
    """

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="attendances"
    )
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

