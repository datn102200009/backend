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
from apps.finance.models import CashFlowTransaction, FixedAsset, FixedAssetDepreciationLog


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

    # Validate period format YYYY-MM
    import re

    if not re.match(r"^\d{4}-\d{2}$", period):
        raise ValidationException("Định dạng kỳ khấu hao không hợp lệ. Vui lòng sử dụng định dạng YYYY-MM.")

    # Check if this period has already been run
    if FixedAssetDepreciationLog.objects.filter(period=period).exists():
        raise ValidationException(f"Kỳ khấu hao '{period}' đã được thực hiện hạch toán trước đó.")

    # Parse period to get dates for UOP query
    import datetime

    from django.db.models import Sum
    from django.utils import timezone

    from apps.master_data.models import BOM

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

    # Fetch active assets that still need depreciation
    assets = FixedAsset.objects.select_for_update().filter(
        is_active=True,
        remaining_life_months__gt=0,
    )

    logs = []

    for asset in assets:
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
            # 1. Get finished products using this mold via BOM
            product_ids = asset.boms.filter(is_active=True).values_list("item_id", flat=True)

            if not product_ids:
                # Mold not linked to any active BOM, skip
                continue

            # 2. Query actual manufactured receipt quantity in StockEntryDetail
            from apps.inventory.models import StockEntryDetail

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

        # Save log
        log = FixedAssetDepreciationLog.objects.create(
            asset=asset,
            period=period,
            depreciation_amount=depreciation_amount,
            remarks=remarks,
        )
        logs.append(log)

        # Update FixedAsset
        asset.accumulated_depreciation += depreciation_amount
        asset.remaining_life_months = max(0, asset.remaining_life_months - 1)
        asset.save()

    if logs:
        create_system_log(
            user=user,
            action="run_depreciation",
            table_name="fixed_asset_depreciation_log",
            record_id=period,
            new_value={"period": period, "depreciated_count": len(logs)},
        )

    return logs
