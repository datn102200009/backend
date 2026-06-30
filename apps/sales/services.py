"""
Services for sales app.

All write operations for Sales Orders and Sales Invoices.
"""

import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

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
    *,
    user: User,
    customer_id: str,
    lines: List[Dict[str, Any]],
    advance_paid_amount: Decimal = Decimal("0.00"),
    due_date: Optional[Any] = None,
) -> SalesOrder:
    """
    Khởi tạo Đơn bán hàng (Sales Order). Không yêu cầu Kho hàng tại bước này.
    """
    PermissionChecker.check_permission(user, "sales.create_order")

    customer = Customer.objects.filter(id=customer_id).first()
    if not customer:
        raise NotFoundException(f"Khách hàng với ID {customer_id} không tồn tại.")

    from datetime import date, datetime, timedelta

    from django.utils import timezone

    if due_date and isinstance(due_date, str):
        due_date = datetime.strptime(due_date, "%Y-%m-%d").date()

    due_date_val = due_date or (timezone.now().date() + timedelta(days=30))

    order = SalesOrder.objects.create(customer=customer, status=SalesOrder.Status.DRAFT, due_date=due_date_val)

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
        allowed_permissions=["sales.view_log"],
    )

    return order


@transaction.atomic
def sales_order_update(
    *,
    user: User,
    order_id: str,
    customer_id: str,
    lines: List[Dict[str, Any]],
    advance_paid_amount: Decimal = Decimal("0.00"),
    due_date: Optional[Any] = None,
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

    from datetime import date, datetime, timedelta

    from django.utils import timezone

    if due_date and isinstance(due_date, str):
        due_date = datetime.strptime(due_date, "%Y-%m-%d").date()

    due_date_val = due_date or (timezone.now().date() + timedelta(days=30))

    # Kiểm tra dòng tiền tạm thời để validate
    temp_total_amount = Decimal("0.00")
    for line in lines:
        qty = Decimal(str(line.get("quantity", 0)))
        unit_price = Decimal(str(line.get("unit_price", 0)))
        temp_total_amount += qty * unit_price

    if advance_paid_amount > temp_total_amount:
        raise ValidationException("Số tiền cọc không được lớn hơn tổng giá trị đơn hàng.")

    order.customer = customer
    order.status = SalesOrder.Status.DRAFT
    order.advance_paid_amount = advance_paid_amount
    order.due_date = due_date_val

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
        allowed_permissions=["sales.view_log"],
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
        user=user,
        action="delete",
        table_name="sales_order",
        record_id=order_id_str,
        new_value={"status": "deleted"},
        allowed_permissions=["sales.view_log"],
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
    Tự động tính toán lại trạng thái của SalesOrder và tiến độ giao hàng/thanh toán.
    """
    if order.status in [SalesOrder.Status.DRAFT, SalesOrder.Status.CANCELLED]:
        return

    from django.db.models import Sum

    from apps.inventory.models import StockEntryDetail

    # 1. Tính toán tiến độ giao hàng cho từng dòng và lưu lại
    lines = order.lines.all()
    lines_count = lines.count()

    # DB-level group by item to avoid loop N+1 issues and memory overhead
    shipped_qtys = {}
    rows = (
        StockEntryDetail.objects.filter(parent__sales_order=order, parent__status="posted")
        .values("item_id")
        .annotate(total_qty=Sum("quantity"))
    )
    for row in rows:
        shipped_qtys[row["item_id"]] = row["total_qty"]

    updated_lines = []
    for line in lines:
        total_shipped = shipped_qtys.get(line.item_id, Decimal("0.00"))

        if line.quantity > 0:
            line.receipt_fulfillment_rate = ((total_shipped / line.quantity) * Decimal("100.00")).quantize(
                Decimal("0.01")
            )
        else:
            line.receipt_fulfillment_rate = Decimal("100.00")
        updated_lines.append(line)

    SalesOrderLine.objects.bulk_update(updated_lines, ["receipt_fulfillment_rate"])

    # 2. Tính toán tiến độ giao hàng tổng của SO (trung bình cộng tiến độ các dòng)
    if lines_count > 0:
        total_rates_sum = sum(line.receipt_fulfillment_rate for line in lines)
        order.receipt_fulfillment_rate = (total_rates_sum / lines_count).quantize(Decimal("0.01"))
    else:
        order.receipt_fulfillment_rate = Decimal("100.00")

    # 3. Tính toán tiến độ thanh toán của SO dựa trên toàn bộ hóa đơn hoạt động
    invoices = order.invoices.exclude(status="cancelled")
    if invoices.exists():
        totals = invoices.aggregate(paid=Sum("paid_amount"))
        paid_amount = totals["paid"] or Decimal("0.00")
    else:
        paid_amount = order.advance_paid_amount

    if order.total_amount > 0:
        order.payment_fulfillment_rate = ((paid_amount / order.total_amount) * Decimal("100.00")).quantize(
            Decimal("0.01")
        )
    else:
        order.payment_fulfillment_rate = Decimal("100.00")

    # 4. Xác định trạng thái mới dựa trên tiến độ giao hàng và thanh toán
    is_shipped = order.receipt_fulfillment_rate >= Decimal("100.00")
    is_paid = order.payment_fulfillment_rate >= Decimal("100.00")

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
def sales_order_approve(*, user: User, order_id: str, due_date=None) -> SalesOrder:
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
            allowed_permissions=["sales.view_log"],
        )
        return order

    # 1. Chuyển trạng thái đơn hàng sang PENDING
    order.status = SalesOrder.Status.PENDING

    orig_advance_paid_amount = order.advance_paid_amount
    order.advance_paid_amount = Decimal("0.00")
    order.save()

    # Tự động ghi nhận dòng tiền cọc (Thu tiền cọc) nếu có cọc và chưa có dòng tiền cọc
    if orig_advance_paid_amount > 0:
        if not order.cash_flows.filter(payment_type="receive").exists():
            from apps.finance.models import CashFlowTransaction

            payment_name = f"CF-REC-DEP-{str(order.id)[:8]}-{str(uuid.uuid4())[:4]}"
            CashFlowTransaction.objects.create(
                name=payment_name,
                payment_type="receive",
                category="Đặt cọc đơn hàng",
                payment_method="bank_transfer",
                amount=orig_advance_paid_amount,
                payment_date=order.updated_at.date(),
                sales_order=order,
                status="pending_approval",
                remarks=f"Tự động thu tiền cọc từ đơn bán hàng {order.id} (Khách hàng: {order.customer.customer_name}, Tổng giá trị đơn: {order.total_amount:,.2f}đ, Số tiền cọc: {orig_advance_paid_amount:,.2f}đ).",
            )

    # 2. Tạo Phiếu xuất kho nháp (Draft Stock Entry)
    from apps.inventory.models import StockEntry, StockEntryDetail

    stock_name = f"OUT-SAL-SO-{str(order.id)[:8].upper()}-{str(uuid.uuid4())[:4]}"
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

    if not due_date:
        due_date = order.due_date
    if not due_date:
        import datetime

        from django.utils import timezone

        due_date = timezone.now().date() + datetime.timedelta(days=30)

    # 3. Tạo Hóa đơn bán hàng (Sales Invoice)
    invoice = SalesInvoice.objects.create(
        order=order,
        stock_entry=stock_entry,
        customer=order.customer,
        status=SalesInvoice.Status.UNPAID,
        total_amount=order.total_amount,
        paid_amount=Decimal("0.00"),
        due_date=due_date,
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
        allowed_permissions=["sales.view_log"],
    )

    return order


@transaction.atomic
def approve_credit_bypass(*, user: User, order_id: str) -> SalesOrder:
    """
    CFO/Admin duyệt đặc cách đơn hàng bị khóa tín dụng.
    Chuyển sang PENDING và tự động sinh StockEntry, SalesInvoice.
    """
    PermissionChecker.check_permission(user, "finance.approve_credit_bypass")

    order = SalesOrder.objects.select_for_update().filter(id=order_id).first()
    if not order:
        raise NotFoundException("Đơn bán hàng không tồn tại.")

    if order.status != SalesOrder.Status.PENDING_CREDIT_APPROVAL:
        raise ValidationException("Chỉ có thể duyệt đặc cách cho đơn hàng ở trạng thái Chờ duyệt tín dụng.")

    # Bỏ qua kiểm tra tín dụng, duyệt trực tiếp:
    order.status = SalesOrder.Status.PENDING

    orig_advance_paid_amount = order.advance_paid_amount
    order.advance_paid_amount = Decimal("0.00")
    order.save()

    # Tự động ghi nhận dòng tiền cọc (Thu tiền cọc) nếu có cọc và chưa có dòng tiền cọc
    if orig_advance_paid_amount > 0:
        if not order.cash_flows.filter(payment_type="receive").exists():
            from apps.finance.models import CashFlowTransaction

            payment_name = f"CF-REC-DEP-{str(order.id)[:8]}-{str(uuid.uuid4())[:4]}"
            CashFlowTransaction.objects.create(
                name=payment_name,
                payment_type="receive",
                category="Đặt cọc đơn hàng",
                payment_method="bank_transfer",
                amount=orig_advance_paid_amount,
                payment_date=order.updated_at.date(),
                sales_order=order,
                status="pending_approval",
                remarks=f"Tự động thu tiền cọc từ đơn bán hàng {order.id} (Khách hàng: {order.customer.customer_name}, Tổng giá trị đơn: {order.total_amount:,.2f}đ, Số tiền cọc: {orig_advance_paid_amount:,.2f}đ).",
            )

    # Tạo Phiếu xuất kho nháp
    from apps.inventory.models import StockEntry, StockEntryDetail

    stock_name = f"OUT-SAL-SO-{str(order.id)[:8].upper()}-{str(uuid.uuid4())[:4]}"
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
    invoice = SalesInvoice.objects.create(
        order=order,
        stock_entry=stock_entry,
        customer=order.customer,
        status=SalesInvoice.Status.UNPAID,
        total_amount=order.total_amount,
        paid_amount=Decimal("0.00"),
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
        allowed_permissions=["sales.view_log"],
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

    created_cfs = []

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
        rev_tx = cash_flow_reverse(user=user, original_tx=tx, remarks=remarks_rev)
        created_cfs.append(rev_tx)

    # 3. Cập nhật các Hóa đơn liên kết
    invoices = order.invoices.select_for_update()
    for invoice in invoices.iterator(chunk_size=1000):
        invoice.status = SalesInvoice.Status.CANCELLED
        invoice.paid_amount = Decimal("0.00")
        invoice.save()

    # 4. Cập nhật Đơn hàng
    if created_cfs:
        order.status = SalesOrder.Status.CANCEL_PENDING
    else:
        order.status = SalesOrder.Status.CANCELLED
    order.advance_paid_amount = Decimal("0.00")
    order.save()

    create_system_log(
        user=user,
        action="cancel",
        table_name="sales_order",
        record_id=str(order.id),
        new_value={"status": order.status},
        allowed_permissions=["sales.view_log"],
    )

    return order
