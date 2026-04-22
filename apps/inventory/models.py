from django.db import models

from apps.common.models import BaseModel
from apps.master_data.models import Item, Warehouse


class StockEntry(BaseModel):
    """
    Stock entry for inventory movements.
    """

    name = models.CharField(max_length=255, unique=True)
    purpose = models.CharField(
        max_length=50,
        choices=[
            ("receipt", "Receipt"),
            ("issue", "Issue"),
            ("transfer", "Transfer"),
            ("manufacture", "Manufacture"),
            ("adjustment", "Adjustment"),
        ],
    )
    posting_date = models.DateTimeField()
    remarks = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("posted", "Posted"),
        ],
        default="draft",
    )

    class Meta:
        db_table = "stock_entry"
        verbose_name = "Stock Entry"
        verbose_name_plural = "Stock Entries"

    def __str__(self):
        return f"{self.name} - {self.purpose}"


class StockEntryDetail(BaseModel):
    """
    Details of items in a stock entry.
    """

    parent = models.ForeignKey(StockEntry, on_delete=models.CASCADE, related_name="details")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=15, decimal_places=2)
    source_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_entries_from",
    )
    target_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_entries_to",
    )

    class Meta:
        db_table = "stock_entry_detail"
        verbose_name = "Stock Entry Detail"
        verbose_name_plural = "Stock Entry Details"

    def __str__(self):
        return f"{self.parent.name} - {self.item.item_code}"


class StockLedger(BaseModel):
    """
    Stock ledger for tracking inventory changes.
    """

    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    posting_date = models.DateTimeField()
    actual_quantity = models.DecimalField(max_digits=15, decimal_places=2)
    voucher_number = models.CharField(max_length=100, null=True, blank=True)
    voucher_type = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "stock_ledger"
        verbose_name = "Stock Ledger"
        verbose_name_plural = "Stock Ledgers"
        indexes = [
            models.Index(fields=["item", "warehouse", "posting_date"]),
        ]

    def __str__(self):
        return f"{self.item.item_code} at {self.warehouse.name}"
