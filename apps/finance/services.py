"""
Services for finance app.

All write operations (Create, Update, Delete) should be defined here.
Never receive request objects, only primitive types or DTOs.
Always ensure atomic transactions.

ARCHITECTURE NOTE (2026-06):
collect_sales_invoice và pay_purchase_invoice thao tác trên SalesInvoice/PurchaseInvoice
của apps.sales/apps.purchasing. Xem apps/finance/selectors.py để biết lý do và quy ước.
"""

import datetime
import re
from decimal import Decimal
from typing import Any, Optional

from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.finance.models import CashFlowTransaction, FixedAsset, FixedAssetDepreciationLog
from apps.inventory.models import StockEntryDetail
from apps.master_data.models import BOM


def _apply_cash_flow_effect(tx: CashFlowTransaction, amount: Decimal):
    from apps.purchasing.models import PurchaseInvoice, PurchaseOrder
    from apps.purchasing.services import purchase_order_update_status
    from apps.sales.models import SalesInvoice, SalesOrder
    from apps.sales.services import sales_order_update_status

    if tx.purchase_order_id:
        po = PurchaseOrder.objects.select_for_update().filter(id=tx.purchase_order_id).first()
        if not po:
            raise NotFoundException("Đơn mua hàng tham chiếu không tồn tại.")

        if po.status == PurchaseOrder.Status.CANCEL_PENDING:
            po.status = PurchaseOrder.Status.CANCELLED
            po.save()
            return
        elif po.status == PurchaseOrder.Status.CANCELLED:
            return

        if po.status == PurchaseOrder.Status.COMPLETED:
            raise ValidationException("Không thể nhận thêm cọc/ứng trước cho đơn hàng đã hoàn tất.")

        if po.advance_paid_amount + amount > po.total_amount:
            raise ValidationException("Số tiền thanh toán vượt quá giá trị đơn mua hàng.")
        po.advance_paid_amount += amount
        po.save()

        # Approved cash flows on PO will automatically credit the linked Purchase Invoice's paid_amount
        pi = po.invoices.exclude(status=PurchaseInvoice.Status.CANCELLED).first()
        if pi:
            if pi.paid_amount + amount > pi.total_amount:
                raise ValidationException("Số tiền thanh toán vượt quá giá trị hóa đơn mua.")
            pi.paid_amount += amount
            if pi.paid_amount >= pi.total_amount:
                pi.status = PurchaseInvoice.Status.PAID
            else:
                pi.status = PurchaseInvoice.Status.PARTIAL
            pi.save()

        purchase_order_update_status(po)

    elif tx.sales_order_id:
        so = SalesOrder.objects.select_for_update().filter(id=tx.sales_order_id).first()
        if not so:
            raise NotFoundException("Đơn bán hàng tham chiếu không tồn tại.")

        if so.status == SalesOrder.Status.CANCEL_PENDING:
            so.status = SalesOrder.Status.CANCELLED
            so.save()
            return
        elif so.status == SalesOrder.Status.CANCELLED:
            return

        if so.status == SalesOrder.Status.COMPLETED:
            raise ValidationException("Không thể nhận thêm cọc cho đơn hàng đã hoàn tất.")

        if so.advance_paid_amount + amount > so.total_amount:
            raise ValidationException("Số tiền thanh toán vượt quá giá trị đơn bán hàng.")
        so.advance_paid_amount += amount
        so.save()

        # Approved cash flows on SO will automatically credit the linked Sales Invoice's paid_amount
        si = so.invoices.exclude(status=SalesInvoice.Status.CANCELLED).first()
        if si:
            if si.paid_amount + amount > si.total_amount:
                raise ValidationException("Số tiền thanh toán vượt quá giá trị hóa đơn bán.")
            si.paid_amount += amount
            if si.paid_amount >= si.total_amount:
                si.status = SalesInvoice.Status.PAID
            else:
                si.status = SalesInvoice.Status.PARTIAL
            si.save()

        sales_order_update_status(so)

    elif tx.purchase_invoice_id:
        pi = PurchaseInvoice.objects.select_for_update().filter(id=tx.purchase_invoice_id).first()
        if not pi:
            raise NotFoundException("Hóa đơn mua hàng tham chiếu không tồn tại.")
        if pi.status in [PurchaseInvoice.Status.PAID, PurchaseInvoice.Status.CANCELLED]:
            raise ValidationException("Hóa đơn mua không hợp lệ hoặc đã hoàn tất thanh toán.")
        if pi.paid_amount + amount > pi.total_amount:
            raise ValidationException("Số tiền thanh toán vượt quá giá trị hóa đơn mua.")
        pi.paid_amount += amount
        if pi.paid_amount >= pi.total_amount:
            pi.status = PurchaseInvoice.Status.PAID
        else:
            pi.status = PurchaseInvoice.Status.PARTIAL
        pi.save()
        if pi.order:
            purchase_order_update_status(pi.order)

    elif tx.sales_invoice_id:
        si = SalesInvoice.objects.select_for_update().filter(id=tx.sales_invoice_id).first()
        if not si:
            raise NotFoundException("Hóa đơn bán hàng tham chiếu không tồn tại.")
        if si.status in [SalesInvoice.Status.PAID, SalesInvoice.Status.CANCELLED]:
            raise ValidationException("Hóa đơn bán không hợp lệ hoặc đã hoàn tất thanh toán.")
        if si.paid_amount + amount > si.total_amount:
            raise ValidationException("Số tiền thanh toán vượt quá giá trị hóa đơn bán.")
        si.paid_amount += amount
        if si.paid_amount >= si.total_amount:
            si.status = SalesInvoice.Status.PAID
        else:
            si.status = SalesInvoice.Status.PARTIAL
        si.save()
        if si.order:
            sales_order_update_status(si.order)


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

    if not any([purchase_order_id, sales_order_id, purchase_invoice_id, sales_invoice_id]):
        raise ValidationException(
            "Phiếu dòng tiền bắt buộc phải tham chiếu tới ít nhất một chứng từ (Đơn hàng hoặc Hóa đơn)."
        )

    if payment_type not in ["pay", "receive"]:
        raise ValidationException("Loại thanh toán phải là 'pay' hoặc 'receive'.")

    if amount <= Decimal("0.00"):
        raise ValidationException("Số tiền thanh toán phải lớn hơn 0.")

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

    # Gán các đối tượng tham chiếu và kiểm tra tính hợp lệ ban đầu
    if purchase_order_id:
        po = PurchaseOrder.objects.filter(id=purchase_order_id).first()
        if not po:
            raise NotFoundException("Đơn mua hàng tham chiếu không tồn tại.")
        if po.status in [PurchaseOrder.Status.COMPLETED, PurchaseOrder.Status.CANCELLED]:
            raise ValidationException("Không thể nhận thêm cọc/ứng trước cho đơn hàng đã hoàn tất hoặc đã hủy.")
        if po.advance_paid_amount + amount > po.total_amount:
            raise ValidationException("Số tiền thanh toán vượt quá giá trị đơn mua hàng.")
        transaction_obj.purchase_order = po

    elif sales_order_id:
        so = SalesOrder.objects.filter(id=sales_order_id).first()
        if not so:
            raise NotFoundException("Đơn bán hàng tham chiếu không tồn tại.")
        if so.status in [SalesOrder.Status.COMPLETED, SalesOrder.Status.CANCELLED]:
            raise ValidationException("Không thể nhận thêm cọc cho đơn hàng đã hoàn tất hoặc đã hủy.")
        if so.advance_paid_amount + amount > so.total_amount:
            raise ValidationException("Số tiền thanh toán vượt quá giá trị đơn bán hàng.")
        transaction_obj.sales_order = so

    elif purchase_invoice_id:
        pi = PurchaseInvoice.objects.filter(id=purchase_invoice_id).first()
        if not pi:
            raise NotFoundException("Hóa đơn mua hàng tham chiếu không tồn tại.")
        if pi.status in [PurchaseInvoice.Status.PAID, PurchaseInvoice.Status.CANCELLED]:
            raise ValidationException("Hóa đơn mua không hợp lệ hoặc đã hoàn tất thanh toán.")
        if pi.paid_amount + amount > pi.total_amount:
            raise ValidationException("Số tiền thanh toán vượt quá giá trị hóa đơn mua.")
        transaction_obj.purchase_invoice = pi
        if pi.order:
            transaction_obj.purchase_order = pi.order

    elif sales_invoice_id:
        si = SalesInvoice.objects.filter(id=sales_invoice_id).first()
        if not si:
            raise NotFoundException("Hóa đơn bán hàng tham chiếu không tồn tại.")
        if si.status in [SalesInvoice.Status.PAID, SalesInvoice.Status.CANCELLED]:
            raise ValidationException("Hóa đơn bán không hợp lệ hoặc đã hoàn tất thanh toán.")
        if si.paid_amount + amount > si.total_amount:
            raise ValidationException("Số tiền thanh toán vượt quá giá trị hóa đơn bán.")
        transaction_obj.sales_invoice = si
        if si.order:
            transaction_obj.sales_order = si.order

    transaction_obj.status = "pending_approval"
    transaction_obj.save()

    create_system_log(
        user=user,
        action="create",
        table_name="cash_flow_transaction",
        record_id=str(transaction_obj.id),
        new_value={"type": payment_type, "amount": str(amount), "status": transaction_obj.status},
    )

    return transaction_obj


