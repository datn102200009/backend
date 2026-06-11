"""
Services for finance app.

All write operations (Create, Update, Delete) should be defined here.
Never receive request objects, only primitive types or DTOs.
Always ensure atomic transactions.
"""

import datetime
import re
from decimal import Decimal
from typing import Any, Optional

from django.db import transaction
from django.db.models import Sum
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

        if tx.category != "Chi phí vận chuyển lô hàng":
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
    _apply_cash_flow_effect(tx, tx.amount)

    tx.status = "posted"
    tx.approved_by = user
    tx.approved_at = timezone.now()
    tx.save()

    create_system_log(
        user=user,
        action="approve",
        table_name="cash_flow_transaction",
        record_id=str(tx.id),
        new_value={"status": tx.status, "approved_by": str(user.id)},
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


@transaction.atomic
def fixed_asset_create(
    *,
    user: User,
    asset_code: str,
    asset_name: str,
    original_value: Decimal,
    salvage_value: Decimal = Decimal("0.00"),
    depreciation_method: str,
    useful_life_months: int,
    designed_capacity: Optional[Decimal] = None,
    department: Optional[str] = None,
) -> FixedAsset:
    PermissionChecker.check_permission(user, "finance.create_fixed_asset")

    if original_value <= Decimal("0.00"):
        raise ValidationException("Nguyên giá tài sản phải lớn hơn 0.")

    if salvage_value < Decimal("0.00"):
        raise ValidationException("Giá trị thanh lý ước tính không được âm.")

    if depreciation_method not in ["straight_line", "unit_of_production"]:
        raise ValidationException("Phương pháp khấu hao không hợp lệ.")

    if depreciation_method == "straight_line":
        if useful_life_months <= 0:
            raise ValidationException("Số tháng khấu hao hữu ích phải lớn hơn 0 đối với phương pháp đường thẳng.")
    elif depreciation_method == "unit_of_production":
        if not designed_capacity or designed_capacity <= Decimal("0.00"):
            raise ValidationException("Công suất thiết kế phải lớn hơn 0 đối với phương pháp sản lượng.")
        if useful_life_months <= 0:
            raise ValidationException("Số tháng khấu hao hữu ích phải lớn hơn 0 đối với phương pháp sản lượng.")

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
        department=department,
    )

    create_system_log(
        user=user,
        action="create",
        table_name="fixed_asset",
        record_id=str(asset.id),
        new_value={"asset_code": asset_code, "original_value": str(original_value)},
    )
    return asset


@transaction.atomic
def fixed_asset_update(
    *,
    user: User,
    asset_id: str,
    asset_name: Optional[str] = None,
    original_value: Optional[Decimal] = None,
    salvage_value: Optional[Decimal] = None,
    depreciation_method: Optional[str] = None,
    useful_life_months: Optional[int] = None,
    designed_capacity: Optional[Decimal] = None,
    department: Optional[str] = None,
) -> FixedAsset:
    PermissionChecker.check_permission(user, "finance.update_fixed_asset")

    asset = FixedAsset.objects.select_for_update().filter(id=asset_id).first()
    if not asset:
        raise NotFoundException("Tài sản cố định không tồn tại.")

    # If already depreciated, block modifying core values
    has_depreciated = asset.depreciation_logs.exists()

    if asset_name is not None:
        asset.asset_name = asset_name

    if department is not None:
        asset.department = department

    if original_value is not None:
        if has_depreciated:
            raise ValidationException("Không thể sửa nguyên giá của tài sản đã phát sinh khấu hao.")
        if original_value <= Decimal("0.00"):
            raise ValidationException("Nguyên giá tài sản phải lớn hơn 0.")
        asset.original_value = original_value

    if salvage_value is not None:
        if has_depreciated:
            raise ValidationException("Không thể sửa giá trị thanh lý của tài sản đã phát sinh khấu hao.")
        if salvage_value < Decimal("0.00"):
            raise ValidationException("Giá trị thanh lý ước tính không được âm.")
        asset.salvage_value = salvage_value

    if depreciation_method is not None:
        if has_depreciated:
            raise ValidationException("Không thể sửa phương pháp khấu hao của tài sản đã phát sinh khấu hao.")
        if depreciation_method not in ["straight_line", "unit_of_production"]:
            raise ValidationException("Phương pháp khấu hao không hợp lệ.")
        asset.depreciation_method = depreciation_method

    if useful_life_months is not None:
        if has_depreciated:
            raise ValidationException("Không thể sửa số tháng sử dụng hữu ích của tài sản đã phát sinh khấu hao.")
        if useful_life_months <= 0:
            raise ValidationException("Số tháng khấu hao hữu ích phải lớn hơn 0.")
        asset.useful_life_months = useful_life_months
        asset.remaining_life_months = useful_life_months

    if designed_capacity is not None:
        if has_depreciated:
            raise ValidationException("Không thể sửa công suất thiết kế của tài sản đã phát sinh khấu hao.")
        if designed_capacity <= Decimal("0.00"):
            raise ValidationException("Công suất thiết kế phải lớn hơn 0.")
        asset.designed_capacity = designed_capacity

    # Double validation based on chosen method
    if asset.depreciation_method == "straight_line":
        if asset.useful_life_months <= 0:
            raise ValidationException("Số tháng khấu hao hữu ích phải lớn hơn 0 đối với phương pháp đường thẳng.")
    elif asset.depreciation_method == "unit_of_production":
        if not asset.designed_capacity or asset.designed_capacity <= Decimal("0.00"):
            raise ValidationException("Công suất thiết kế phải lớn hơn 0 đối với phương pháp sản lượng.")

    asset.save()

    create_system_log(
        user=user,
        action="update",
        table_name="fixed_asset",
        record_id=str(asset.id),
        new_value={"asset_name": asset.asset_name, "original_value": str(asset.original_value)},
    )
    return asset


