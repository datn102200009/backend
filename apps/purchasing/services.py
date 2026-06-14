"""
Services for purchasing app.

All write operations for Purchase Orders and Purchase Invoices.
"""

import logging
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

logger = logging.getLogger(__name__)


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

    orig_advance_paid_amount = order.advance_paid_amount
    order.advance_paid_amount = Decimal("0.00")
    order.save()

    # Tự động ghi nhận dòng tiền cọc (Chi tiền cọc) nếu có cọc và chưa có dòng tiền cọc
    if orig_advance_paid_amount > 0:
        if not order.cash_flows.filter(payment_type="pay").exists():
            from apps.finance.models import CashFlowTransaction

            payment_name = f"CF-PAY-DEP-{str(order.id)[:8]}-{str(uuid.uuid4())[:4]}"
            CashFlowTransaction.objects.create(
                name=payment_name,
                payment_type="pay",
                category="Đặt cọc đơn hàng",
                payment_method="bank_transfer",
                amount=orig_advance_paid_amount,
                payment_date=order.updated_at.date(),
                purchase_order=order,
                status="pending_approval",
                remarks=f"Tự động chi tiền cọc cho đơn mua hàng {order.id} (Nhà cung cấp: {order.vendor.supplier_name}, Tổng giá trị đơn: {order.total_amount:,.2f}đ, Số tiền cọc: {orig_advance_paid_amount:,.2f}đ).",
            )

    # 2. Tạo Hóa đơn mua hàng (Purchase Invoice)
    invoice = PurchaseInvoice.objects.create(
        order=order,
        stock_entry=None,  # Sẽ được gán khi hoàn tất lô hàng (shipment_complete)
        vendor=order.vendor,
        status=PurchaseInvoice.Status.UNPAID,
        total_amount=order.total_amount,
        paid_amount=Decimal("0.00"),
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

    # 3. Kích hoạt cập nhật lại trạng thái dựa trên thanh toán ứng trước (nếu có)
    purchase_order_update_status(order)

    create_system_log(
        user=user,
        action="approve",
        table_name="purchase_order",
        record_id=str(order.id),
        new_value={"status": order.status, "invoice_id": str(invoice.id)},
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
    created_cfs = []

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
                rev_tx = cash_flow_reverse(user=user, original_tx=tx, remarks=remarks_rev)
                created_cfs.append(rev_tx)

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

                diff_tx = CashFlowTransaction.objects.create(
                    name=payment_name,
                    payment_type="pay",
                    category="Thanh toán đối ứng chênh lệch hủy đơn",
                    payment_method="bank_transfer",
                    amount=diff,
                    payment_date=timezone.now().date(),
                    purchase_order=order,
                    status="pending_approval",
                    remarks=f"Tự động chi tiền chênh lệch khi hủy đơn mua {order.id} và giữ lại hàng (Giá trị hàng: {received_value:,.2f}đ, Đã thanh toán: {total_paid:,.2f}đ, Chênh lệch cần chi: {diff:,.2f}đ).",
                )
                created_cfs.append(diff_tx)
            elif diff < 0:
                # Giá trị hàng nhận nhỏ hơn số tiền đã trả -> tạo phiếu THU (receive) để thu hồi tiền chênh lệch từ nhà cung cấp
                import uuid

                from django.utils import timezone

                payment_name = f"CF-REC-DIFF-{str(order.id)[:8]}-{str(uuid.uuid4())[:4]}"

                diff_tx = CashFlowTransaction.objects.create(
                    name=payment_name,
                    payment_type="receive",
                    category="Hoàn trả đối ứng chênh lệch hủy đơn",
                    payment_method="bank_transfer",
                    amount=abs(diff),
                    payment_date=timezone.now().date(),
                    purchase_order=order,
                    status="pending_approval",
                    remarks=f"Tự động thu tiền chênh lệch khi hủy đơn mua {order.id} và giữ lại hàng (Giá trị hàng: {received_value:,.2f}đ, Đã thanh toán: {total_paid:,.2f}đ, Chênh lệch cần thu: {abs(diff):,.2f}đ).",
                )
                created_cfs.append(diff_tx)

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
                rev_tx = cash_flow_reverse(user=user, original_tx=tx, remarks=remarks_rev)
                created_cfs.append(rev_tx)

            # c. Hủy các Hóa đơn liên kết
            invoices = order.invoices.select_for_update()
            for invoice in invoices:
                invoice.status = PurchaseInvoice.Status.CANCELLED
                invoice.paid_amount = Decimal("0.00")
                invoice.save()

            # d. Reset tiền cọc trên PO
            order.advance_paid_amount = Decimal("0.00")

    # 5. Cập nhật Đơn hàng sang CANCEL_PENDING hoặc CANCELLED
    if created_cfs:
        order.status = PurchaseOrder.Status.CANCEL_PENDING
    else:
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
            Shipment.Status.DRAFT: [Shipment.Status.INSPECTING],
            Shipment.Status.INSPECTING: [Shipment.Status.COMPLETED],
            Shipment.Status.COMPLETED: [],
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


@transaction.atomic
def shipment_create_from_po(
    *,
    user: User,
    shipment_num: str,
    name: str,
    purchase_order_id: str,
    remarks: Optional[str] = None,
) -> Shipment:
    PermissionChecker.check_permission(user, "purchasing.allocate_landed_cost")
    from apps.purchasing.models import PurchaseOrder, Shipment

    po = PurchaseOrder.objects.select_for_update().filter(id=purchase_order_id).first()
    if not po:
        raise NotFoundException("Đơn mua hàng không tồn tại.")

    if po.status not in [PurchaseOrder.Status.PENDING, PurchaseOrder.Status.PAID_UNSHIPPED]:
        raise ValidationException("Chỉ có thể tạo lô hàng cho PO ở trạng thái chờ xử lý hoặc đã thanh toán.")

    existing = Shipment.objects.filter(
        purchase_order=po, status__in=[Shipment.Status.DRAFT, Shipment.Status.INSPECTING]
    ).exists()
    if existing:
        raise ValidationException("PO này đã có lô hàng đang xử lý.")

    if Shipment.objects.filter(shipment_num=shipment_num).exists():
        raise ValidationException("Mã lô hàng đã tồn tại.")

    shipment = Shipment.objects.create(
        shipment_num=shipment_num,
        name=name,
        purchase_order=po,
        status=Shipment.Status.DRAFT,
        remarks=remarks,
        total_logistic_fees=Decimal("0.00"),
    )

    create_system_log(
        user=user,
        action="create",
        table_name="shipment",
        record_id=str(shipment.id),
        new_value={"shipment_num": shipment_num, "status": shipment.status, "purchase_order_id": str(po.id)},
    )
    return shipment


@transaction.atomic
def shipment_complete(
    *,
    user: User,
    shipment_id: str,
    details: list,
    total_logistic_fees: Decimal,
) -> Shipment:
    PermissionChecker.check_permission(user, "purchasing.allocate_landed_cost")
    import uuid

    from django.db.models import Sum
    from django.utils import timezone

    from apps.finance.models import CashFlowTransaction
    from apps.inventory.models import StockEntry, StockEntryDetail, StockLedger
    from apps.purchasing.models import PurchaseInvoice, PurchaseInvoiceLine, Shipment

    shipment = Shipment.objects.select_for_update().filter(id=shipment_id).first()
    if not shipment:
        logger.warning("shipment_complete: shipment_id=%s not found", shipment_id)
        raise NotFoundException("Lô hàng không tồn tại.")

    logger.info(
        "shipment_complete: start shipment_id=%s status=%s",
        shipment.id,
        shipment.status,
        extra={"shipment_id": str(shipment.id), "user_id": str(user.id)},
    )

    if shipment.status != Shipment.Status.INSPECTING:
        logger.warning(
            "shipment_complete: invalid status transition shipment_id=%s status=%s",
            shipment.id,
            shipment.status,
        )
        raise ValidationException("Chỉ có thể hoàn tất lô hàng đang ở trạng thái Đang tiếp nhận.")

    po = shipment.purchase_order
    if not po:
        logger.warning("shipment_complete: shipment_id=%s is not linked to any PO", shipment.id)
        raise ValidationException("Lô hàng chưa liên kết PO.")

    if total_logistic_fees < 0:
        raise ValidationException("Chi phí logistic không được âm.")

    # Tính trước tổng đã nhập cho toàn bộ các dòng trong PO
    already_received_map: dict[str, Decimal] = {}
    received_rows = (
        StockEntryDetail.objects.filter(parent__purchase_order=po, parent__status="posted")
        .values("item_id")
        .annotate(total_qty=Sum("quantity"))
    )
    for row in received_rows:
        already_received_map[str(row["item_id"])] = row["total_qty"] or Decimal("0.00")

    # Validate details
    for d in details:
        qty = Decimal(str(d["quantity"]))
        if qty < 0:
            raise ValidationException("Số lượng đạt chuẩn không được âm.")

        po_line = po.lines.filter(id=d["po_line_id"]).first()
        if not po_line:
            raise ValidationException("Dòng sản phẩm không khớp với PO.")

        if qty > po_line.quantity:
            raise ValidationException(
                f"Số lượng nhận ({qty}) vượt quá số lượng đặt ({po_line.quantity}) cho sản phẩm {po_line.item.item_code}."
            )

        already_received = already_received_map.get(str(d["item_id"]), Decimal("0.00"))
        if already_received + qty > po_line.quantity:
            raise ValidationException(
                f"Tổng SL đã nhập ({already_received}) + SL lần này ({qty}) "
                f"vượt quá SL đặt ({po_line.quantity}) cho sản phẩm {po_line.item.item_code}."
            )

        if qty == 0:
            d["target_warehouse_id"] = None
        elif qty > 0 and not d.get("target_warehouse_id"):
            raise ValidationException(f"Sản phẩm {po_line.item.item_code} có số lượng nhận >0 phải chỉ định kho.")

    # Bước 1: Tạo StockEntry posted trực tiếp
    try:
        stock_name = f"IN-PUR-SHIP-{str(shipment.id)[:8].upper()}-{str(uuid.uuid4())[:4]}"
        stock_entry = StockEntry.objects.create(
            name=stock_name,
            purpose="receipt",
            posting_date=timezone.now(),
            remarks=f"Nhập kho từ lô hàng {shipment.shipment_num}",
            status="posted",
            purchase_order=po,
            shipment=shipment,
        )
        logger.info(
            "shipment_complete: created StockEntry id=%s name=%s",
            stock_entry.id,
            stock_name,
            extra={"shipment_id": str(shipment.id), "stock_entry_id": str(stock_entry.id)},
        )
    except Exception:
        logger.exception("shipment_complete: failed to create StockEntry for shipment_id=%s", shipment.id)
        raise

    for d in details:
        qty = Decimal(str(d["quantity"]))
        if qty > 0:
            try:
                StockEntryDetail.objects.create(
                    parent=stock_entry,
                    item_id=d["item_id"],
                    quantity=qty,
                    target_warehouse_id=d["target_warehouse_id"],
                )
                StockLedger.objects.create(
                    item_id=d["item_id"],
                    warehouse_id=d["target_warehouse_id"],
                    posting_date=stock_entry.posting_date,
                    actual_quantity=qty,
                    voucher_number=stock_entry.name,
                    voucher_type="Stock In",
                )
            except Exception:
                logger.exception(
                    "shipment_complete: failed to create StockEntryDetail/Ledger item_id=%s qty=%s",
                    d.get("item_id"),
                    qty,
                )
                raise

    logger.info(
        "shipment_complete: created StockEntryDetails for shipment_id=%s",
        shipment.id,
    )

    # Bước 2: Cập nhật PurchaseInvoice liên kết với StockEntry
    updated_invoices = PurchaseInvoice.objects.filter(order=po, stock_entry__isnull=True).update(
        stock_entry=stock_entry
    )
    logger.info(
        "shipment_complete: linked %d PurchaseInvoices to StockEntry %s",
        updated_invoices,
        stock_entry.id,
    )

    # Bước 3: Tạo CashFlowTransaction cho chi phí logistic
    if total_logistic_fees > 0:
        try:
            cf = CashFlowTransaction.objects.create(
                name=f"CF-PAY-LOG-{shipment.shipment_num[:10]}-{str(uuid.uuid4())[:4]}",
                payment_type="pay",
                category="Chi phí vận chuyển lô hàng",
                payment_method="bank_transfer",
                amount=total_logistic_fees,
                payment_date=timezone.now().date(),
                purchase_order=po,
                status="pending_approval",
                remarks=f"Thanh toán chi phí logistic dồn tích cho Lô Hàng {shipment.shipment_num}",
            )
            logger.info(
                "shipment_complete: created CashFlow id=%s amount=%s for shipment_id=%s",
                cf.id,
                total_logistic_fees,
                shipment.id,
            )
        except Exception:
            logger.exception("shipment_complete: failed to create CashFlow for shipment_id=%s", shipment.id)
            raise

    # Bước 4: Cập nhật Shipment status
    shipment.status = Shipment.Status.COMPLETED
    shipment.total_logistic_fees = total_logistic_fees
    shipment.save()

    # Bước 5: Cập nhật PO status
    purchase_order_update_status(po)

    logger.info(
        "shipment_complete: completed shipment_id=%s total_logistic_fees=%s",
        shipment.id,
        total_logistic_fees,
    )

    create_system_log(
        user=user,
        action="update",
        table_name="shipment",
        record_id=str(shipment.id),
        new_value={
            "status": shipment.status,
            "total_logistic_fees": str(total_logistic_fees),
            "stock_entry_id": str(stock_entry.id),
        },
    )
    return shipment
