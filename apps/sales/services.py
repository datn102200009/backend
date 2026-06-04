"""
Services for sales app.

All write operations for Sales Orders and Sales Invoices.
"""

import uuid
from decimal import Decimal
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
from apps.sales.selectors import check_customer_overdue_debts, get_customer_current_debt


@transaction.atomic
def sales_order_create(
    *, user: User, customer_id: str, lines: List[Dict[str, Any]], advance_paid_amount: Decimal = Decimal("0.00")
) -> SalesOrder:
    """
    Khởi tạo Đơn bán hàng (Sales Order). Không yêu cầu Kho hàng tại bước này.
    """
    PermissionChecker.check_permission(user, "sales.create_order")

    customer = Customer.objects.filter(id=customer_id).first()
    if not customer:
        raise NotFoundException(f"Khách hàng với ID {customer_id} không tồn tại.")

    order = SalesOrder.objects.create(customer=customer, status=SalesOrder.Status.DRAFT)

    total_amount = Decimal("0.00")
    for line in lines:
        item = Item.objects.filter(id=line["item_id"]).first()
        if not item:
            raise NotFoundException(f"Sản phẩm với ID {line['item_id']} không tồn tại.")

        qty = Decimal(str(line.get("quantity", 0)))
        unit_price = Decimal(str(line.get("unit_price", 0)))
        line_total = qty * unit_price
        total_amount += line_total

        SalesOrderLine.objects.create(
            order=order, item=item, quantity=qty, unit_price=unit_price, line_total=line_total
        )

    if advance_paid_amount > total_amount:
        raise ValidationException("Số tiền cọc không được lớn hơn tổng giá trị đơn hàng.")

    order.total_amount = total_amount
    order.advance_paid_amount = advance_paid_amount
    order.save()

    create_system_log(
        user=user,
        action="create",
        table_name="sales_order",
        record_id=str(order.id),
        new_value={"status": order.status, "total": str(total_amount), "advance_paid_amount": str(advance_paid_amount)},
    )

    return order