@transaction.atomic
def cash_flow_approve(*, user: User, tx_id: str) -> CashFlowTransaction:
    """
    Phê duyệt Phiếu chi dòng tiền (CFO/Admin).
    Chuyển trạng thái sang posted và thực hiện cập nhật công nợ/ứng trước.
    """
    PermissionChecker.check_permission(user, "finance.approve_cash_flow")

    tx = CashFlowTransaction.objects.select_for_update().filter(id=tx_id).first()
    if not tx:
        raise NotFoundException("Phiếu chi dòng tiền không tồn tại.")

    if tx.status != "pending_approval":
        raise ValidationException("Chỉ có thể phê duyệt phiếu chi ở trạng thái Chờ duyệt.")

    # Kích hoạt cập nhật công nợ/ứng trước của Hóa đơn/Đơn hàng liên quan
    if not tx.fixed_asset_id:
        _apply_cash_flow_effect(tx, tx.amount)

    tx.status = "posted"
    tx.approved_by = user
    tx.approved_at = timezone.now()
    tx.save()

    if tx.fixed_asset_id:
        asset = tx.fixed_asset
        if tx.payment_type == "pay":
            if asset.status == "pending_receive":
                asset.status = "idle"
                if not asset.purchase_date:
                    asset.purchase_date = tx.payment_date
                asset.save()
                create_system_log(
                    user=user,
                    action="auto_activate",
                    table_name="fixed_asset",
                    record_id=str(asset.id),
                    new_value={"status": "idle", "purchase_date": str(asset.purchase_date)},
                )
            else:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Hook auto_activate skip: asset {asset.id} status is {asset.status}, expected pending_receive"
                )
        elif tx.payment_type == "receive":
            if asset.status == "pending_dispose":
                asset.status = "disposed"
                if not asset.disposal_date:
                    asset.disposal_date = tx.payment_date
                asset.save()
                create_system_log(
                    user=user,
                    action="auto_dispose",
                    table_name="fixed_asset",
                    record_id=str(asset.id),
                    new_value={"status": "disposed", "disposal_date": str(asset.disposal_date)},
                )
            else:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Hook auto_dispose skip: asset {asset.id} status is {asset.status}, expected pending_dispose"
                )

    create_system_log(
        user=user,
        action="approve",
        table_name="cash_flow_transaction",
        record_id=str(tx.id),
        new_value={"status": tx.status, "approved_by": str(user.id)},
    )

    return tx


