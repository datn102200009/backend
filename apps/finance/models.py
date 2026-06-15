from django.db import models

from apps.common.models import BaseModel
from apps.master_data.models import Employee, Item


class SalarySlip(BaseModel):
    """
    Salary slip for employees.
    """

    name = models.CharField(max_length=255, unique=True)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="salary_slips")
    salary_period = models.CharField(max_length=10, db_index=True)  # Format: YYYY-MM
    base_salary = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    overtime_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    allowance_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    reward_amount_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discipline_deduction_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    gross_pay = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_method = models.CharField(
        max_length=50,
        choices=[("cash", "Cash"), ("bank_transfer", "Bank Transfer")],
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=30,
        choices=[
            ("draft", "Draft"),
            ("calculated", "Calculated"),
            ("submitted", "Submitted"),
            ("pending_finance_review", "Pending Finance Review"),
            ("approved", "Approved"),
            ("paid", "Paid"),
        ],
        default="draft",
    )
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_salary_slips",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    breakdown = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "salary_slip"
        verbose_name = "Salary Slip"
        verbose_name_plural = "Salary Slips"
        constraints = [
            models.UniqueConstraint(fields=["employee", "salary_period"], name="unique_salary_slip_per_period")
        ]

    def __str__(self):
        return self.name


class TaxReport(BaseModel):
    """
    Tax report tracking.
    """

    report_id = models.CharField(max_length=100, unique=True)
    tax_type = models.CharField(
        max_length=50,
        choices=[
            ("vat", "VAT"),
            ("income_tax", "Income Tax"),
            ("corporate_tax", "Corporate Tax"),
            ("other", "Other"),
        ],
    )
    period = models.CharField(max_length=10)  # Format: YYYY-MM or YYYY-Q1
    total_revenue = models.DecimalField(max_digits=18, decimal_places=2)
    tax_payable_amount = models.DecimalField(max_digits=18, decimal_places=2)
    tax_paid_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    due_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "tax_report"
        verbose_name = "Tax Report"
        verbose_name_plural = "Tax Reports"
        unique_together = ("tax_type", "period")

    def __str__(self):
        return f"{self.tax_type} - {self.period}"


class EnvironmentFeeLog(BaseModel):
    """
    Environmental fee tracking.
    """

    waste_water_volume = models.DecimalField(max_digits=15, decimal_places=2)
    gas_emission_fee_fixed = models.DecimalField(max_digits=15, decimal_places=2)
    variable_fee = models.DecimalField(max_digits=15, decimal_places=2)
    period = models.CharField(max_length=10)  # Format: YYYY-MM
    total_fee = models.DecimalField(max_digits=15, decimal_places=2)
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "environment_fee_log"
        verbose_name = "Environment Fee Log"
        verbose_name_plural = "Environment Fee Logs"
        unique_together = ("period",)

    def __str__(self):
        return f"Environment Fee - {self.period}"


class CashFlowTransaction(BaseModel):
    """
    Cash flow transaction for tracking receipts and payments.
    """

    name = models.CharField(max_length=255, unique=True)
    payment_type = models.CharField(max_length=50, choices=[("receive", "Receive Money"), ("pay", "Pay Money")])
    category = models.CharField(max_length=100, blank=True, null=True, verbose_name="Loại Thu/Chi")
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ("cash", "Cash"),
            ("bank_transfer", "Bank Transfer"),
            ("credit_card", "Credit Card"),
            ("other", "Other"),
        ],
        default="bank_transfer",
        db_index=True,
    )
    # References to Orders (for advance payment/deposits)
    purchase_order = models.ForeignKey(
        "purchasing.PurchaseOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="cash_flows"
    )
    sales_order = models.ForeignKey(
        "sales.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="cash_flows"
    )
    # References to Invoices (for clearing debts)
    purchase_invoice = models.ForeignKey(
        "purchasing.PurchaseInvoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="cash_flows"
    )
    sales_invoice = models.ForeignKey(
        "sales.SalesInvoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="cash_flows"
    )
    fixed_asset = models.ForeignKey(
        "FixedAsset", on_delete=models.SET_NULL, null=True, blank=True, related_name="cash_flows"
    )

    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateField()
    remarks = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("pending_approval", "Pending Approval"),
            ("posted", "Posted"),
            ("rejected", "Rejected"),
        ],
        default="pending_approval",
        db_index=True,
    )
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_cash_flows",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "cash_flow_transaction"
        verbose_name = "Cash Flow Transaction"
        verbose_name_plural = "Cash Flow Transactions"
        indexes = [
            models.Index(fields=["payment_type", "payment_date"]),
            models.Index(fields=["status", "payment_date"]),
            models.Index(fields=["purchase_order", "status"]),
            models.Index(fields=["sales_order", "status"]),
        ]

    def __str__(self):
        return self.name


class FixedAsset(BaseModel):
    """
    Fixed Asset model representing physical assets like machines and molds.
    """

    asset_code = models.CharField(max_length=100, unique=True)
    asset_name = models.CharField(max_length=255)
    original_value = models.DecimalField(max_digits=15, decimal_places=2)
    salvage_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    depreciation_method = models.CharField(
        max_length=50,
        choices=[
            ("straight_line", "Đường thẳng"),
            ("unit_of_production", "Sản lượng"),
        ],
    )
    useful_life_months = models.IntegerField(null=True, blank=True)
    remaining_life_months = models.IntegerField(null=True, blank=True)
    designed_capacity = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    accumulated_depreciation = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending_receive", "Chờ duyệt mua"),
            ("idle", "Đang nhàn rỗi"),
            ("active", "Đang sử dụng"),
            ("pending_dispose", "Chờ duyệt thanh lý"),
            ("disposed", "Đã thanh lý"),
        ],
        default="pending_receive",
        db_index=True,
    )
    purchase_date = models.DateField(null=True, blank=True)
    disposal_date = models.DateField(null=True, blank=True)
    disposal_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    vendor_name = models.CharField(max_length=255, null=True, blank=True)
    payment_method = models.CharField(
        max_length=50,
        choices=[("cash", "Tiền mặt"), ("bank_transfer", "Chuyển khoản")],
        default="bank_transfer",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "fixed_asset"
        verbose_name = "Fixed Asset"
        verbose_name_plural = "Fixed Assets"
        indexes = [
            models.Index(fields=["status", "-updated_at"], name="fa_status_updated_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(depreciation_method="straight_line", useful_life_months__isnull=False)
                    | models.Q(depreciation_method="unit_of_production", useful_life_months__isnull=True)
                ),
                name="check_fixed_asset_useful_life_by_method",
            )
        ]

    def __str__(self):
        return f"{self.asset_code} - {self.asset_name}"


class FixedAssetDepreciationLog(BaseModel):
    """
    Depreciation log tracking monthly depreciation runs for fixed assets.
    """

    asset = models.ForeignKey(FixedAsset, on_delete=models.CASCADE, related_name="depreciation_logs")
    period = models.CharField(max_length=7, db_index=True)  # Format: YYYY-MM
    depreciation_amount = models.DecimalField(max_digits=15, decimal_places=2)
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "fixed_asset_depreciation_log"
        verbose_name = "Fixed Asset Depreciation Log"
        verbose_name_plural = "Fixed Asset Depreciation Logs"
        unique_together = ("asset", "period")

    def __str__(self):
        return f"{self.asset.asset_code} - {self.period} - {self.depreciation_amount}"
