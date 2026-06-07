"""
Services for purchasing app.

All write operations for Purchase Orders and Purchase Invoices.
"""

import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.inventory.services import stock_in_approve, stock_in_create
from apps.master_data.models import Item
from apps.procurement.models import Supplier
from apps.purchasing.models import PurchaseInvoice, PurchaseInvoiceLine, PurchaseOrder, PurchaseOrderLine, Shipment


@transaction.atomic
def purchase_order_create(
    *,
    user: User,
    vendor_id: str,
    lines: List[Dict[str, Any]],
    advance_paid_amount: Decimal = Decimal("0.00"),
    expected_delivery_date: Optional[Any] = None,
) -> PurchaseOrder:
    """
    Khởi tạo Đơn mua hàng (Purchase Order).
    """
    PermissionChecker.check_permission(user, "purchasing.create_order")

    vendor = Supplier.objects.filter(id=vendor_id).first()
    if not vendor:
        raise NotFoundException(f"Nhà cung cấp với ID {vendor_id} không tồn tại.")

    from datetime import date, datetime

    if expected_delivery_date and isinstance(expected_delivery_date, str):
        expected_delivery_date = datetime.strptime(expected_delivery_date, "%Y-%m-%d").date()

    order = PurchaseOrder.objects.create(
        vendor=vendor, status=PurchaseOrder.Status.DRAFT, expected_delivery_date=expected_delivery_date
    )

    total_amount = Decimal("0.00")
    for line in lines:
        item = Item.objects.filter(id=line["item_id"]).first()
        if not item:
            raise NotFoundException(f"Sản phẩm với ID {line['item_id']} không tồn tại.")

        qty = Decimal(str(line.get("quantity", 0)))
        unit_price = Decimal(str(line.get("unit_price", 0)))
        line_total = qty * unit_price
        total_amount += line_total

        PurchaseOrderLine.objects.create(
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
        table_name="purchase_order",
        record_id=str(order.id),
        new_value={"status": order.status, "total": str(total_amount), "advance_paid_amount": str(advance_paid_amount)},
    )

    return order