@transaction.atomic
def cash_flow_reject(*, user: User, tx_id: str, remarks: str = "") -> CashFlowTransaction:
    """
    Từ chối phiếu dòng tiền. Nếu CF liên quan đến TSCĐ, revert asset status.
    """
    PermissionChecker.check_permission(user, "finance.approve_cash_flow")

    tx = CashFlowTransaction.objects.select_for_update().filter(id=tx_id).first()
    if not tx:
        raise NotFoundException("Phiếu chi dòng tiền không tồn tại.")
    if tx.status != "pending_approval":
        raise ValidationException("Chỉ có thể từ chối phiếu ở trạng thái Chờ duyệt.")

    if tx.fixed_asset_id:
        asset = tx.fixed_asset
        if tx.payment_type == "pay" and asset.status == "pending_receive":
            # Không duyệt mua: xóa asset + PO/PI liên quan
            # Clear FK trên CF trước khi xóa PO/PI để tránh DB constraint violation
            po_id = tx.purchase_order_id
            pi_id = tx.purchase_invoice_id
            asset_id = str(asset.id)
            asset_code = asset.asset_code

            tx.purchase_order = None
            tx.purchase_invoice = None
            tx.fixed_asset = None
            tx.save(update_fields=["purchase_order", "purchase_invoice", "fixed_asset"])

            from apps.purchasing.models import PurchaseInvoice, PurchaseOrder

            if po_id:
                po = PurchaseOrder.objects.filter(id=po_id).first()
                if po:
                    po.delete()
            if pi_id:
                pi = PurchaseInvoice.objects.filter(id=pi_id).first()
                if pi:
                    pi.delete()

            asset.delete()

            create_system_log(
                user=user,
                action="reject_purchase",
                table_name="fixed_asset",
                record_id=asset_id,
                new_value={
                    "asset_code": asset_code,
                    "deleted": True,
                    "reason": "Từ chối đơn duyệt mua",
                },
            )
        elif tx.payment_type == "receive" and asset.status == "pending_dispose":
            # Không duyệt thanh lý: trở về idle
            old_status = asset.status
            old_disposal_value = asset.disposal_value
            old_disposal_date = asset.disposal_date

            asset.status = "idle"
            asset.disposal_date = None
            asset.disposal_value = None
            asset.save()
            create_system_log(
                user=user,
                action="reject_dispose",
                table_name="fixed_asset",
                record_id=str(asset.id),
                old_value={
                    "status": old_status,
                    "disposal_value": str(old_disposal_value) if old_disposal_value is not None else None,
                    "disposal_date": str(old_disposal_date) if old_disposal_date is not None else None,
                },
                new_value={"status": "idle", "disposal_value": None, "disposal_date": None},
            )

    tx.status = "rejected"
    tx.approved_by = user
    tx.approved_at = timezone.now()
    if remarks:
        tx.remarks = (tx.remarks or "") + f"\n[Từ chối] {remarks}"
    tx.save()

    create_system_log(
        user=user,
        action="reject",
        table_name="cash_flow_transaction",
        record_id=str(tx.id),
        new_value={"status": "rejected", "rejected_by": str(user.id)},
    )
    return tx


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


