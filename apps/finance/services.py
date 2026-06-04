"""
Services for finance app.

All write operations (Create, Update, Delete) should be defined here.
Never receive request objects, only primitive types or DTOs.
Always ensure atomic transactions.
"""

from decimal import Decimal
from typing import Optional

from django.db import transaction

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.finance.models import CashFlowTransaction


@transaction.atomic
def cash_flow_create(
    *,
    user: User,
    payment_type: str,
    amount: Decimal,
    payment_date: str,
    category: Optional[str] = None,
    payment_method: str = "bank_transfer",
    purchase_order_id: Optional[str] = None,
    sales_order_id: Optional[str] = None,
    purchase_invoice_id: Optional[str] = None,
    sales_invoice_id: Optional[str] = None,
    remarks: Optional[str] = None,
) -> CashFlowTransaction:
    """
    Ghi nhận Phiếu dòng tiền (CashFlowTransaction).
    Có thể hoạt động độc lập hoặc tham chiếu tới Đơn hàng / Hóa đơn.
    """
    PermissionChecker.check_permission(user, "finance.create_cash_flow")

    # 1. Khởi tạo đối tượng Cash Flow
    import uuid

    payment_name = f"CF-{payment_type.upper()}-{str(uuid.uuid4())[:8]}"

    transaction_obj = CashFlowTransaction(
        name=payment_name,
        payment_type=payment_type,
        amount=amount,
        payment_date=payment_date,
        category=category,
        payment_method=payment_method,
        remarks=remarks,
    )

    # 2. Xử lý tham chiếu chéo (Cross-update)
    from apps.purchasing.models import PurchaseInvoice, PurchaseOrder
    from apps.sales.models import SalesInvoice, SalesOrder

    # -- Tham chiếu: Purchase Order --
    if purchase_order_id:
        po = PurchaseOrder.objects.select_for_update().filter(id=purchase_order_id).first()
        if not po:
            raise NotFoundException("Đơn mua hàng tham chiếu không tồn tại.")
        if po.status in [PurchaseOrder.Status.COMPLETED, PurchaseOrder.Status.CANCELLED]:
            raise ValidationException("Không thể nhận thêm cọc/ứng trước cho đơn hàng đã hoàn tất hoặc đã hủy.")

        if po.advance_paid_amount + amount > po.total_amount:
            raise ValidationException("Số tiền thanh toán vượt quá giá trị đơn mua hàng.")

        transaction_obj.purchase_order = po
        po.advance_paid_amount += amount
        po.save()

        # Cập nhật trạng thái Đơn hàng
        from apps.purchasing.services import purchase_order_update_status

        purchase_order_update_status(po)

    # -- Tham chiếu: Sales Order --
    if sales_order_id:
        so = SalesOrder.objects.select_for_update().filter(id=sales_order_id).first()
        if not so:
            raise NotFoundException("Đơn bán hàng tham chiếu không tồn tại.")
        if so.status in [SalesOrder.Status.COMPLETED, SalesOrder.Status.CANCELLED]:
            raise ValidationException("Không thể nhận thêm cọc cho đơn hàng đã hoàn tất hoặc đã hủy.")

        if so.advance_paid_amount + amount > so.total_amount:
            raise ValidationException("Số tiền thanh toán vượt quá giá trị đơn bán hàng.")

        transaction_obj.sales_order = so
        so.advance_paid_amount += amount
        so.save()

        # Cập nhật trạng thái Đơn hàng
        from apps.sales.services import sales_order_update_status

        sales_order_update_status(so)

    # -- Tham chiếu: Purchase Invoice --
    if purchase_invoice_id:
        pi = PurchaseInvoice.objects.select_for_update().filter(id=purchase_invoice_id).first()
        if not pi:
            raise NotFoundException("Hóa đơn mua hàng tham chiếu không tồn tại.")
        if pi.status in [PurchaseInvoice.Status.PAID, PurchaseInvoice.Status.CANCELLED]:
            raise ValidationException("Hóa đơn mua không hợp lệ hoặc đã hoàn tất thanh toán.")

        if pi.paid_amount + amount > pi.total_amount:
            raise ValidationException("Số tiền thanh toán vượt quá giá trị hóa đơn mua.")

        transaction_obj.purchase_invoice = pi
        pi.paid_amount += amount

        if pi.paid_amount >= pi.total_amount:
            pi.status = PurchaseInvoice.Status.PAID
        else:
            pi.status = PurchaseInvoice.Status.PARTIAL
        pi.save()

        # Cập nhật trạng thái Đơn hàng gốc liên kết
        if pi.order:
            from apps.purchasing.services import purchase_order_update_status

            purchase_order_update_status(pi.order)

    # -- Tham chiếu: Sales Invoice --
    if sales_invoice_id:
        si = SalesInvoice.objects.select_for_update().filter(id=sales_invoice_id).first()
        if not si:
            raise NotFoundException("Hóa đơn bán hàng tham chiếu không tồn tại.")
        if si.status in [SalesInvoice.Status.PAID, SalesInvoice.Status.CANCELLED]:
            raise ValidationException("Hóa đơn bán không hợp lệ hoặc đã hoàn tất thanh toán.")

        if si.paid_amount + amount > si.total_amount:
            raise ValidationException("Số tiền thanh toán vượt quá giá trị hóa đơn bán.")

        transaction_obj.sales_invoice = si
        si.paid_amount += amount

        if si.paid_amount >= si.total_amount:
            si.status = SalesInvoice.Status.PAID
        else:
            si.status = SalesInvoice.Status.PARTIAL
        si.save()

        # Cập nhật trạng thái Đơn hàng gốc liên kết
        if si.order:
            from apps.sales.services import sales_order_update_status

            sales_order_update_status(si.order)

    transaction_obj.save()

    create_system_log(
        user=user,
        action="create",
        table_name="cash_flow_transaction",
        record_id=str(transaction_obj.id),
        new_value={"type": payment_type, "amount": str(amount)},
    )

    return transaction_obj


@transaction.atomic
def cash_flow_reverse(
    *,
    user: User,
    original_tx: CashFlowTransaction,
    remarks: str,
) -> CashFlowTransaction:
    """
    Tạo một giao dịch dòng tiền đảo ngược (đối ứng) cho giao dịch dòng tiền gốc.
    """
    PermissionChecker.check_permission(user, "finance.create_cash_flow")

    import datetime
    import uuid

    reverse_payment_type = "receive" if original_tx.payment_type == "pay" else "pay"
    payment_name = f"CF-REV-{reverse_payment_type.upper()}-{str(uuid.uuid4())[:8]}"

    reverse_tx = CashFlowTransaction(
        name=payment_name,
        payment_type=reverse_payment_type,
        amount=original_tx.amount,
        payment_date=datetime.date.today(),
        category="Hoàn trả thanh toán",
        payment_method=original_tx.payment_method,
        purchase_order=original_tx.purchase_order,
        sales_order=original_tx.sales_order,
        purchase_invoice=original_tx.purchase_invoice,
        sales_invoice=original_tx.sales_invoice,
        remarks=remarks,
    )
    reverse_tx.save()

    create_system_log(
        user=user,
        action="create",
        table_name="cash_flow_transaction",
        record_id=str(reverse_tx.id),
        new_value={
            "type": reverse_payment_type,
            "amount": str(original_tx.amount),
            "is_reversal": True,
            "original_tx_id": str(original_tx.id),
        },
    )

    return reverse_tx
