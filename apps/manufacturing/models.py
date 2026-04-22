from django.db import models

from apps.common.models import BaseModel
from apps.master_data.models import Item


class BOM(BaseModel):
    """
    Bill of Materials for manufacturing.
    """

    name = models.CharField(max_length=255, unique=True)
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="boms"
    )
    quantity = models.DecimalField(max_digits=15, decimal_places=2)
    is_active = models.BooleanField(default=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "bom"
        verbose_name = "Bill of Materials"
        verbose_name_plural = "Bills of Materials"

    def __str__(self):
        return self.name


class BOMItem(BaseModel):
    """
    Items that compose a BOM.
    """

    parent = models.ForeignKey(
        BOM, on_delete=models.CASCADE, related_name="items"
    )
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="bom_items"
    )
    quantity = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = "bom_item"
        verbose_name = "BOM Item"
        verbose_name_plural = "BOM Items"
        unique_together = ("parent", "item")

    def __str__(self):
        return f"{self.parent.name} - {self.item.item_code}"


class WorkOrder(BaseModel):
    """
    Manufacturing work order.
    """

    name = models.CharField(max_length=255, unique=True)
    bom = models.ForeignKey(
        BOM, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_orders"
    )
    production_item = models.ForeignKey(
        Item, on_delete=models.PROTECT, related_name="work_orders"
    )
    quantity = models.IntegerField()
    planned_start_date = models.DateField()
    planned_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("not_started", "Not Started"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("closed", "Closed"),
        ],
        default="draft",
    )
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "work_order"
        verbose_name = "Work Order"
        verbose_name_plural = "Work Orders"

    def __str__(self):
        return self.name
