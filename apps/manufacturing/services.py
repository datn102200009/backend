"""
Services for manufacturing app.

All write operations (Create, Update, Delete) should be defined here.
Never receive request objects, only primitive types or DTOs.
Always ensure atomic transactions.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.master_data.models import BOM, BOMItem, Item, WorkOrder

_UNSET = object()

# ======================== BOM (Định mức vật tư) ========================


@transaction.atomic
def bom_create(
    *,
    user: User,
    name: str,
    item_id: str,
    quantity: Decimal = Decimal("1"),
    description: Optional[str] = None,
    mold_id: Optional[str] = None,
    items: List[Dict[str, Any]],
) -> BOM:
    """
    Tạo định mức (BOM) mới cho một sản phẩm.

    Args:
        user: User thực hiện hành động
        name: Tên/mã định mức (unique)
        item_id: ID sản phẩm thành phẩm
        quantity: Số lượng thành phẩm tiêu chuẩn (mặc định = 1)
        description: Mô tả
        mold_id: ID khuôn mẫu tài sản cố định
        items: Danh sách linh kiện [{"item_id": "...", "quantity": 10.0}]

    Returns:
        BOM object

    Raises:
        PermissionException: Nếu user không có quyền
        ValidationException: Nếu dữ liệu không hợp lệ
        NotFoundException: Nếu item không tồn tại
    """
    PermissionChecker.check_permission(user, "manufacturing.bom_create")

    # Validate items list
    if not items:
        raise ValidationException("Định mức phải có ít nhất một linh kiện")

    # Kiểm tra tên unique
    if BOM.objects.filter(name=name).exists():
        raise ValidationException(f"Định mức '{name}' đã tồn tại")

    # Kiểm tra sản phẩm tồn tại
    item = Item.objects.filter(id=item_id).first()
    if not item:
        raise NotFoundException(f"Sản phẩm với ID {item_id} không tồn tại")

    # Kiểm tra sản phẩm đã có BOM active chưa
    existing_bom = BOM.objects.filter(item=item, is_active=True).first()
    if existing_bom:
        raise ValidationException(f"Sản phẩm '{item.item_code}' đã có định mức đang hoạt động: {existing_bom.name}")

    # Validate tất cả item_id trong items
    item_ids = [str(i["item_id"]) for i in items]
    existing_items = Item.objects.filter(id__in=item_ids)
    existing_item_ids = set(str(i.id) for i in existing_items)
    missing_ids = set(item_ids) - existing_item_ids
    if missing_ids:
        raise NotFoundException(f"Linh kiện không tồn tại: {', '.join(missing_ids)}")

    # Kiểm tra không có linh kiện trùng với thành phẩm
    if str(item.id) in item_ids:
        raise ValidationException("Linh kiện không được trùng với sản phẩm thành phẩm")

    # Resolve mold if passed
    mold = None
    if mold_id:
        from apps.finance.models import FixedAsset

        mold = FixedAsset.objects.filter(id=mold_id).first()
        if not mold:
            raise NotFoundException(f"Khuôn mẫu với ID {mold_id} không tồn tại")

    # Tạo BOM Header
    bom = BOM.objects.create(
        name=name,
        item=item,
        quantity=quantity,
        is_active=True,
        description=description,
        mold=mold,
    )

    # Tạo BOM Items (bulk create)
    item_map = {str(i.id): i for i in existing_items}
    bom_items = []
    for bom_item_data in items:
        bom_items.append(
            BOMItem(
                parent=bom,
                item=item_map[str(bom_item_data["item_id"])],
                quantity=bom_item_data["quantity"],
            )
        )
    BOMItem.objects.bulk_create(bom_items)

    # Ghi log
    create_system_log(
        user=user,
        action="create",
        table_name="bom",
        record_id=str(bom.id),
        new_value={
            "name": bom.name,
            "item_code": item.item_code,
            "quantity": str(bom.quantity),
            "items_count": len(items),
        },
    )

    return bom


@transaction.atomic
def bom_update(
    *,
    user: User,
    bom_id: str,
    name: Optional[str] = None,
    quantity: Optional[Decimal] = None,
    description: Optional[str] = None,
    mold_id: Optional[str] = _UNSET,  # type: ignore
    items: Optional[List[Dict[str, Any]]] = None,
) -> BOM:
    """
    Cập nhật định mức (BOM).

    Chiến lược cập nhật items: Xóa toàn bộ items cũ → Chèn items mới.
    Theo đặc tả: quan_li_bom.md mục 3.

    Args:
        user: User thực hiện hành động
        bom_id: ID của BOM cần cập nhật
        name: Tên/mã định mức mới
        quantity: Số lượng thành phẩm tiêu chuẩn mới
        description: Mô tả mới
        mold_id: ID khuôn mẫu tài sản cố định mới
        items: Danh sách linh kiện mới [{"item_id": "...", "quantity": 10.0}]

    Returns:
        BOM object đã cập nhật
    """
    PermissionChecker.check_permission(user, "manufacturing.bom_update")

    # Lấy BOM hiện tại
    bom = BOM.objects.select_related("item").filter(id=bom_id).first()
    if not bom:
        raise NotFoundException(f"Định mức với ID {bom_id} không tồn tại")

    # Lưu giá trị cũ cho audit log
    old_value = {
        "name": bom.name,
        "quantity": str(bom.quantity),
        "description": bom.description,
        "mold_id": str(bom.mold_id) if bom.mold_id else None,
        "items_count": bom.items.count(),
    }

    # Cập nhật header fields
    if name is not None and name != bom.name:
        if BOM.objects.filter(name=name).exclude(id=bom.id).exists():
            raise ValidationException(f"Định mức '{name}' đã tồn tại")
        bom.name = name

    if quantity is not None:
        bom.quantity = quantity
    if description is not None:
        bom.description = description

    if mold_id is not _UNSET:
        if mold_id:
            from apps.finance.models import FixedAsset

            mold = FixedAsset.objects.filter(id=mold_id).first()
            if not mold:
                raise NotFoundException(f"Khuôn mẫu với ID {mold_id} không tồn tại")
            bom.mold = mold
        else:
            bom.mold = None

    bom.save()

    # Cập nhật items (nếu có)
    if items is not None:
        if not items:
            raise ValidationException("Định mức phải có ít nhất một linh kiện")

        # Validate item_ids
        item_ids = [str(i["item_id"]) for i in items]
        existing_items = Item.objects.filter(id__in=item_ids)
        existing_item_ids = set(str(i.id) for i in existing_items)
        missing_ids = set(item_ids) - existing_item_ids
        if missing_ids:
            raise NotFoundException(f"Linh kiện không tồn tại: {', '.join(missing_ids)}")

        # Kiểm tra không có linh kiện trùng với thành phẩm
        if str(bom.item_id) in item_ids:
            raise ValidationException("Linh kiện không được trùng với sản phẩm thành phẩm")

        # Xóa items cũ → chèn items mới
        bom.items.all().delete()

        item_map = {str(i.id): i for i in existing_items}
        bom_items = []
        for bom_item_data in items:
            bom_items.append(
                BOMItem(
                    parent=bom,
                    item=item_map[str(bom_item_data["item_id"])],
                    quantity=bom_item_data["quantity"],
                )
            )
        BOMItem.objects.bulk_create(bom_items)

    # Ghi log
    new_value = {
        "name": bom.name,
        "quantity": str(bom.quantity),
        "description": bom.description,
        "items_count": bom.items.count(),
    }
    create_system_log(
        user=user,
        action="update",
        table_name="bom",
        record_id=str(bom.id),
        old_value=old_value,
        new_value=new_value,
    )

    return bom


@transaction.atomic
def bom_delete(*, user: User, bom_id: str) -> None:
    """
    Xóa định mức (BOM).

    Kiểm tra ràng buộc: Nếu BOM đang được sử dụng trong WorkOrder → không cho xóa.
    Theo đặc tả: quan_li_bom.md mục 4.

    Args:
        user: User thực hiện hành động
        bom_id: ID của BOM cần xóa
    """
    PermissionChecker.check_permission(user, "manufacturing.bom_delete")

    bom = BOM.objects.filter(id=bom_id).first()
    if not bom:
        raise NotFoundException(f"Định mức với ID {bom_id} không tồn tại")

    # Kiểm tra ràng buộc với Work Order
    work_order_count = WorkOrder.objects.filter(bom=bom).count()
    if work_order_count > 0:
        raise ValidationException(
            f"Không thể xóa định mức '{bom.name}' vì đang được sử dụng " f"trong {work_order_count} lệnh sản xuất"
        )

    # Lưu thông tin cho log trước khi xóa
    log_data = {
        "name": bom.name,
        "item_id": str(bom.item_id),
    }

    # Xóa items trước, rồi xóa BOM
    bom.items.all().delete()
    bom.delete()

    # Ghi log
    create_system_log(
        user=user,
        action="delete",
        table_name="bom",
        record_id=bom_id,
        old_value=log_data,
    )


# ======================== Work Order (Lệnh sản xuất) ========================


@transaction.atomic
def work_order_create(
    *,
    user: User,
    name: str,
    bom_id: str,
    quantity: Decimal,
    source_warehouse_id: str,
    target_warehouse_id: str,
    production_warehouse_id: str,
    planned_start_date: date,
    planned_end_date: Optional[date] = None,
    remarks: Optional[str] = None,
) -> WorkOrder:
    from apps.master_data.models import Warehouse

    PermissionChecker.check_permission(user, "manufacturing.work_order_create")

    if WorkOrder.objects.filter(name=name).exists():
        raise ValidationException(f"Lệnh sản xuất '{name}' đã tồn tại")

    bom = BOM.objects.select_related("item").filter(id=bom_id).first()
    if not bom:
        raise NotFoundException(f"Định mức với ID {bom_id} không tồn tại")

    if not bom.is_active:
        raise ValidationException(f"Định mức '{bom.name}' không hoạt động")

    if quantity <= 0:
        raise ValidationException("Số lượng sản xuất phải lớn hơn 0")

    source = Warehouse.objects.filter(id=source_warehouse_id).first()
    target = Warehouse.objects.filter(id=target_warehouse_id).first()
    production = Warehouse.objects.filter(id=production_warehouse_id).first()

    if not source:
        raise NotFoundException("Kho nguồn không tồn tại")
    if not target:
        raise NotFoundException("Kho đích không tồn tại")
    if not production:
        raise NotFoundException("Kho sản xuất không tồn tại")

    work_order = WorkOrder.objects.create(
        name=name,
        bom=bom,
        production_item=bom.item,
        quantity=quantity,
        source_warehouse=source,
        target_warehouse=target,
        production_warehouse=production,
        status="pending_approval",
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        remarks=remarks,
    )

    create_system_log(
        user=user,
        action="create",
        table_name="work_order",
        record_id=str(work_order.id),
        new_value={
            "name": work_order.name,
            "bom_name": bom.name,
            "quantity": str(work_order.quantity),
            "status": work_order.status,
        },
    )

    return work_order


@transaction.atomic
def work_order_approve(
    *,
    user: User,
    work_order_id: str,
) -> WorkOrder:
    from apps.inventory.models import StockEntry, StockEntryDetail, StockLedger

    PermissionChecker.check_permission(user, "manufacturing.work_order_approve")

    work_order = (
        WorkOrder.objects.select_for_update()
        .select_related("bom", "source_warehouse", "production_warehouse")
        .prefetch_related("bom__items")
        .filter(id=work_order_id)
        .first()
    )

    if not work_order:
        raise NotFoundException("Lệnh sản xuất không tồn tại")

    if work_order.status != "pending_approval":
        raise ValidationException("Chỉ có thể phê duyệt lệnh ở trạng thái 'Chờ phê duyệt'")

    stock_entry_name = f"TRF-{work_order.name}-RAW-{int(timezone.now().timestamp())}"
    stock_entry = StockEntry.objects.create(
        name=stock_entry_name,
        purpose="transfer",
        posting_date=timezone.now(),
        status="posted",
        work_order=work_order,
        remarks=f"Xuất nguyên liệu cho lệnh sản xuất {work_order.name}",
    )

    details = []
    ledgers = []
    for bom_item in work_order.bom.items.all():
        required_qty = bom_item.quantity * (Decimal(str(work_order.quantity)) / work_order.bom.quantity)
        details.append(
            StockEntryDetail(
                parent=stock_entry,
                item=bom_item.item,
                quantity=required_qty,
                source_warehouse=work_order.source_warehouse,
                target_warehouse=work_order.production_warehouse,
            )
        )
        ledgers.append(
            StockLedger(
                item=bom_item.item,
                warehouse=work_order.source_warehouse,
                posting_date=timezone.now(),
                actual_quantity=-required_qty,
                voucher_number=stock_entry.name,
                voucher_type="Transfer Issue",
            )
        )
        ledgers.append(
            StockLedger(
                item=bom_item.item,
                warehouse=work_order.production_warehouse,
                posting_date=timezone.now(),
                actual_quantity=required_qty,
                voucher_number=stock_entry.name,
                voucher_type="Transfer Receipt",
            )
        )

    if details:
        StockEntryDetail.objects.bulk_create(details)
        StockLedger.objects.bulk_create(ledgers)

    work_order.status = "in_progress"
    work_order.planned_start_date = timezone.now().date()
    work_order.save()

    create_system_log(
        user=user,
        action="approve",
        table_name="work_order",
        record_id=str(work_order.id),
        new_value={"status": "in_progress"},
    )

    return work_order


@transaction.atomic
def work_order_declare_production(
    *,
    user: User,
    work_order_id: str,
    produced_qty: Decimal,
) -> WorkOrder:
    from apps.inventory.models import StockEntry, StockEntryDetail, StockLedger

    PermissionChecker.check_permission(user, "manufacturing.work_order_declare")

    work_order = (
        WorkOrder.objects.select_for_update()
        .select_related("bom", "production_warehouse", "production_item")
        .prefetch_related("bom__items")
        .filter(id=work_order_id)
        .first()
    )

    if not work_order:
        raise NotFoundException("Lệnh sản xuất không tồn tại")

    if work_order.status != "in_progress":
        raise ValidationException("Chỉ có thể nhập liệu cho lệnh đang thực hiện")

    if produced_qty <= Decimal("0.0"):
        raise ValidationException("Số lượng sản phẩm hoàn thành phải lớn hơn 0")

    if work_order.produced_qty + produced_qty > work_order.quantity:
        raise ValidationException("Số lượng nhập liệu vượt quá yêu cầu của lệnh sản xuất")

    stock_entry_name = f"MFG-{work_order.name}-{int(timezone.now().timestamp())}"
    stock_entry = StockEntry.objects.create(
        name=stock_entry_name,
        purpose="manufacture",
        posting_date=timezone.now(),
        status="posted",
        work_order=work_order,
        remarks=f"Nhập liệu sản xuất cho lệnh {work_order.name}",
    )

    details = []
    ledgers = []

    for bom_item in work_order.bom.items.all():
        consumed_qty = bom_item.quantity * (produced_qty / work_order.bom.quantity)
        details.append(
            StockEntryDetail(
                parent=stock_entry,
                item=bom_item.item,
                quantity=consumed_qty,
                source_warehouse=work_order.production_warehouse,
            )
        )
        ledgers.append(
            StockLedger(
                item=bom_item.item,
                warehouse=work_order.production_warehouse,
                posting_date=timezone.now(),
                actual_quantity=-consumed_qty,
                voucher_number=stock_entry.name,
                voucher_type="Manufacture Consumption",
            )
        )

    details.append(
        StockEntryDetail(
            parent=stock_entry,
            item=work_order.production_item,
            quantity=produced_qty,
            target_warehouse=work_order.production_warehouse,
        )
    )
    ledgers.append(
        StockLedger(
            item=work_order.production_item,
            warehouse=work_order.production_warehouse,
            posting_date=timezone.now(),
            actual_quantity=produced_qty,
            voucher_number=stock_entry.name,
            voucher_type="Manufacture Receipt",
        )
    )

    StockEntryDetail.objects.bulk_create(details)
    StockLedger.objects.bulk_create(ledgers)

    work_order.produced_qty += Decimal(str(produced_qty))
    work_order.save()

    create_system_log(
        user=user,
        action="declare_production",
        table_name="work_order",
        record_id=str(work_order.id),
        new_value={"produced_qty": str(produced_qty), "stock_entry": stock_entry.name},
    )

    return work_order


@transaction.atomic
def work_order_complete(
    *,
    user: User,
    work_order_id: str,
) -> WorkOrder:
    from django.db.models import Sum

    from apps.inventory.models import StockEntry, StockEntryDetail, StockLedger

    PermissionChecker.check_permission(user, "manufacturing.work_order_complete")

    work_order = (
        WorkOrder.objects.select_for_update()
        .select_related("production_item", "production_warehouse", "target_warehouse")
        .filter(id=work_order_id)
        .first()
    )

    if not work_order:
        raise NotFoundException("Lệnh sản xuất không tồn tại")

    if work_order.status != "in_progress":
        raise ValidationException("Chỉ có thể hoàn thành lệnh đang thực hiện")

    manufacture_entries = StockEntry.objects.filter(purpose="manufacture", work_order=work_order, status="posted")

    total_produced_result = StockEntryDetail.objects.filter(
        parent__in=manufacture_entries,
        item=work_order.production_item,
        target_warehouse=work_order.production_warehouse,
    ).aggregate(total=Sum("quantity"))

    total_produced = total_produced_result["total"] or Decimal("0.0")

    if work_order.produced_qty < work_order.quantity:
        raise ValidationException("Chưa sản xuất đủ số lượng yêu cầu")

    if total_produced > Decimal("0.0"):
        stock_entry_name = f"TRF-{work_order.name}-FIN-{int(timezone.now().timestamp())}"
        stock_entry = StockEntry.objects.create(
            name=stock_entry_name,
            purpose="transfer",
            posting_date=timezone.now(),
            status="posted",
            work_order=work_order,
            remarks=f"Nhập kho đích thành phẩm từ lệnh {work_order.name}",
        )
        StockEntryDetail.objects.create(
            parent=stock_entry,
            item=work_order.production_item,
            quantity=total_produced,
            source_warehouse=work_order.production_warehouse,
            target_warehouse=work_order.target_warehouse,
        )
        StockLedger.objects.create(
            item=work_order.production_item,
            warehouse=work_order.production_warehouse,
            posting_date=timezone.now(),
            actual_quantity=-total_produced,
            voucher_number=stock_entry.name,
            voucher_type="Transfer Issue",
        )
        StockLedger.objects.create(
            item=work_order.production_item,
            warehouse=work_order.target_warehouse,
            posting_date=timezone.now(),
            actual_quantity=total_produced,
            voucher_number=stock_entry.name,
            voucher_type="Transfer Receipt",
        )

    work_order.status = "completed"
    work_order.actual_end_date = timezone.now().date()
    work_order.planned_end_date = timezone.now().date()
    work_order.save()

    create_system_log(
        user=user,
        action="complete",
        table_name="work_order",
        record_id=str(work_order.id),
        new_value={"status": "completed"},
    )

    return work_order


@transaction.atomic
def work_order_cancel(
    *,
    user: User,
    work_order_id: str,
) -> WorkOrder:
    PermissionChecker.check_permission(user, "manufacturing.work_order_approve")

    work_order = WorkOrder.objects.select_for_update().filter(id=work_order_id).first()

    if not work_order:
        raise NotFoundException("Lệnh sản xuất không tồn tại")

    if work_order.status != "pending_approval":
        raise ValidationException("Chỉ có thể hủy lệnh đang chờ phê duyệt")

    work_order.status = "cancelled"
    work_order.save()

    create_system_log(
        user=user,
        action="cancel",
        table_name="work_order",
        record_id=str(work_order.id),
        new_value={"status": "cancelled"},
    )

    return work_order
