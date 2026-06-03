from django.db import models

from apps.common.models import BaseModel
from apps.crm.models import Customer
from apps.master_data.models import Item


class SalesOrder(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Nháp"
        PENDING = "pending", "Chờ xử lý"
        PENDING_CREDIT_APPROVAL = "pending_credit_approval", "Chờ duyệt tín dụng"
        PAID_UNSHIPPED = "paid_unshipped", "Đã nhận tiền, chưa giao hàng"
        SHIPPED_UNPAID = "shipped_unpaid", "Đã giao hàng, chưa thanh toán"
        COMPLETED = "completed", "Hoàn tất"
        CANCELLED = "cancelled", "Đã hủy"

    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="sales_orders", verbose_name="Khách hàng"
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, verbose_name="Trạng thái")
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Tổng tiền")
    advance_paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Đã ứng trước")

    class Meta:
        db_table = "sales_order"
        verbose_name = "Sales Order"
        verbose_name_plural = "Sales Orders"

    def __str__(self):
        return f"Sales Order {self.id} - {self.get_status_display()}"


class SalesOrderLine(BaseModel):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines", verbose_name="Đơn hàng")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, verbose_name="Sản phẩm")
    quantity = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Số lượng")
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Đơn giá")
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Thành tiền")

    class Meta:
        db_table = "sales_order_line"
        verbose_name = "Sales Order Line"
        verbose_name_plural = "Sales Order Lines"

    def __str__(self):
        return f"{self.order.id} - {self.item.item_name}"


class SalesInvoice(BaseModel):
    class Status(models.TextChoices):
        UNPAID = "unpaid", "Chưa thanh toán"
        PARTIAL = "partial", "Thanh toán một phần"
        PAID = "paid", "Đã thanh toán"
        CANCELLED = "cancelled", "Đã hủy"

    order = models.ForeignKey(
        SalesOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name="Đơn hàng gốc",
    )
    stock_entry = models.ForeignKey(
        "inventory.StockEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_invoices",
        verbose_name="Phiếu xuất kho",
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="sales_invoices", verbose_name="Khách hàng"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UNPAID, db_index=True, verbose_name="Trạng thái"
    )
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Tổng tiền")
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Đã thanh toán")

    class Meta:
        db_table = "sales_invoice"
        verbose_name = "Sales Invoice"
        verbose_name_plural = "Sales Invoices"

    def __str__(self):
        return f"Sales Invoice {self.id} - {self.get_status_display()}"


class SalesInvoiceLine(BaseModel):
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="lines", verbose_name="Hóa đơn")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, verbose_name="Sản phẩm")
    quantity = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Số lượng")
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Đơn giá")
    vat_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Thuế VAT")
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Thành tiền")

    class Meta:
        db_table = "sales_invoice_line"
        verbose_name = "Sales Invoice Line"
        verbose_name_plural = "Sales Invoice Lines"

    def __str__(self):
        return f"{self.invoice.id} - {self.item.item_name}"