def _create_po_pi_for_asset(asset: FixedAsset):
    """Tạo PO + PI PAID cho asset (mua tài sản cố định)."""
    from apps.master_data.models import Item
    from apps.procurement.models import Supplier
    from apps.purchasing.models import PurchaseInvoice, PurchaseInvoiceLine, PurchaseOrder, PurchaseOrderLine

    if asset.vendor_name:
        vendor, _ = Supplier.objects.get_or_create(
            name=asset.vendor_name, defaults={"supplier_name": asset.vendor_name, "is_active": True}
        )
    else:
        vendor = Supplier.objects.filter(name="NCC_TSCĐ").first() or Supplier.objects.first()
        if not vendor:
            vendor = Supplier.objects.create(
                name="NCC_TSCĐ", supplier_name="Nhà cung cấp tài sản cố định", is_active=True
            )

    item = Item.objects.filter(item_code="FA_PLACEHOLDER").first() or Item.objects.first()
    if not item:
        item = Item.objects.create(
            item_code="FA_PLACEHOLDER", item_name="Tài sản cố định", is_active=True, is_import=False, status="active"
        )

    p_date = asset.purchase_date or timezone.now().date()

    po = PurchaseOrder.objects.create(
        vendor=vendor,
        status=PurchaseOrder.Status.COMPLETED,
        total_amount=asset.original_value,
        advance_paid_amount=asset.original_value,
        payment_fulfillment_rate=Decimal("100.00"),
        receipt_fulfillment_rate=Decimal("100.00"),
        expected_delivery_date=p_date,
    )
    PurchaseOrderLine.objects.create(
        order=po,
        item=item,
        quantity=Decimal("1.00"),
        unit_price=asset.original_value,
        line_total=asset.original_value,
    )

    pi = PurchaseInvoice.objects.create(
        order=po,
        vendor=vendor,
        status=PurchaseInvoice.Status.PAID,
        total_amount=asset.original_value,
        paid_amount=asset.original_value,
        due_date=p_date,
    )
    PurchaseInvoiceLine.objects.create(
        invoice=pi,
        item=item,
        quantity=Decimal("1.00"),
        unit_price=asset.original_value,
        line_total=asset.original_value,
    )
    return po, pi


