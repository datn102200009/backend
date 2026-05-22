"""
Services for purchasing app.

All write operations for Purchase Orders and Purchase Invoices.
"""

from typing import Any, Dict, List

from django.db import transaction

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.inventory.services import stock_in_approve, stock_in_create
from apps.master_data.models import Item
from apps.procurement.models import Supplier
from apps.purchasing.models import PurchaseInvoice, PurchaseInvoiceLine, PurchaseOrder, PurchaseOrderLine


@transaction.atomic
def purchase_order_create(*, user: User, vendor_id: str, lines: List[Dict[str, Any]]) -> PurchaseOrder:
    """
    Khởi tạo Đơn mua hàng (Purchase Order).
    """
    PermissionChecker.check_permission(user, "purchasing.create_order")

    vendor = Supplier.objects.filter(id=vendor_id).first()
    if not vendor:
        raise NotFoundException(f"Nhà cung cấp với ID {vendor_id} không tồn tại.")

    order = PurchaseOrder.objects.create(vendor=vendor, status=PurchaseOrder.Status.DRAFT)

    total_amount = 0
    for line in lines:
        item = Item.objects.filter(id=line["item_id"]).first()
        if not item:
            raise NotFoundException(f"Sản phẩm với ID {line['item_id']} không tồn tại.")

        qty = line.get("quantity", 0)
        unit_price = line.get("unit_price", 0)
        line_total = qty * unit_price
        total_amount += line_total

        PurchaseOrderLine.objects.create(
            order=order, item=item, quantity=qty, unit_price=unit_price, line_total=line_total
        )

    order.total_amount = total_amount
    order.save()

    create_system_log(
        user=user,
        action="create",
        table_name="purchase_order",
        record_id=str(order.id),
        new_value={"status": order.status, "total": str(total_amount)},
    )

    return order


@transaction.atomic
def purchase_order_update(
    *, user: User, order_id: str, vendor_id: str, status: str, lines: List[Dict[str, Any]]
) -> PurchaseOrder:
    """
    Cập nhật Đơn mua hàng. Chỉ cho phép khi ở trạng thái Draft.
    """
    PermissionChecker.check_permission(user, "purchasing.update_order")

    order = PurchaseOrder.objects.select_for_update().filter(id=order_id).first()
    if not order:
        raise NotFoundException("Đơn mua hàng không tồn tại.")

    if order.status not in [PurchaseOrder.Status.DRAFT]:
        raise ValidationException("Chỉ có thể cập nhật đơn hàng ở trạng thái Nháp.")

    vendor = Supplier.objects.filter(id=vendor_id).first()
    if not vendor:
        raise NotFoundException(f"Nhà cung cấp với ID {vendor_id} không tồn tại.")

    order.vendor = vendor
    order.status = status

    # Xóa các line cũ và tạo mới
    order.lines.all().delete()

    total_amount = 0
    for line in lines:
        item = Item.objects.filter(id=line["item_id"]).first()
        if not item:
            raise NotFoundException(f"Sản phẩm với ID {line['item_id']} không tồn tại.")

        qty = line.get("quantity", 0)
        unit_price = line.get("unit_price", 0)
        line_total = qty * unit_price
        total_amount += line_total

        PurchaseOrderLine.objects.create(
            order=order, item=item, quantity=qty, unit_price=unit_price, line_total=line_total
        )

    order.total_amount = total_amount
    order.save()

    create_system_log(
        user=user,
        action="update",
        table_name="purchase_order",
        record_id=str(order.id),
        new_value={"status": order.status, "total": str(total_amount)},
    )

    return order


@transaction.atomic
def purchase_order_delete(*, user: User, order_id: str) -> None:
    """
    Xóa Đơn mua hàng. Chỉ cho phép khi ở trạng thái Draft.
    """
    PermissionChecker.check_permission(user, "purchasing.delete_order")

    order = PurchaseOrder.objects.select_for_update().filter(id=order_id).first()
    if not order:
        raise NotFoundException("Đơn mua hàng không tồn tại.")

    if order.status != PurchaseOrder.Status.DRAFT:
        raise ValidationException("Chỉ có thể xóa hoàn toàn đơn hàng khi đang ở trạng thái Nháp.")

    order_id_str = str(order.id)
    order.delete()

    create_system_log(
        user=user, action="delete", table_name="purchase_order", record_id=order_id_str, new_value={"status": "deleted"}
    )


