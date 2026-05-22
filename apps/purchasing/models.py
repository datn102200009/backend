from django.db import models

from apps.common.models import BaseModel
from apps.master_data.models import Item
from apps.procurement.models import Supplier


class PurchaseOrder(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Nháp"
        PENDING = "pending", "Chờ xử lý"
        PAID_UNSHIPPED = "paid_unshipped", "Đã thanh toán, chưa nhận hàng"
        SHIPPED_UNPAID = "shipped_unpaid", "Đã nhận hàng, chưa thanh toán"
        COMPLETED = "completed", "Hoàn tất"
        CANCELLED = "cancelled", "Đã hủy"

    vendor = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="purchase_orders", verbose_name="Nhà cung cấp"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, verbose_name="Trạng thái")
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Tổng tiền")
    advance_paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Đã ứng trước")

    class Meta:
        db_table = "purchase_order"
        verbose_name = "Purchase Order"
        verbose_name_plural = "Purchase Orders"

    def __str__(self):
        return f"Purchase Order {self.id} - {self.get_status_display()}"


class PurchaseOrderLine(BaseModel):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines", verbose_name="Đơn hàng")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, verbose_name="Sản phẩm")
    quantity = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Số lượng")
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Đơn giá")
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Thành tiền")

    class Meta:
        db_table = "purchase_order_line"
        verbose_name = "Purchase Order Line"
        verbose_name_plural = "Purchase Order Lines"

    def __str__(self):
        return f"{self.order.id} - {self.item.item_name}"


class PurchaseInvoice(BaseModel):
    class Status(models.TextChoices):
        UNPAID = "unpaid", "Chưa thanh toán"
        PARTIAL = "partial", "Thanh toán một phần"
        PAID = "paid", "Đã thanh toán"
        CANCELLED = "cancelled", "Đã hủy"

    order = models.ForeignKey(
        PurchaseOrder,
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
        related_name="purchase_invoices",
        verbose_name="Phiếu nhập kho",
    )
    vendor = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="purchase_invoices", verbose_name="Nhà cung cấp"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID, verbose_name="Trạng thái")
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Tổng tiền")
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Đã thanh toán")

    class Meta:
        db_table = "purchase_invoice"
        verbose_name = "Purchase Invoice"
        verbose_name_plural = "Purchase Invoices"

    def __str__(self):
        return f"Purchase Invoice {self.id} - {self.get_status_display()}"


class PurchaseInvoiceLine(BaseModel):
    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name="lines", verbose_name="Hóa đơn")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, verbose_name="Sản phẩm")
    quantity = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Số lượng")
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Đơn giá")
    import_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Thuế nhập khẩu")
    vat_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Thuế VAT")
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Thành tiền")

    class Meta:
        db_table = "purchase_invoice_line"
        verbose_name = "Purchase Invoice Line"
        verbose_name_plural = "Purchase Invoice Lines"

    def __str__(self):
        return f"{self.invoice.id} - {self.item.item_name}"