@transaction.atomic
def fixed_asset_create(
    *,
    user: User,
    asset_name: str,
    original_value: Decimal,
    salvage_value: Decimal = Decimal("0.00"),
    depreciation_method: str,
    useful_life_months: Optional[int] = None,
    designed_capacity: Optional[Decimal] = None,
    purchase_date: Optional[str] = None,
    vendor_name: Optional[str] = None,
    payment_method: str = "bank_transfer",
    # Kept for compatibility:
    asset_code: Optional[str] = None,
) -> FixedAsset:
    PermissionChecker.check_permission(user, "finance.create_fixed_asset")

    if original_value <= Decimal("0.00"):
        raise ValidationException("Nguyên giá tài sản phải lớn hơn 0.")

    if salvage_value < Decimal("0.00"):
        raise ValidationException("Giá trị thanh lý ước tính không được âm.")

    if depreciation_method not in ["straight_line", "unit_of_production"]:
        raise ValidationException("Phương pháp khấu hao không hợp lệ.")

    if depreciation_method == "straight_line":
        if useful_life_months is None or useful_life_months <= 0:
            raise ValidationException("Số tháng khấu hao hữu ích phải lớn hơn 0 đối với phương pháp đường thẳng.")
        if designed_capacity is not None:
            raise ValidationException(
                "Công suất thiết kế không được cung cấp đối với phương pháp khấu hao đường thẳng."
            )
    elif depreciation_method == "unit_of_production":
        if not designed_capacity or designed_capacity <= Decimal("0.00"):
            raise ValidationException("Công suất thiết kế phải lớn hơn 0 đối với phương pháp sản lượng.")
        if useful_life_months is not None:
            raise ValidationException(
                "Thời gian khấu hao không được cung cấp đối với phương pháp khấu hao theo sản lượng."
            )

    if not asset_code:
        import uuid

        asset_code = f"FA-{str(uuid.uuid4())}"

    # Check unique asset code
    if FixedAsset.objects.filter(asset_code=asset_code).exists():
        raise ValidationException(f"Mã tài sản cố định '{asset_code}' đã tồn tại.")

    asset = FixedAsset.objects.create(
        asset_code=asset_code,
        asset_name=asset_name,
        original_value=original_value,
        salvage_value=salvage_value,
        depreciation_method=depreciation_method,
        useful_life_months=useful_life_months,
        remaining_life_months=useful_life_months,
        designed_capacity=designed_capacity,
        accumulated_depreciation=Decimal("0.00"),
        status="pending_receive",
        purchase_date=purchase_date,
        vendor_name=vendor_name,
        payment_method=payment_method,
    )

    create_system_log(
        user=user,
        action="create",
        table_name="fixed_asset",
        record_id=str(asset.id),
        new_value={"asset_code": asset_code, "original_value": str(original_value)},
    )

    # Tự tạo PO + PI + CF pending_approval
    po, pi = _create_po_pi_for_asset(asset)

    import uuid as uuid_lib

    cf_name = f"CF-PAY-FA-{asset.asset_code}-{str(uuid_lib.uuid4())[:8].upper()}"
    CashFlowTransaction.objects.create(
        name=cf_name,
        payment_type="pay",
        category="Mua tài sản cố định",
        payment_method=asset.payment_method or "bank_transfer",
        purchase_order=po,
        purchase_invoice=pi,
        amount=asset.original_value,
        payment_date=asset.purchase_date or timezone.now().date(),
        status="pending_approval",
        fixed_asset=asset,
        remarks=f"Phiếu chi mua tài sản cố định: {asset.asset_name} ({asset.asset_code})",
    )
    return asset


@transaction.atomic
def fixed_asset_request_dispose(
    *,
    user: User,
    asset_id: str,
    disposal_date: str,
    disposal_value: Decimal,
    remarks: Optional[str] = None,
) -> FixedAsset:
    PermissionChecker.check_permission(user, "finance.update_fixed_asset")

    asset = FixedAsset.objects.select_for_update().filter(id=asset_id).first()
    if not asset:
        raise NotFoundException("Tài sản cố định không tồn tại.")

    if asset.status == "active":
        raise ValidationException("Tài sản đang hoạt động không thể yêu cầu thanh lý. Vui lòng kết thúc sử dụng trước.")

    if asset.status != "idle":
        raise ValidationException("Chỉ có thể yêu cầu thanh lý tài sản đang ở trạng thái nhàn rỗi.")

    if disposal_value < Decimal("0.00"):
        raise ValidationException("Giá trị thanh lý không được âm.")

    # LUỒNG 1: Thanh lý có giá trị → chờ duyệt dòng tiền (CFO duyệt/từ chối)
    #   - Set status = "pending_dispose"
    #   - Tạo CashFlowTransaction với payment_type="receive", status="pending_approval"
    #   - CFO duyệt CF → asset.status = "disposed"
    #   - CFO từ chối CF → asset quay về "idle"
    if disposal_value > Decimal("0.00"):
        asset.status = "pending_dispose"
        asset.disposal_date = disposal_date
        asset.disposal_value = disposal_value
        asset.save()

        import uuid

        cf_name = f"CF-REV-FA-{asset.asset_code}-{str(uuid.uuid4())[:8].upper()}"
        CashFlowTransaction.objects.create(
            name=cf_name,
            payment_type="receive",
            category="Thanh lý tài sản cố định",
            payment_method="bank_transfer",
            amount=disposal_value,
            payment_date=disposal_date,
            status="pending_approval",
            fixed_asset=asset,
            remarks=f"Phiếu thu thanh lý tài sản cố định: {asset.asset_name} ({asset.asset_code})",
        )

        create_system_log(
            user=user,
            action="request_dispose",
            table_name="fixed_asset",
            record_id=str(asset.id),
            new_value={"status": "pending_dispose", "disposal_value": str(disposal_value)},
        )
    # LUỒNG 2: Thanh lý 0 đồng (mua lại phế liệu/hủy bỏ không thu hồi tiền) → chuyển thẳng sang disposed
    #   - KHÔNG tạo CF (không có dòng tiền)
    #   - Set status = "disposed" ngay lập tức
    #   - Không thể từ chối (vì không có CF để reject)
    else:
        asset.status = "disposed"
        asset.disposal_date = disposal_date
        asset.disposal_value = disposal_value
        asset.save()

        create_system_log(
            user=user,
            action="request_dispose_zero_value",
            table_name="fixed_asset",
            record_id=str(asset.id),
            new_value={"status": "disposed", "disposal_value": "0.00"},
        )
    return asset


