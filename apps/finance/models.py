from django.db import models

from apps.common.models import BaseModel
from apps.master_data.models import Employee, Item


class SalarySlip(BaseModel):
    """
    Salary slip for employees.
    """

    name = models.CharField(max_length=255, unique=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="salary_slips")
    salary_period = models.CharField(max_length=10)  # Format: YYYY-MM
    base_salary = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    overtime_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    allowance_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    reward_amount_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discipline_deduction_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    union_fee_2pct = models.DecimalField(max_digits=15, decimal_places=2, default=0, null=True, blank=True)
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
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("paid", "Paid"),
        ],
        default="draft",
    )
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "salary_slip"
        verbose_name = "Salary Slip"
        verbose_name_plural = "Salary Slips"

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


class TechnicalCertification(BaseModel):
    """
    Technical certification for items.
    """

    cert_id = models.CharField(max_length=100, unique=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="certifications")
    cert_type = models.CharField(max_length=100)
    assessment_fee = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    issue_date = models.DateField(auto_now_add=True)
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "technical_certification"
        verbose_name = "Technical Certification"
        verbose_name_plural = "Technical Certifications"

    def __str__(self):
        return f"{self.cert_id} - {self.item.item_code}"


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

    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateField()
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "cash_flow_transaction"
        verbose_name = "Cash Flow Transaction"
        verbose_name_plural = "Cash Flow Transactions"

    def __str__(self):
        return self.name
