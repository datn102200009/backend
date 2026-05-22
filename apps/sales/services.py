"""
Services for sales app.

All write operations for Sales Orders and Sales Invoices.
"""

from typing import Any, Dict, List

from django.db import transaction

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.crm.models import Customer
from apps.inventory.selectors import stock_ledger_balance_by_item_warehouse
from apps.inventory.services import stock_issue_approve, stock_issue_create
from apps.master_data.models import Item, Warehouse
from apps.sales.models import SalesInvoice, SalesInvoiceLine, SalesOrder, SalesOrderLine


@transaction.atomic
def sales_order_create(*, user: User, customer_id: str, lines: List[Dict[str, Any]]) -> SalesOrder:
    """
    Khởi tạo Đơn bán hàng (Sales Order). Không yêu cầu Kho hàng tại bước này.
    """
    PermissionChecker.check_permission(user, "sales.create_order")

    customer = Customer.objects.filter(id=customer_id).first()
    if not customer:
        raise NotFoundException(f"Khách hàng với ID {customer_id} không tồn tại.")

    order = SalesOrder.objects.create(customer=customer, status=SalesOrder.Status.DRAFT)

    total_amount = 0
    for line in lines:
        item = Item.objects.filter(id=line["item_id"]).first()
        if not item:
            raise NotFoundException(f"Sản phẩm với ID {line['item_id']} không tồn tại.")

        qty = line.get("quantity", 0)
        unit_price = line.get("unit_price", 0)
        line_total = qty * unit_price
        total_amount += line_total

        SalesOrderLine.objects.create(
            order=order, item=item, quantity=qty, unit_price=unit_price, line_total=line_total
        )

    order.total_amount = total_amount
    order.save()

    create_system_log(
        user=user,
        action="create",
        table_name="sales_order",
        record_id=str(order.id),
        new_value={"status": order.status, "total": str(total_amount)},
    )

    return order


@transaction.atomic
def sales_order_update(
    *, user: User, order_id: str, customer_id: str, status: str, lines: List[Dict[str, Any]]
) -> SalesOrder:
    """
    Cập nhật Đơn bán hàng. Chỉ cho phép khi ở trạng thái Draft.
    """
    PermissionChecker.check_permission(user, "sales.update_order")

    order = SalesOrder.objects.select_for_update().filter(id=order_id).first()
    if not order:
        raise NotFoundException("Đơn bán hàng không tồn tại.")

    if order.status not in [SalesOrder.Status.DRAFT]:
        raise ValidationException("Chỉ có thể cập nhật đơn hàng ở trạng thái Nháp.")

    customer = Customer.objects.filter(id=customer_id).first()
    if not customer:
        raise NotFoundException(f"Khách hàng với ID {customer_id} không tồn tại.")

    order.customer = customer
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

        SalesOrderLine.objects.create(
            order=order, item=item, quantity=qty, unit_price=unit_price, line_total=line_total
        )

    order.total_amount = total_amount
    order.save()

    create_system_log(
        user=user,
        action="update",
        table_name="sales_order",
        record_id=str(order.id),
        new_value={"status": order.status, "total": str(total_amount)},
    )

    return order


@transaction.atomic
def sales_order_delete(*, user: User, order_id: str) -> None:
    """
    Xóa Đơn bán hàng. Chỉ cho phép khi ở trạng thái Draft.
    """
    PermissionChecker.check_permission(user, "sales.delete_order")

    order = SalesOrder.objects.select_for_update().filter(id=order_id).first()
    if not order:
        raise NotFoundException("Đơn bán hàng không tồn tại.")

    if order.status != SalesOrder.Status.DRAFT:
        raise ValidationException("Chỉ có thể xóa hoàn toàn đơn hàng khi đang ở trạng thái Nháp.")

    order_id_str = str(order.id)
    order.delete()

    create_system_log(
        user=user, action="delete", table_name="sales_order", record_id=order_id_str, new_value={"status": "deleted"}
    )


@transaction.atomic
def sales_order_deliver_goods(*, user: User, order_id: str, source_warehouse_id: str) -> SalesInvoice:
    """
    [DEPRECATED] Xuất giao hàng trực tiếp. Đã chuyển sang quy trình duyệt phiếu xuất kho riêng biệt.
    """
    raise ValidationException(
        "Quy trình giao hàng trực tiếp qua đơn bán đã bị loại bỏ. Vui lòng duyệt Phiếu xuất kho tương ứng."
    )