@transaction.atomic
def set_fixed_asset_status_for_workorder(*, asset_ids: list[str], target_status: str, source: str) -> int:
    """
    Set FixedAsset status khi WorkOrder chuyển trạng thái.
    CHỈ set nếu asset hiện ở idle (chuyển sang active) hoặc active (chuyển về idle).
    Bảo vệ các trạng thái khác (pending_receive, pending_dispose, disposed).
    """
    if not asset_ids:
        return 0

    import logging

    logger = logging.getLogger(__name__)

    # Bảo vệ: KHÔNG đè status pending_receive / pending_dispose / disposed
    protected_statuses = ["pending_receive", "pending_dispose", "disposed"]

    if target_status == "active":
        queryset = FixedAsset.objects.filter(id__in=asset_ids, status="idle")
    elif target_status == "idle":
        queryset = FixedAsset.objects.filter(id__in=asset_ids, status="active")
    else:
        queryset = FixedAsset.objects.filter(id__in=asset_ids).exclude(status__in=protected_statuses)

    count = queryset.update(status=target_status, updated_at=timezone.now())
    logger.info(f"[finance] Auto-set {count} FixedAsset to {target_status} (source={source})")
    return count


@transaction.atomic
def validate_fixed_assets_for_workorder_start(*, asset_ids: list[str]) -> None:
    """
    Validate tất cả asset đều ở trạng thái idle trước khi WO chuyển in_progress.
    Raise ValidationException với danh sách asset vi phạm nếu có.
    """
    if not asset_ids:
        return

    invalid_assets = (
        FixedAsset.objects.filter(id__in=asset_ids).exclude(status="idle").values("asset_code", "asset_name", "status")
    )

    invalid_list = list(invalid_assets)
    if invalid_list:
        details = "\n".join(f"- [{a['asset_code']}] {a['asset_name']} (hiện tại: {a['status']})" for a in invalid_list)
        raise ValidationException(
            "Không thể chuyển WorkOrder sang 'in_progress' vì có tài sản "
            f"chưa ở trạng thái 'idle'. Vui lòng đổi các tài sản sau:\n{details}"
        )

    # Lỗi 2: MỚI — asset có thể đã bị gán cho WO active khác giữa lúc set và lúc approve
    from apps.master_data.models import WorkOrderFixedAsset

    conflicting = WorkOrderFixedAsset.objects.select_related("work_order", "fixed_asset").filter(
        fixed_asset_id__in=asset_ids,
        work_order__status__in=("in_progress", "pending_production_complete"),
    )
    conflicting_list = list(conflicting)
    if conflicting_list:
        details = "\n".join(
            f"- [{link.fixed_asset.asset_code}] {link.fixed_asset.asset_name} "
            f"(đang được sử dụng bởi WO '{link.work_order.name}')"
            for link in conflicting_list
        )
        raise ValidationException(
            "Phát hiện xung đột: Một số tài sản đã được gán cho WorkOrder khác "
            f"đang hoạt động. Vui lòng kiểm tra:\n{details}"
        )


@transaction.atomic
def fixed_asset_update(
    *,
    user: User,
    asset_id: str,
    asset_name: Optional[str] = None,
    useful_life_months: Optional[int] = None,
    **kwargs,
) -> FixedAsset:
    PermissionChecker.check_permission(user, "finance.update_fixed_asset")

    forbidden_keys = {"original_value", "salvage_value", "depreciation_method", "designed_capacity"}
    passed_forbidden = set(kwargs.keys()) & forbidden_keys
    for k in forbidden_keys:
        if kwargs.get(k) is not None:
            passed_forbidden.add(k)

    if passed_forbidden:
        raise ValidationException(
            f"Chỉ được phép cập nhật các trường: asset_name, useful_life_months. Gặp trường không hợp lệ: {', '.join(passed_forbidden)}."
        )

    asset = FixedAsset.objects.select_for_update().filter(id=asset_id).first()
    if not asset:
        raise NotFoundException("Tài sản cố định không tồn tại.")

    if asset.status != "idle":
        raise ValidationException("Chỉ được phép chỉnh sửa thông tin tài sản cố định đang ở trạng thái 'idle'.")

    has_depreciated = asset.depreciation_logs.exists()

    if asset_name is not None:
        asset.asset_name = asset_name

    if useful_life_months is not None:
        if asset.depreciation_method == "unit_of_production":
            raise ValidationException("Không thể sửa số tháng sử dụng hữu ích của tài sản khấu hao theo sản lượng.")
        if has_depreciated:
            raise ValidationException("Không thể sửa số tháng sử dụng hữu ích của tài sản đã phát sinh khấu hao.")
        if useful_life_months <= 0:
            raise ValidationException("Số tháng khấu hao hữu ích phải lớn hơn 0.")
        asset.useful_life_months = useful_life_months
        asset.remaining_life_months = useful_life_months

    asset.save()

    create_system_log(
        user=user,
        action="update",
        table_name="fixed_asset",
        record_id=str(asset.id),
        new_value={"asset_name": asset.asset_name, "useful_life_months": asset.useful_life_months},
    )
    return asset