@transaction.atomic
def fixed_asset_delete(*, user: User, asset_id: str) -> None:
    PermissionChecker.check_permission(user, "finance.delete_fixed_asset")

    asset = FixedAsset.objects.filter(id=asset_id).first()
    if not asset:
        raise NotFoundException("Tài sản cố định không tồn tại.")

    if asset.depreciation_logs.exists():
        raise ValidationException("Không thể xóa tài sản cố định đã phát sinh lịch sử khấu hao.")

    # Check if linked to any BOM
    if asset.boms.exists():
        bom_names = ", ".join(asset.boms.values_list("name", flat=True))
        raise ValidationException(f"Không thể xóa tài sản cố định đang liên kết với định mức BOM: {bom_names}.")

    create_system_log(
        user=user,
        action="delete",
        table_name="fixed_asset",
        record_id=str(asset.id),
        new_value={"asset_code": asset.asset_code, "asset_name": asset.asset_name},
    )
    asset.delete()


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

    # Process active assets in chunks using keyset pagination (Batch size: 500)
    chunk_size = 500
    last_id = None

    from django.db import OperationalError, connection

    while True:
        qs = FixedAsset.objects.filter(
            is_active=True,
            remaining_life_months__gt=0,
        )
        if last_id:
            qs = qs.filter(id__gt=last_id)

        # Select for update to lock the rows
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

            # Remainder depreciable amount
            depreciable_value = asset.original_value - asset.salvage_value
            remaining_value = depreciable_value - asset.accumulated_depreciation

            if remaining_value <= Decimal("0.00"):
                continue

            depreciation_amount = Decimal("0.00")
            remarks = ""

            if asset.depreciation_method == "straight_line":
                depreciation_amount = depreciable_value / Decimal(str(asset.useful_life_months))
                remarks = f"Khấu hao đường thẳng kỳ {period}. (Hữu ích: {asset.useful_life_months} tháng)"

            elif asset.depreciation_method == "unit_of_production":
                # Get finished products using this mold via BOM
                product_ids = asset.boms.filter(is_active=True).values_list("item_id", flat=True)

                if not product_ids:
                    # Mold not linked to any active BOM, skip
                    continue

                # Query actual manufactured receipt quantity in StockEntryDetail
                prod_qty_result = StockEntryDetail.objects.filter(
                    item_id__in=product_ids,
                    target_warehouse__isnull=False,
                    parent__purpose="manufacture",
                    parent__status="posted",
                    parent__posting_date__range=(start_datetime, end_datetime),
                ).aggregate(total=Sum("quantity"))

                prod_qty = prod_qty_result["total"] or Decimal("0.00")

                if prod_qty <= Decimal("0.00"):
                    continue

                depreciation_amount = prod_qty * (depreciable_value / asset.designed_capacity)
                remarks = f"Khấu hao sản lượng kỳ {period} (Sản lượng thực tế: {prod_qty:.2f} cái, CS thiết kế: {asset.designed_capacity:.2f} cái)."

            # Cap depreciation amount to remaining value
            if depreciation_amount > remaining_value:
                depreciation_amount = remaining_value

            depreciation_amount = depreciation_amount.quantize(Decimal("0.01"))

            if depreciation_amount <= Decimal("0.00"):
                continue

            # Save log to bulk create list
            log = FixedAssetDepreciationLog(
                asset=asset,
                period=period,
                depreciation_amount=depreciation_amount,
                remarks=remarks,
            )
            logs_to_create.append(log)

            # Update asset properties
            asset.accumulated_depreciation += depreciation_amount
            asset.remaining_life_months = max(0, asset.remaining_life_months - 1)
            assets_to_update.append(asset)

        if logs_to_create:
            FixedAssetDepreciationLog.objects.bulk_create(logs_to_create)
        if assets_to_update:
            FixedAsset.objects.bulk_update(assets_to_update, ["accumulated_depreciation", "remaining_life_months"])

    # Fetch logs from DB using select_related("asset") to prevent downstream N+1
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