@transaction.atomic
def purchase_order_receive_goods(*, user: User, order_id: str, target_warehouse_id: str) -> PurchaseInvoice:
    """
    [DEPRECATED] Nhận hàng trực tiếp. Đã chuyển sang quy trình duyệt phiếu nhập kho riêng biệt.
    """
    raise ValidationException(
        "Quy trình nhận hàng trực tiếp qua đơn mua đã bị loại bỏ. Vui lòng duyệt Phiếu nhập kho tương ứng."
    )


def purchase_order_update_status(order: PurchaseOrder) -> None:
    """
    Tự động tính toán lại trạng thái của PurchaseOrder dựa trên:
    - Trạng thái thanh toán của Hóa đơn liên kết
    - Trạng thái duyệt của Phiếu nhập kho liên kết
    """
    if order.status in [PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.CANCELLED]:
        return

    # 1. Kiểm tra trạng thái thanh toán
    invoice = order.invoices.first()
    is_paid = False
    if invoice:
        is_paid = invoice.status == PurchaseInvoice.Status.PAID
    else:
        is_paid = order.advance_paid_amount >= order.total_amount and order.total_amount > 0

    # 2. Kiểm tra trạng thái nhập kho
    is_received = order.stock_entries.filter(status="posted").exists()

    # 3. Xác định trạng thái mới
    if is_received and is_paid:
        order.status = PurchaseOrder.Status.COMPLETED
    elif is_paid and not is_received:
        order.status = PurchaseOrder.Status.PAID_UNSHIPPED
    elif is_received and not is_paid:
        order.status = PurchaseOrder.Status.SHIPPED_UNPAID
    else:
        order.status = PurchaseOrder.Status.PENDING

    order.save()


@transaction.atomic
def purchase_order_approve(*, user: User, order_id: str) -> PurchaseOrder:
    """
    Duyệt Đơn mua hàng (Purchase Order):
    1. Chuyển trạng thái PO sang PENDING.
    2. Tạo Phiếu nhập kho nháp (Stock Entry receipt, draft, target_warehouse=None).
    3. Tạo Hóa đơn mua hàng (Purchase Invoice unpaid/partial/paid).
    """
    PermissionChecker.check_permission(user, "purchasing.update_order")

    order = PurchaseOrder.objects.select_for_update().filter(id=order_id).first()
    if not order:
        raise NotFoundException("Đơn mua hàng không tồn tại.")

    if order.status != PurchaseOrder.Status.DRAFT:
        raise ValidationException("Chỉ có thể duyệt đơn hàng đang ở trạng thái Nháp.")

    # 1. Chuyển trạng thái đơn hàng sang PENDING
    order.status = PurchaseOrder.Status.PENDING
    order.save()

    # 2. Tạo Phiếu nhập kho nháp (Draft Stock Entry)
    import uuid

    from apps.inventory.models import StockEntry, StockEntryDetail

    stock_name = f"IN-PUR-{str(order.id)[:8]}-{str(uuid.uuid4())[:4]}"
    stock_entry = StockEntry.objects.create(
        name=stock_name,
        purpose="receipt",
        posting_date=order.updated_at,
        remarks=f"Nhập kho tự động từ đơn mua {order.id}",
        status="draft",
        purchase_order=order,
    )
    for line in order.lines.all():
        StockEntryDetail.objects.create(
            parent=stock_entry, item=line.item, quantity=line.quantity, target_warehouse=None
        )

    # 3. Tạo Hóa đơn mua hàng (Purchase Invoice)
    if order.advance_paid_amount >= order.total_amount and order.total_amount > 0:
        invoice_status = PurchaseInvoice.Status.PAID
    elif order.advance_paid_amount > 0:
        invoice_status = PurchaseInvoice.Status.PARTIAL
    else:
        invoice_status = PurchaseInvoice.Status.UNPAID

    invoice = PurchaseInvoice.objects.create(
        order=order,
        stock_entry=stock_entry,
        vendor=order.vendor,
        status=invoice_status,
        total_amount=order.total_amount,
        paid_amount=order.advance_paid_amount,
    )
    for line in order.lines.all():
        PurchaseInvoiceLine.objects.create(
            invoice=invoice,
            item=line.item,
            quantity=line.quantity,
            unit_price=line.unit_price,
            import_tax=0,
            vat_tax=0,
            line_total=line.line_total,
        )

    # 4. Kích hoạt cập nhật lại trạng thái dựa trên thanh toán ứng trước (nếu có)
    purchase_order_update_status(order)

    create_system_log(
        user=user,
        action="approve",
        table_name="purchase_order",
        record_id=str(order.id),
        new_value={"status": order.status, "invoice_id": str(invoice.id), "stock_entry_id": str(stock_entry.id)},
    )

    return order