@transaction.atomic
def fixed_asset_delete(*, user: User, asset_id: str) -> None:
    raise ValidationException("Tài sản cố định chỉ có thể thanh lý, không thể xóa.")


def auto_run_depreciation_for_period(*, period: str, user: User) -> None:
    """
    Gọi run_fixed_asset_depreciation một cách im lặng.
    Bắt lỗi NotFoundException/ValidationException để không ảnh hưởng API.
    """
    try:
        if not PermissionChecker.has_permission(user, "finance.run_depreciation"):
            return

        if FixedAssetDepreciationLog.objects.filter(period=period).exists():
            return

        run_fixed_asset_depreciation(user=user, period=period)
    except (NotFoundException, ValidationException) as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Auto-depreciation skip for period {period}: {e}")
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Auto-depreciation error for period {period}: {e}", exc_info=True)


@transaction.atomic
def run_fixed_asset_depreciation(*, user: User, period: str) -> list[FixedAssetDepreciationLog]:
    """
    Kích hoạt chạy khấu hao tự động cho toàn bộ tài sản hoạt động trong kỳ (YYYY-MM).
    """
    PermissionChecker.check_permission(user, "finance.run_depreciation")

    if not re.match(r"^\d{4}-\d{2}$", period):
        raise ValidationException("Định dạng kỳ khấu hao không hợp lệ. Vui lòng sử dụng định dạng YYYY-MM.")

    # Check if this period has already been run
    if FixedAssetDepreciationLog.objects.filter(period=period).exists():
        raise ValidationException(f"Kỳ khấu hao '{period}' đã được thực hiện hạch toán trước đó.")

    year, month = map(int, period.split("-"))
    start_datetime = timezone.make_aware(datetime.datetime(year, month, 1, 0, 0, 0))
    if month == 12:
        end_datetime = timezone.make_aware(datetime.datetime(year + 1, 1, 1, 0, 0, 0)) - datetime.timedelta(
            microseconds=1
        )
    else:
        end_datetime = timezone.make_aware(datetime.datetime(year, month + 1, 1, 0, 0, 0)) - datetime.timedelta(
            microseconds=1
        )

    chunk_size = 500
    last_id = None

    from django.db import OperationalError, connection

    while True:
        from django.db.models import F

        qs = FixedAsset.objects.filter(is_active=True, status="active").filter(
            models.Q(depreciation_method="straight_line", remaining_life_months__gt=0)
            | models.Q(
                depreciation_method="unit_of_production",
                accumulated_depreciation__lt=F("original_value") - F("salvage_value"),
            )
        )
        if last_id:
            qs = qs.filter(id__gt=last_id)

        try:
            if connection.vendor == "postgresql":
                chunk = list(qs.order_by("id")[:chunk_size].select_for_update(nowait=True))
            else:
                chunk = list(qs.order_by("id")[:chunk_size].select_for_update())
        except OperationalError as e:
            if "could not obtain lock" in str(e).lower() or "lock" in str(e).lower():
                raise ValidationException("Hệ thống đang xử lý khấu hao, vui lòng thử lại sau.")
            raise

        if not chunk:
            break

        logs_to_create = []
        assets_to_update = []

        for asset in chunk:
            last_id = asset.id

            depreciable_value = asset.original_value - asset.salvage_value
            remaining_value = depreciable_value - asset.accumulated_depreciation

            if asset.depreciation_method == "straight_line" and asset.remaining_life_months == 0:
                continue
            if (
                asset.depreciation_method == "unit_of_production"
                and asset.accumulated_depreciation >= depreciable_value
            ):
                continue

            if remaining_value <= Decimal("0.00"):
                continue

            depreciation_amount = Decimal("0.00")
            remarks = ""

            if asset.depreciation_method == "straight_line":
                depreciation_amount = depreciable_value / Decimal(str(asset.useful_life_months))
                remarks = f"Khấu hao đường thẳng kỳ {period}. (Hữu ích: {asset.useful_life_months} tháng)"

            elif asset.depreciation_method == "unit_of_production":
                prod_qty_result = StockEntryDetail.objects.filter(
                    target_warehouse__isnull=False,
                    parent__purpose="manufacture",
                    parent__status="posted",
                    parent__work_order__fixed_asset_links__fixed_asset=asset,
                    parent__posting_date__range=(start_datetime, end_datetime),
                ).aggregate(total=Sum("quantity"))

                prod_qty = prod_qty_result["total"] or Decimal("0.00")

                if prod_qty <= Decimal("0.00"):
                    depreciation_amount = Decimal("0.00")
                    remarks = "Không có WorkOrder nào sản xuất trong kỳ sử dụng tài sản này."
                else:
                    depreciation_amount = prod_qty * (depreciable_value / asset.designed_capacity)
                    remarks = f"Khấu hao sản lượng kỳ {period} (Sản lượng thực tế: {prod_qty:.2f} cái, CS thiết kế: {asset.designed_capacity:.2f} cái)."

            if depreciation_amount > remaining_value:
                depreciation_amount = remaining_value

            depreciation_amount = depreciation_amount.quantize(Decimal("0.01"))

            # Save UOP logs even if amount is 0.00 (with special remarks)
            if depreciation_amount <= Decimal("0.00") and asset.depreciation_method != "unit_of_production":
                continue

            log = FixedAssetDepreciationLog(
                asset=asset,
                period=period,
                depreciation_amount=depreciation_amount,
                remarks=remarks,
            )
            logs_to_create.append(log)

            asset.accumulated_depreciation += depreciation_amount
            if asset.depreciation_method == "straight_line":
                asset.remaining_life_months = max(0, asset.remaining_life_months - 1)
            assets_to_update.append(asset)

        if logs_to_create:
            FixedAssetDepreciationLog.objects.bulk_create(logs_to_create)
        if assets_to_update:
            FixedAsset.objects.bulk_update(assets_to_update, ["accumulated_depreciation", "remaining_life_months"])

    logs = list(
        FixedAssetDepreciationLog.objects.filter(period=period).select_related("asset").order_by("created_at", "id")
    )

    if logs:
        create_system_log(
            user=user,
            action="run_depreciation",
            table_name="fixed_asset_depreciation_log",
            record_id=period,
            new_value={"period": period, "depreciated_count": len(logs)},
        )

    return logs