@transaction.atomic
def sales_order_update(
    *,
    user: User,
    order_id: str,
    customer_id: str,
    status: str,
    lines: List[Dict[str, Any]],
    advance_paid_amount: Decimal = Decimal("0.00"),
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

    # Kiểm tra dòng tiền tạm thời để validate
    temp_total_amount = Decimal("0.00")
    for line in lines:
        qty = Decimal(str(line.get("quantity", 0)))
        unit_price = Decimal(str(line.get("unit_price", 0)))
        temp_total_amount += qty * unit_price

    if advance_paid_amount > temp_total_amount:
        raise ValidationException("Số tiền cọc không được lớn hơn tổng giá trị đơn hàng.")

    order.customer = customer
    order.status = status
    order.advance_paid_amount = advance_paid_amount

    # Xóa các line cũ và tạo mới
    order.lines.all().delete()

    total_amount = Decimal("0.00")
    for line in lines:
        item = Item.objects.filter(id=line["item_id"]).first()
        if not item:
            raise NotFoundException(f"Sản phẩm với ID {line['item_id']} không tồn tại.")

        qty = Decimal(str(line.get("quantity", 0)))
        unit_price = Decimal(str(line.get("unit_price", 0)))
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
        new_value={"status": order.status, "total": str(total_amount), "advance_paid_amount": str(advance_paid_amount)},
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

    if order.advance_paid_amount > 0:
        raise ValidationException(
            "Không thể xóa đơn hàng đã phát sinh thanh toán cọc. Vui lòng hoàn trả dòng tiền cọc trước khi xóa."
        )

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


def validate_sales_order_credit(sales_order_id: str) -> tuple[bool, str]:
    """
    Kiểm tra tín dụng của khách hàng liên quan đến đơn bán hàng.
    Trả về (True, "") nếu tín dụng hợp lệ, (False, lý do) nếu bị khóa nợ, vượt hạn mức hoặc có nợ quá hạn > 30 ngày.
    """
    order = SalesOrder.objects.filter(id=sales_order_id).select_related("customer").first()
    if not order:
        raise NotFoundException("Đơn bán hàng không tồn tại.")

    customer = order.customer
    if customer.is_credit_locked:
        return False, "Khách hàng bị khóa tín dụng chủ động"

    current_debt = get_customer_current_debt(str(customer.id))
    projected_credit_amount = max(Decimal("0.00"), order.total_amount - order.advance_paid_amount)
    projected_debt = current_debt + projected_credit_amount

    if projected_debt > customer.credit_limit:
        return (
            False,
            f"Vượt hạn mức tín dụng công nợ (Hạn mức: {customer.credit_limit}, Dư nợ dự kiến: {projected_debt})",
        )

    if check_customer_overdue_debts(str(customer.id), max_days=30):
        return False, "Có hóa đơn quá hạn thanh toán trên 30 ngày"

    return True, ""


@transaction.atomic
def sales_order_approve(*, user: User, order_id: str) -> SalesOrder:
    """
    Duyệt Đơn bán hàng (Sales Order):
    1. Kiểm tra hạn mức tín dụng & công nợ phải thu (AR).
    2. Nếu không đạt yêu cầu, chuyển trạng thái sang PENDING_CREDIT_APPROVAL (Chờ duyệt tín dụng) và khóa đơn.
    3. Nếu đạt yêu cầu, chuyển trạng thái sang PENDING và tự động sinh StockEntry, SalesInvoice.
    """
    PermissionChecker.check_permission(user, "sales.update_order")

    order = SalesOrder.objects.select_for_update().filter(id=order_id).first()
    if not order:
        raise NotFoundException("Đơn bán hàng không tồn tại.")

    if order.status != SalesOrder.Status.DRAFT:
        raise ValidationException("Chỉ có thể duyệt đơn hàng đang ở trạng thái Nháp.")

    # Kiểm tra tín dụng trước khi duyệt
    is_credit_valid, credit_block_reason = validate_sales_order_credit(order_id)

    if not is_credit_valid:
        order.status = SalesOrder.Status.PENDING_CREDIT_APPROVAL
        order.save()

        create_system_log(
            user=user,
            action="approve",
            table_name="sales_order",
            record_id=str(order.id),
            new_value={"status": order.status, "message": f"Bị khóa tín dụng công nợ: {credit_block_reason}"},
        )
        return order

    # 1. Chuyển trạng thái đơn hàng sang PENDING
    order.status = SalesOrder.Status.PENDING
    order.save()

    # Tự động ghi nhận dòng tiền cọc (Thu tiền cọc) nếu có cọc và chưa có dòng tiền cọc
    if order.advance_paid_amount > 0:
        if not order.cash_flows.filter(payment_type="receive").exists():
            from apps.finance.models import CashFlowTransaction

            payment_name = f"CF-REC-DEP-{str(order.id)[:8]}-{str(uuid.uuid4())[:4]}"
            CashFlowTransaction.objects.create(
                name=payment_name,
                payment_type="receive",
                category="Đặt cọc đơn hàng",
                payment_method="bank_transfer",
                amount=order.advance_paid_amount,
                payment_date=order.updated_at.date(),
                sales_order=order,
                remarks=f"Tự động thu tiền cọc từ đơn bán hàng {order.id} (Khách hàng: {order.customer.customer_name}, Tổng giá trị đơn: {order.total_amount:,.2f}đ, Số tiền cọc: {order.advance_paid_amount:,.2f}đ).",
            )

    # 2. Tạo Phiếu xuất kho nháp (Draft Stock Entry)
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


@transaction.atomic
def approve_credit_bypass(*, user: User, order_id: str) -> SalesOrder:
    """
    CFO/Admin duyệt đặc cách đơn hàng bị khóa tín dụng.
    Chuyển sang PENDING và tự động sinh StockEntry, SalesInvoice.
    """
    PermissionChecker.check_permission(user, "sales.approve_credit_bypass")

    order = SalesOrder.objects.select_for_update().filter(id=order_id).first()
    if not order:
        raise NotFoundException("Đơn bán hàng không tồn tại.")

    if order.status != SalesOrder.Status.PENDING_CREDIT_APPROVAL:
        raise ValidationException("Chỉ có thể duyệt đặc cách cho đơn hàng ở trạng thái Chờ duyệt tín dụng.")

    # Bỏ qua kiểm tra tín dụng, duyệt trực tiếp:
    order.status = SalesOrder.Status.PENDING
    order.save()

    # Tự động ghi nhận dòng tiền cọc (Thu tiền cọc) nếu có cọc và chưa có dòng tiền cọc
    if order.advance_paid_amount > 0:
        if not order.cash_flows.filter(payment_type="receive").exists():
            from apps.finance.models import CashFlowTransaction

            payment_name = f"CF-REC-DEP-{str(order.id)[:8]}-{str(uuid.uuid4())[:4]}"
            CashFlowTransaction.objects.create(
                name=payment_name,
                payment_type="receive",
                category="Đặt cọc đơn hàng",
                payment_method="bank_transfer",
                amount=order.advance_paid_amount,
                payment_date=order.updated_at.date(),
                sales_order=order,
                remarks=f"Tự động thu tiền cọc từ đơn bán hàng {order.id} (Khách hàng: {order.customer.customer_name}, Tổng giá trị đơn: {order.total_amount:,.2f}đ, Số tiền cọc: {order.advance_paid_amount:,.2f}đ).",
            )

    # Tạo Phiếu xuất kho nháp
    from apps.inventory.models import StockEntry, StockEntryDetail

    stock_name = f"OUT-SAL-{str(order.id)[:8]}-{str(uuid.uuid4())[:4]}"
    stock_entry = StockEntry.objects.create(
        name=stock_name,
        purpose="issue",
        posting_date=order.updated_at,
        remarks=f"Xuất kho tự động từ đơn bán {order.id} (Duyệt đặc cách tín dụng)",
        status="draft",
        sales_order=order,
    )
    for line in order.lines.all():
        StockEntryDetail.objects.create(
            parent=stock_entry, item=line.item, quantity=line.quantity, source_warehouse=None
        )

    # Tạo Hóa đơn bán hàng
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

    sales_order_update_status(order)

    create_system_log(
        user=user,
        action="approve_credit_bypass",
        table_name="sales_order",
        record_id=str(order.id),
        new_value={"status": order.status, "invoice_id": str(invoice.id), "stock_entry_id": str(stock_entry.id)},
    )

    return order


@transaction.atomic
def sales_order_cancel(*, user: User, order_id: str) -> SalesOrder:
    """
    Hủy Đơn bán hàng (Sales Order) đã duyệt bằng cách:
    1. Chuyển trạng thái các StockEntry liên quan sang cancelled hoặc đối ứng.
    2. Đảo ngược các CashFlowTransaction liên quan.
    3. Hủy các Invoice liên quan và cập nhật paid_amount về 0.
    4. Đổi trạng thái SO sang cancelled.
    """
    PermissionChecker.check_permission(user, "sales.cancel_order")

    order = SalesOrder.objects.select_for_update().filter(id=order_id).first()
    if not order:
        raise NotFoundException("Đơn bán hàng không tồn tại.")

    if order.status == SalesOrder.Status.DRAFT:
        raise ValidationException(
            "Đơn hàng ở trạng thái Nháp không thể hủy theo quy trình này. Vui lòng cập nhật hoặc xóa đơn hàng."
        )
    if order.status == SalesOrder.Status.CANCELLED:
        raise ValidationException("Đơn hàng đã được hủy trước đó.")

    from django.db.models import Q

    from apps.finance.models import CashFlowTransaction
    from apps.finance.services import cash_flow_reverse
    from apps.inventory.models import StockEntry
    from apps.inventory.services import stock_entry_cancel, stock_entry_reverse

    # 1. Xử lý các StockEntry liên kết
    stock_entries = StockEntry.objects.select_for_update().filter(sales_order=order)
    for entry in stock_entries.iterator(chunk_size=1000):
        if entry.status == "draft":
            stock_entry_cancel(user=user, stock_entry=entry)
        elif entry.status == "posted":
            remarks_rev = f"Nhập kho hoàn trả tự động do hủy đơn bán {order.id}"
            stock_entry_reverse(user=user, original_entry=entry, remarks=remarks_rev)

    # 2. Xử lý các CashFlowTransaction liên kết
    invoice_ids = list(order.invoices.values_list("id", flat=True))
    cash_flows = CashFlowTransaction.objects.select_for_update().filter(
        Q(sales_order=order) | Q(sales_invoice_id__in=invoice_ids)
    )
    for tx in cash_flows.iterator(chunk_size=1000):
        if tx.category == "Hoàn trả thanh toán":
            continue
        remarks_rev = f"Hoàn trả thu tiền tự động do hủy đơn bán {order.id} (Đối ứng cho giao dịch đặt cọc/thanh toán gốc {tx.name}, Số tiền hoàn: {tx.amount:,.2f}đ)."
        cash_flow_reverse(user=user, original_tx=tx, remarks=remarks_rev)

    # 3. Cập nhật các Hóa đơn liên kết
    invoices = order.invoices.select_for_update()
    for invoice in invoices.iterator(chunk_size=1000):
        invoice.status = SalesInvoice.Status.CANCELLED
        invoice.paid_amount = Decimal("0.00")
        invoice.save()

    # 4. Cập nhật Đơn hàng
    order.status = SalesOrder.Status.CANCELLED
    order.advance_paid_amount = Decimal("0.00")
    order.save()

    create_system_log(
        user=user,
        action="cancel",
        table_name="sales_order",
        record_id=str(order.id),
        new_value={"status": order.status},
    )

    return order