def sales_order_update_status(order: SalesOrder) -> None:
    """
    Tự động tính toán lại trạng thái của SalesOrder dựa trên:
    - Trạng thái thanh toán của Hóa đơn liên kết
    - Trạng thái duyệt của Phiếu xuất kho liên kết
    """
    if order.status in [SalesOrder.Status.DRAFT, SalesOrder.Status.CANCELLED]:
        return

    # 1. Kiểm tra trạng thái thanh toán
    invoice = order.invoices.first()
    is_paid = False
    if invoice:
        is_paid = invoice.status == SalesInvoice.Status.PAID
    else:
        is_paid = order.advance_paid_amount >= order.total_amount and order.total_amount > 0

    # 2. Kiểm tra trạng thái xuất kho
    is_shipped = order.stock_entries.filter(status="posted").exists()

    # 3. Xác định trạng thái mới
    if is_shipped and is_paid:
        order.status = SalesOrder.Status.COMPLETED
    elif is_paid and not is_shipped:
        order.status = SalesOrder.Status.PAID_UNSHIPPED
    elif is_shipped and not is_paid:
        order.status = SalesOrder.Status.SHIPPED_UNPAID
    else:
        order.status = SalesOrder.Status.PENDING

    order.save()


@transaction.atomic
def sales_order_approve(*, user: User, order_id: str) -> SalesOrder:
    """
    Duyệt Đơn bán hàng (Sales Order):
    1. Chuyển trạng thái SO sang PENDING.
    2. Tạo Phiếu xuất kho nháp (Stock Entry issue, draft, source_warehouse=None).
    3. Tạo Hóa đơn bán hàng (Sales Invoice unpaid/partial/paid).
    """
    PermissionChecker.check_permission(user, "sales.update_order")

    order = SalesOrder.objects.select_for_update().filter(id=order_id).first()
    if not order:
        raise NotFoundException("Đơn bán hàng không tồn tại.")

    if order.status != SalesOrder.Status.DRAFT:
        raise ValidationException("Chỉ có thể duyệt đơn hàng đang ở trạng thái Nháp.")

    # 1. Chuyển trạng thái đơn hàng sang PENDING
    order.status = SalesOrder.Status.PENDING
    order.save()

    # 2. Tạo Phiếu xuất kho nháp (Draft Stock Entry)
    import uuid

    from apps.inventory.models import StockEntry, StockEntryDetail

    stock_name = f"OUT-SAL-{str(order.id)[:8]}-{str(uuid.uuid4())[:4]}"
    stock_entry = StockEntry.objects.create(
        name=stock_name,
        purpose="issue",
        posting_date=order.updated_at,
        remarks=f"Xuất kho tự động từ đơn bán {order.id}",
        status="draft",
        sales_order=order,
    )
    for line in order.lines.all():
        StockEntryDetail.objects.create(
            parent=stock_entry, item=line.item, quantity=line.quantity, source_warehouse=None
        )

    # 3. Tạo Hóa đơn bán hàng (Sales Invoice)
    if order.advance_paid_amount >= order.total_amount and order.total_amount > 0:
        invoice_status = SalesInvoice.Status.PAID
    elif order.advance_paid_amount > 0:
        invoice_status = SalesInvoice.Status.PARTIAL
    else:
        invoice_status = SalesInvoice.Status.UNPAID

    invoice = SalesInvoice.objects.create(
        order=order,
        stock_entry=stock_entry,
        customer=order.customer,
        status=invoice_status,
        total_amount=order.total_amount,
        paid_amount=order.advance_paid_amount,
    )
    for line in order.lines.all():
        SalesInvoiceLine.objects.create(
            invoice=invoice,
            item=line.item,
            quantity=line.quantity,
            unit_price=line.unit_price,
            vat_tax=0,
            line_total=line.line_total,
        )

    # 4. Kích hoạt cập nhật lại trạng thái dựa trên thanh toán ứng trước (nếu có)
    sales_order_update_status(order)

    create_system_log(
        user=user,
        action="approve",
        table_name="sales_order",
        record_id=str(order.id),
        new_value={"status": order.status, "invoice_id": str(invoice.id), "stock_entry_id": str(stock_entry.id)},
    )

    return order