@transaction.atomic
def pay_purchase_invoice(*, user: User, invoice_id: str, amount: Decimal, payment_method: str) -> Any:
    """
    Thanh toán hóa đơn mua hàng (Purchase Invoice).
    """
    PermissionChecker.check_permission(user, "finance.pay_invoice")

    from apps.purchasing.models import PurchaseInvoice

    invoice = PurchaseInvoice.objects.select_for_update().filter(id=invoice_id).first()
    if not invoice:
        raise NotFoundException("Hóa đơn mua hàng không tồn tại.")

    from django.utils import timezone

    payment_date_str = timezone.now().date().isoformat()

    tx = cash_flow_create(
        user=user,
        payment_type="pay",
        amount=amount,
        payment_date=payment_date_str,
        category="Thanh toán hóa đơn mua hàng",
        payment_method=payment_method,
        purchase_invoice_id=str(invoice.id),
        remarks=f"Thanh toán cho hóa đơn mua hàng {invoice.id} (NCC: {invoice.vendor.supplier_name}).",
    )

    return tx


@transaction.atomic
def collect_sales_invoice(*, user: User, invoice_id: str, amount: Decimal, payment_method: str) -> Any:
    """
    Thu tiền hóa đơn bán hàng (Sales Invoice - AR collection).
    Tạo CashFlow transaction pending_approval, tương tự pay_purchase_invoice.
    """
    PermissionChecker.check_permission(user, "finance.collect_sales_invoice")

    from apps.sales.models import SalesInvoice

    invoice = SalesInvoice.objects.select_for_update().filter(id=invoice_id).first()
    if not invoice:
        raise NotFoundException("Hóa đơn bán hàng không tồn tại.")

    if invoice.status in [SalesInvoice.Status.PAID, SalesInvoice.Status.CANCELLED]:
        raise ValidationException("Hóa đơn bán không hợp lệ hoặc đã hoàn tất thanh toán.")

    from django.utils import timezone

    payment_date_str = timezone.now().date().isoformat()

    tx = cash_flow_create(
        user=user,
        payment_type="receive",
        amount=amount,
        payment_date=payment_date_str,
        category="Thu tiền hóa đơn bán hàng",
        payment_method=payment_method,
        sales_invoice_id=str(invoice.id),
        remarks=f"Thu tiền HĐ bán {str(invoice.id)[:8].upper()} (Khách hàng: {invoice.customer.customer_name}).",
    )

    return tx