@transaction.atomic
def purchase_order_update(
    *,
    user: User,
    order_id: str,
    vendor_id: str,
    lines: List[Dict[str, Any]],
    advance_paid_amount: Decimal = Decimal("0.00"),
    expected_delivery_date: Optional[Any] = None,
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

    from datetime import date, datetime

    if expected_delivery_date and isinstance(expected_delivery_date, str):
        expected_delivery_date = datetime.strptime(expected_delivery_date, "%Y-%m-%d").date()

    # Kiểm tra dòng tiền tạm thời để validate
    temp_total_amount = Decimal("0.00")
    for line in lines:
        qty = Decimal(str(line.get("quantity", 0)))
        unit_price = Decimal(str(line.get("unit_price", 0)))
        temp_total_amount += qty * unit_price

    if advance_paid_amount > temp_total_amount:
        raise ValidationException("Số tiền cọc không được lớn hơn tổng giá trị đơn hàng.")

    order.vendor = vendor
    order.status = PurchaseOrder.Status.DRAFT
    order.advance_paid_amount = advance_paid_amount
    order.expected_delivery_date = expected_delivery_date

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
        new_value={"status": order.status, "total": str(total_amount), "advance_paid_amount": str(advance_paid_amount)},
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

    if order.advance_paid_amount > 0:
        raise ValidationException(
            "Không thể xóa đơn hàng đã phát sinh thanh toán cọc. Vui lòng hoàn trả dòng tiền cọc trước khi xóa."
        )

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


@transaction.atomic
def purchase_order_update_status(order: PurchaseOrder) -> None:
    """
    Tự động tính toán lại trạng thái của PurchaseOrder và tiến độ nhận hàng/thanh toán.
    """
    if order.status in [PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.CANCELLED]:
        return

    from django.db.models import Sum

    from apps.inventory.models import StockEntryDetail

    # 1. Tính toán tiến độ nhận hàng cho từng dòng và lưu lại
    lines = order.lines.all()
    lines_count = lines.count()

    # DB-level group by item to avoid loop N+1 issues and memory overhead
    received_qtys = {}
    rows = (
        StockEntryDetail.objects.filter(parent__purchase_order=order, parent__status="posted")
        .values("item_id")
        .annotate(total_qty=Sum("quantity"))
    )
    for row in rows:
        received_qtys[row["item_id"]] = row["total_qty"]

    updated_lines = []
    for line in lines:
        total_received = received_qtys.get(line.item_id, Decimal("0.00"))

        if line.quantity > 0:
            line.receipt_fulfillment_rate = ((total_received / line.quantity) * Decimal("100.00")).quantize(
                Decimal("0.01")
            )
        else:
            line.receipt_fulfillment_rate = Decimal("100.00")
        updated_lines.append(line)

    from apps.purchasing.models import PurchaseOrderLine

    PurchaseOrderLine.objects.bulk_update(updated_lines, ["receipt_fulfillment_rate"])

    # 2. Tính toán tiến độ nhận hàng tổng của PO (trung bình cộng tiến độ các dòng)
    if lines_count > 0:
        total_rates_sum = sum(line.receipt_fulfillment_rate for line in lines)
        order.receipt_fulfillment_rate = (total_rates_sum / lines_count).quantize(Decimal("0.01"))
    else:
        order.receipt_fulfillment_rate = Decimal("100.00")

    # 3. Tính toán tiến độ thanh toán của PO dựa trên toàn bộ hóa đơn hoạt động
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

    # 4. Xác định trạng thái mới dựa trên tiến độ nhận hàng và thanh toán
    is_received = order.receipt_fulfillment_rate >= Decimal("100.00")
    is_paid = order.payment_fulfillment_rate >= Decimal("100.00")

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

    # Tự động ghi nhận dòng tiền cọc (Chi tiền cọc) nếu có cọc và chưa có dòng tiền cọc
    if order.advance_paid_amount > 0:
        if not order.cash_flows.filter(payment_type="pay").exists():
            from apps.finance.models import CashFlowTransaction

            payment_name = f"CF-PAY-DEP-{str(order.id)[:8]}-{str(uuid.uuid4())[:4]}"
            CashFlowTransaction.objects.create(
                name=payment_name,
                payment_type="pay",
                category="Đặt cọc đơn hàng",
                payment_method="bank_transfer",
                amount=order.advance_paid_amount,
                payment_date=order.updated_at.date(),
                purchase_order=order,
                remarks=f"Tự động chi tiền cọc cho đơn mua hàng {order.id} (Nhà cung cấp: {order.vendor.supplier_name}, Tổng giá trị đơn: {order.total_amount:,.2f}đ, Số tiền cọc: {order.advance_paid_amount:,.2f}đ).",
            )

    # 2. Tạo Phiếu nhập kho nháp (Draft Stock Entry)
    from apps.inventory.models import StockEntry, StockEntryDetail

    stock_name = f"IN-PUR-PO-{str(order.id)[:8].upper()}-{str(uuid.uuid4())[:4]}"
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


@transaction.atomic
def purchase_order_cancel(
    *,
    user: User,
    order_id: str,
    refund_deposit: bool = True,
    keep_goods: bool = False,
) -> PurchaseOrder:
    """
    Hủy Đơn mua hàng (Purchase Order) đã duyệt với các tùy chọn:
    - Nếu chưa có hàng nhập kho:
        - refund_deposit=True: Hoàn trả lại tiền cọc (đảo ngược dòng tiền).
        - refund_deposit=False: Giữ tiền cọc (không hoàn trả dòng tiền).
    - Nếu đã có hàng nhập kho:
        - keep_goods=True: Giữ lại hàng, tính chênh lệch giữa giá trị hàng nhận và tiền đã trả, tạo giao dịch dòng tiền đối ứng để cân bằng.
        - keep_goods=False: Trả lại hàng (đảo ngược phiếu kho) và hoàn trả tiền (đảo ngược dòng tiền).
    """
    PermissionChecker.check_permission(user, "purchasing.cancel_order")

    order = PurchaseOrder.objects.select_for_update().filter(id=order_id).first()
    if not order:
        raise NotFoundException("Đơn mua hàng không tồn tại.")

    if order.status == PurchaseOrder.Status.DRAFT:
        raise ValidationException(
            "Đơn hàng ở trạng thái Nháp không thể hủy theo quy trình này. Vui lòng cập nhật hoặc xóa đơn hàng."
        )
    if order.status == PurchaseOrder.Status.CANCELLED:
        raise ValidationException("Đơn hàng đã được hủy trước đó.")

    from django.db.models import Q

    from apps.finance.models import CashFlowTransaction
    from apps.finance.services import cash_flow_reverse
    from apps.inventory.models import StockEntry, StockEntryDetail
    from apps.inventory.services import stock_entry_cancel, stock_entry_reverse

    # Kiểm tra xem đã có bất kỳ phiếu nhập kho nào đã post (hàng đã nhập thực tế) hay chưa
    has_received_goods = order.stock_entries.filter(status="posted").exists()

    if not has_received_goods:
        # --- CASE 1: Chưa có hàng nhập kho ---
        # 1. Hủy các StockEntry nháp
        stock_entries = StockEntry.objects.select_for_update().filter(purchase_order=order)
        for entry in stock_entries:
            if entry.status == "draft":
                stock_entry_cancel(user=user, stock_entry=entry)

        # 2. Xử lý dòng tiền cọc
        if refund_deposit:
            # Hoàn trả cọc: Đảo ngược các giao dịch dòng tiền gốc
            invoice_ids = list(order.invoices.values_list("id", flat=True))
            cash_flows = CashFlowTransaction.objects.select_for_update().filter(
                Q(purchase_order=order) | Q(purchase_invoice_id__in=invoice_ids)
            )
            for tx in cash_flows:
                if tx.category == "Hoàn trả thanh toán":
                    continue
                remarks_rev = f"Hoàn trả chi tiền tự động do hủy đơn mua {order.id} (Đối ứng cho giao dịch đặt cọc/thanh toán gốc {tx.name}, Số tiền hoàn: {tx.amount:,.2f}đ)."
                cash_flow_reverse(user=user, original_tx=tx, remarks=remarks_rev)

            # Cập nhật số tiền đặt cọc về 0
            order.advance_paid_amount = Decimal("0.00")
        else:
            # Giữ cọc: Không đảo ngược dòng tiền, giữ nguyên advance_paid_amount
            pass

        # 3. Hủy hóa đơn
        invoices = order.invoices.select_for_update()
        for invoice in invoices:
            invoice.status = PurchaseInvoice.Status.CANCELLED
            if refund_deposit:
                invoice.paid_amount = Decimal("0.00")
            invoice.save()

    else:
        # --- CASE 2: Đã có hàng nhập kho ---
        if keep_goods:
            # 1. Giữ lại hàng: Hủy các StockEntry nháp, giữ nguyên StockEntry posted
            stock_entries = StockEntry.objects.select_for_update().filter(purchase_order=order)
            for entry in stock_entries:
                if entry.status == "draft":
                    stock_entry_cancel(user=user, stock_entry=entry)

            # 2. Tính toán chênh lệch
            # Giá trị hàng nhận: sum(qty_received * po_line.unit_price)
            # Lấy qty_received thực tế cho từng item (trừ đi các dòng reversal nếu có)
            from django.db.models import Case, DecimalField, F, Sum, Value, When

            qty_received_by_item = {}
            details = (
                StockEntryDetail.objects.filter(parent__purchase_order=order, parent__status="posted")
                .annotate(
                    signed_qty=Case(
                        When(parent__purpose="receipt", then="quantity"),
                        When(parent__purpose="issue", then=F("quantity") * -1),
                        default=Value(0),
                        output_field=DecimalField(),
                    )
                )
                .values("item_id")
                .annotate(total_qty=Sum("signed_qty"))
            )

            for row in details:
                qty_received_by_item[row["item_id"]] = row["total_qty"] or Decimal("0.00")

            received_value = Decimal("0.00")
            for line in order.lines.all():
                qty_rec = qty_received_by_item.get(line.item_id, Decimal("0.00"))
                received_value += qty_rec * line.unit_price

            # Tổng tiền đã trả
            invoice_ids = list(order.invoices.values_list("id", flat=True))
            cash_flows = CashFlowTransaction.objects.filter(
                Q(purchase_order=order) | Q(purchase_invoice_id__in=invoice_ids)
            )
            total_paid = Decimal("0.00")
            for tx in cash_flows:
                if tx.payment_type == "pay":
                    total_paid += tx.amount
                elif tx.payment_type == "receive":
                    total_paid -= tx.amount

            # So khớp và cân bằng tài chính
            diff = received_value - total_paid
            if diff > 0:
                # Giá trị hàng nhận lớn hơn số tiền đã trả -> tạo phiếu CHI (pay) cho nhà cung cấp phần chênh lệch
                import uuid

                from django.utils import timezone

                payment_name = f"CF-PAY-DIFF-{str(order.id)[:8]}-{str(uuid.uuid4())[:4]}"

                CashFlowTransaction.objects.create(
                    name=payment_name,
                    payment_type="pay",
                    category="Thanh toán đối ứng chênh lệch hủy đơn",
                    payment_method="bank_transfer",
                    amount=diff,
                    payment_date=timezone.now().date(),
                    purchase_order=order,
                    remarks=f"Tự động chi tiền chênh lệch khi hủy đơn mua {order.id} và giữ lại hàng (Giá trị hàng: {received_value:,.2f}đ, Đã thanh toán: {total_paid:,.2f}đ, Chênh lệch cần chi: {diff:,.2f}đ).",
                )
            elif diff < 0:
                # Giá trị hàng nhận nhỏ hơn số tiền đã trả -> tạo phiếu THU (receive) để thu hồi tiền chênh lệch từ nhà cung cấp
                import uuid

                from django.utils import timezone

                payment_name = f"CF-REC-DIFF-{str(order.id)[:8]}-{str(uuid.uuid4())[:4]}"

                CashFlowTransaction.objects.create(
                    name=payment_name,
                    payment_type="receive",
                    category="Hoàn trả đối ứng chênh lệch hủy đơn",
                    payment_method="bank_transfer",
                    amount=abs(diff),
                    payment_date=timezone.now().date(),
                    purchase_order=order,
                    remarks=f"Tự động thu tiền chênh lệch khi hủy đơn mua {order.id} và giữ lại hàng (Giá trị hàng: {received_value:,.2f}đ, Đã thanh toán: {total_paid:,.2f}đ, Chênh lệch cần thu: {abs(diff):,.2f}đ).",
                )

            # Cập nhật advance_paid_amount trên PO để phục vụ cập nhật trạng thái tạm thời
            order.status = PurchaseOrder.Status.PENDING
            order.advance_paid_amount = received_value
            order.save()

            # Cập nhật hóa đơn đầu tiên sang PAID với tổng tiền bằng received_value. Hủy các hóa đơn khác (nếu có).
            invoices = list(order.invoices.select_for_update())
            if invoices:
                # Cập nhật hóa đơn đầu tiên về bằng giá trị hàng đã nhận thực tế và đánh dấu PAID
                first_invoice = invoices[0]
                first_invoice.total_amount = received_value
                first_invoice.paid_amount = received_value
                first_invoice.status = PurchaseInvoice.Status.PAID
                first_invoice.save()

                # Các hóa đơn khác hủy bỏ
                for invoice in invoices[1:]:
                    invoice.status = PurchaseInvoice.Status.CANCELLED
                    invoice.paid_amount = Decimal("0.00")
                    invoice.save()

            # Cập nhật các tỷ lệ nhận hàng/thanh toán trên PO
            purchase_order_update_status(order)

        else:
            # 2. Không giữ lại hàng: Trả hàng và hoàn trả tiền như bình thường (default logic)
            # a. Hủy các StockEntry nháp và đảo ngược các StockEntry posted (trả hàng)
            stock_entries = StockEntry.objects.select_for_update().filter(purchase_order=order)
            for entry in stock_entries:
                if entry.status == "draft":
                    stock_entry_cancel(user=user, stock_entry=entry)
                elif entry.status == "posted":
                    remarks_rev = f"Xuất kho trả hàng tự động do hủy đơn mua {order.id}"
                    stock_entry_reverse(user=user, original_entry=entry, remarks=remarks_rev)

            # b. Đảo ngược toàn bộ giao dịch dòng tiền gốc liên kết
            invoice_ids = list(order.invoices.values_list("id", flat=True))
            cash_flows = CashFlowTransaction.objects.select_for_update().filter(
                Q(purchase_order=order) | Q(purchase_invoice_id__in=invoice_ids)
            )
            for tx in cash_flows:
                if tx.category == "Hoàn trả thanh toán":
                    continue
                remarks_rev = f"Hoàn trả chi tiền tự động do hủy đơn mua {order.id} (Đối ứng cho giao dịch đặt cọc/thanh toán gốc {tx.name}, Số tiền hoàn: {tx.amount:,.2f}đ)."
                cash_flow_reverse(user=user, original_tx=tx, remarks=remarks_rev)

            # c. Hủy các Hóa đơn liên kết
            invoices = order.invoices.select_for_update()
            for invoice in invoices:
                invoice.status = PurchaseInvoice.Status.CANCELLED
                invoice.paid_amount = Decimal("0.00")
                invoice.save()

            # d. Reset tiền cọc trên PO
            order.advance_paid_amount = Decimal("0.00")

    # 5. Cập nhật Đơn hàng sang CANCELLED
    order.status = PurchaseOrder.Status.CANCELLED
    order.save()

    create_system_log(
        user=user,
        action="cancel",
        table_name="purchase_order",
        record_id=str(order.id),
        new_value={"status": order.status},
    )

    return order


@transaction.atomic
def verify_4_way_matching(*, invoice_id: str) -> bool:
    """
    Thực hiện quy trình đối soát 4 bên (4-Way Matching) cho Hóa đơn mua hàng (Purchase Invoice).
    - So khớp đơn giá từng dòng hóa đơn với đơn giá trên dòng Đơn mua hàng gốc (PO).
    - Kiểm tra kết quả kiểm định chất lượng (QA/QC) của từng sản phẩm.
    - So sánh ngày thực tế nhận hàng với ngày cam kết giao hàng của PO.
    - Tính toán tỷ lệ hoàn thành số lượng (%) cấp dòng và cấp tổng hóa đơn và lưu lại.
    - Ghi nhận chênh lệch vào block_reason làm thông tin rà soát cho người dùng,
      nhưng KHÔNG chặn thanh toán (trạng thái hóa đơn vẫn là unpaid/partial/paid).
    """
    from apps.finance.models import TechnicalCertification
    from apps.inventory.models import StockEntryDetail
    from apps.purchasing.models import PurchaseInvoice

    invoice = PurchaseInvoice.objects.select_for_update().filter(id=invoice_id).first()
    if not invoice:
        raise NotFoundException("Hóa đơn mua hàng không tồn tại.")

    po = invoice.order

    blocked = False
    reasons = []

    # Map PO lines for matching unit prices
    po_lines = {}
    if po:
        po_lines = {line.item_id: line for line in po.lines.all()}

    # Map Stock entry details for receiving quantities from all posted StockEntries for this PO
    received_qtys = {}
    if po:
        from django.db.models import Sum

        # DB-level group by item to avoid loop N+1 issues and memory overhead
        rows = (
            StockEntryDetail.objects.filter(parent__purchase_order=po, parent__status="posted")
            .values("item_id")
            .annotate(total_qty=Sum("quantity"))
        )
        for row in rows:
            received_qtys[row["item_id"]] = row["total_qty"]

    total_po_qty = Decimal("0.00")
    total_received_qty = Decimal("0.00")

    invoice_lines = list(invoice.lines.all())
    for line in invoice_lines:
        item = line.item
        item_id = item.id

        # a. Đơn giá
        if po:
            po_line = po_lines.get(item_id)
            if po_line:
                if line.unit_price != po_line.unit_price:
                    blocked = True
                    reasons.append(
                        f"Chênh lệch đơn giá dòng sản phẩm {item.item_code} (Hóa đơn: {line.unit_price:,.2f}đ, PO: {po_line.unit_price:,.2f}đ)"
                    )
            else:
                blocked = True
                reasons.append(f"Không tìm thấy dòng sản phẩm {item.item_code} tương ứng trên Đơn mua hàng gốc")

        # b. QA/QC check (Kiểm tra nếu có bất kỳ chứng nhận FAILED nào cho sản phẩm này trong các lô nhập kho của PO)
        if po:
            failed_certs = TechnicalCertification.objects.filter(
                item=item, stock_entry__purchase_order=po, result="FAILED"
            )
            if failed_certs.exists():
                blocked = True
                reasons.append(f"Sản phẩm {item.item_code} có lô hàng không đạt kiểm định chất lượng (QA/QC Failed)")

        # c. Tỷ lệ hoàn thành số lượng dòng (%)
        po_qty = Decimal("0.00")
        if po:
            po_line = po_lines.get(item_id)
            if po_line:
                po_qty = po_line.quantity

        if po_qty == 0:
            po_qty = line.quantity

        received_qty = received_qtys.get(item_id, Decimal("0.00"))

        total_po_qty += po_qty
        total_received_qty += received_qty

        if po_qty > 0:
            line_rate = (received_qty / po_qty) * Decimal("100.00")
        else:
            line_rate = Decimal("100.00")

        line_rate = line_rate.quantize(Decimal("0.01"))
        line.qty_fulfillment_rate = line_rate

    if invoice_lines:
        PurchaseInvoiceLine.objects.bulk_update(invoice_lines, ["qty_fulfillment_rate"])

    # d. Kiểm tra thời gian giao hàng trễ hạn
    if po and po.expected_delivery_date:
        late_entries = po.stock_entries.filter(status="posted", posting_date__date__gt=po.expected_delivery_date)
        if late_entries.exists():
            blocked = True
            reasons.append(f"Giao hàng trễ hạn ở các phiếu nhập kho: {', '.join(entry.name for entry in late_entries)}")

    # Calculate overall fulfillment rate
    if total_po_qty > 0:
        overall_rate = (total_received_qty / total_po_qty) * Decimal("100.00")
    else:
        overall_rate = Decimal("100.00")

    overall_rate = overall_rate.quantize(Decimal("0.01"))
    invoice.qty_fulfillment_rate = overall_rate

    # Update invoice status (Không gán trạng thái BLOCKED_FOR_PAYMENT)
    if reasons:
        invoice.block_reason = "; ".join(reasons)
    else:
        invoice.block_reason = None

    if invoice.paid_amount >= invoice.total_amount and invoice.total_amount > 0:
        invoice.status = PurchaseInvoice.Status.PAID
    elif invoice.paid_amount > 0:
        invoice.status = PurchaseInvoice.Status.PARTIAL
    else:
        invoice.status = PurchaseInvoice.Status.UNPAID

    invoice.save()

    if invoice.order:
        purchase_order_update_status(invoice.order)

    return not blocked


@transaction.atomic
def shipment_create(
    *,
    user: User,
    shipment_num: str,
    name: str,
    remarks: Optional[str] = None,
    stock_entry_ids: Optional[List[str]] = None,
) -> Shipment:
    """
    Tạo lô hàng (Shipment) mới và liên kết các StockEntry (phiếu nhập kho).
    """
    PermissionChecker.check_permission(user, "purchasing.allocate_landed_cost")

    if Shipment.objects.filter(shipment_num=shipment_num).exists():
        raise ValidationException(f"Mã lô hàng '{shipment_num}' đã tồn tại.")

    shipment = Shipment.objects.create(
        shipment_num=shipment_num,
        name=name,
        remarks=remarks,
        status="draft",
    )

    if stock_entry_ids:
        from apps.inventory.models import StockEntry

        stock_entries = StockEntry.objects.filter(id__in=stock_entry_ids)
        for entry in stock_entries:
            entry.shipment = shipment
            entry.save()

    create_system_log(
        user=user,
        action="create",
        table_name="shipment",
        record_id=str(shipment.id),
        new_value={"shipment_num": shipment_num, "status": shipment.status},
    )

    return shipment


@transaction.atomic
def record_shipment_logistic_fees(*, user: User, shipment_id: str, total_logistic_fees: Decimal) -> Shipment:
    """
    Ghi nhận chi phí logistic cho lô hàng.
    """
    PermissionChecker.check_permission(user, "purchasing.allocate_landed_cost")

    shipment = Shipment.objects.select_for_update().filter(id=shipment_id).first()
    if not shipment:
        raise NotFoundException("Lô hàng không tồn tại.")

    if total_logistic_fees <= 0:
        raise ValidationException("Chi phí logistic phải lớn hơn 0.")

    shipment.total_logistic_fees = total_logistic_fees
    shipment.status = "completed"
    shipment.save()

    # Tự động ghi nhận log dòng tiền cho chi phí logistic (nếu > 0)
    if total_logistic_fees > 0:
        from django.utils import timezone

        from apps.finance.models import CashFlowTransaction

        po = None
        first_se = shipment.stock_entries.filter(purchase_order__isnull=False).first()
        if first_se:
            po = first_se.purchase_order

        payment_name = f"CF-PAY-LOG-{shipment.shipment_num[:10]}-{str(uuid.uuid4())[:4]}"
        CashFlowTransaction.objects.create(
            name=payment_name,
            payment_type="pay",
            category="Chi phí vận chuyển lô hàng",
            payment_method="bank_transfer",
            amount=total_logistic_fees,
            payment_date=timezone.now().date(),
            purchase_order=po,
            remarks=f"Thanh toán chi phí logistic dồn tích cho Lô Hàng {shipment.shipment_num} (Tên hồ sơ: {shipment.name}).",
        )

    create_system_log(
        user=user,
        action="update",
        table_name="shipment",
        record_id=str(shipment.id),
        new_value={
            "status": shipment.status,
            "total_logistic_fees": str(total_logistic_fees),
            "accounting_entry": f"[Hạch toán] Nợ TK 152 (Chi phí mua hàng dồn tích) / Có TK 331 (Phải trả người bán - Chi phí vận chuyển): {total_logistic_fees:,.2f}đ",
        },
    )

    return shipment


@transaction.atomic
def technical_certification_create(
    *,
    user: User,
    item_id: str,
    stock_entry_id: str,
    cert_type: str,
    assessment_fee: Optional[Decimal] = None,
    expiry_date: Optional[str] = None,
    result: str,
    remarks: Optional[str] = None,
) -> Any:
    PermissionChecker.check_permission(user, "purchasing.manage_qc")

    import uuid

    from apps.finance.models import TechnicalCertification
    from apps.inventory.models import StockEntry
    from apps.master_data.models import Item

    stock_entry = StockEntry.objects.select_for_update().filter(id=stock_entry_id).first()
    if not stock_entry:
        raise NotFoundException("Phiếu nhập kho không tồn tại")

    shipment = stock_entry.shipment
    if not shipment:
        raise ValidationException(
            "Phiếu nhập kho chưa được liên kết với bất kỳ Lô hàng nào. Vui lòng lập Lô hàng trước khi thực hiện QC."
        )

    if shipment.status == "draft":
        raise ValidationException(
            "Lô hàng chưa cập bến thực tế (đang ở trạng thái Draft). Không được phép thực hiện kiểm định QA/QC sớm."
        )

    item = Item.objects.filter(id=item_id).first()
    if not item:
        raise NotFoundException("Sản phẩm không tồn tại")

    cert_id = f"CERT-{str(uuid.uuid4())[:8].upper()}"
    cert = TechnicalCertification.objects.create(
        cert_id=cert_id,
        item=item,
        stock_entry=stock_entry,
        cert_type=cert_type,
        assessment_fee=assessment_fee,
        expiry_date=expiry_date,
        result=result,
        remarks=remarks,
    )

    create_system_log(
        user=user,
        action="create",
        table_name="technical_certification",
        record_id=str(cert.id),
        new_value={
            "cert_id": cert_id,
            "item_id": str(item.id),
            "stock_entry_id": str(stock_entry.id),
            "cert_type": cert_type,
            "result": result,
        },
    )

    from apps.purchasing.models import PurchaseInvoice
    from apps.purchasing.services import verify_4_way_matching

    invoices = PurchaseInvoice.objects.filter(stock_entry=stock_entry).exclude(
        status__in=[PurchaseInvoice.Status.PAID, PurchaseInvoice.Status.CANCELLED]
    )
    for invoice in invoices:
        verify_4_way_matching(invoice_id=str(invoice.id))

    return cert


@transaction.atomic
def shipment_update(
    *,
    user: User,
    shipment_id: str,
    status: Optional[str] = None,
    remarks: Optional[str] = None,
) -> Shipment:
    PermissionChecker.check_permission(user, "purchasing.allocate_landed_cost")
    from apps.purchasing.models import Shipment

    shipment = Shipment.objects.select_for_update().filter(id=shipment_id).first()
    if not shipment:
        raise NotFoundException("Lô hàng không tồn tại")

    old_status = shipment.status
    old_remarks = shipment.remarks

    if status and status != shipment.status:
        if status not in Shipment.Status.values:
            raise ValidationException(f"Trạng thái {status} không hợp lệ.")

        valid_transitions = {
            Shipment.Status.DRAFT: [Shipment.Status.ARRIVED],
            Shipment.Status.ARRIVED: [Shipment.Status.DRAFT, Shipment.Status.INSPECTED],
            Shipment.Status.INSPECTED: [Shipment.Status.ARRIVED, Shipment.Status.COMPLETED],
            Shipment.Status.COMPLETED: [Shipment.Status.INSPECTED],
        }
        allowed = valid_transitions.get(shipment.status, [])
        if status not in allowed:
            raise ValidationException(f"Không thể chuyển trạng thái lô hàng từ '{shipment.status}' sang '{status}'.")
        shipment.status = status

    if remarks is not None:
        shipment.remarks = remarks

    shipment.save()

    create_system_log(
        user=user,
        action="update",
        table_name="shipment",
        record_id=str(shipment.id),
        old_value={"status": old_status, "remarks": old_remarks},
        new_value={"status": shipment.status, "remarks": shipment.remarks},
    )
    return shipment
