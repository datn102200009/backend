"""
Services for inventory app.

All write operations (Create, Update, Delete) should be defined here.
Never receive request objects, only primitive types or DTOs.
Always ensure atomic transactions.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import DecimalField, Sum

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.inventory.models import StockEntry, StockEntryDetail, StockLedger
from apps.master_data.models import BOM, Item, Warehouse

# ======================== Stock In (Nhập Kho) ========================


@transaction.atomic
def stock_in_create(
    *,
    user: User,
    name: str,
    posting_date: str,
    details: List[Dict[str, Any]],
    remarks: Optional[str] = None,
) -> StockEntry:
    """
    Tạo phiếu nhập kho.

    Args:
        user: User thực hiện hành động
        name: Tên phiếu nhập
        posting_date: Ngày hạch toán
        details: Danh sách chi tiết [{"item_id": "...", "quantity": 10, "target_warehouse_id": "..."}]
        remarks: Ghi chú

    Returns:
        StockEntry object

    Raises:
        PermissionException: Nếu user không có quyền
        ValidationException: Nếu dữ liệu không hợp lệ
    """
    # Kiểm tra phân quyền
    PermissionChecker.check_permission(user, "inventory.stock_in")

    # Xác thực dữ liệu
    if not details:
        raise ValidationException("Phiếu nhập phải có ít nhất một chi tiết")

    # Kiểm tra duplicate name
    if StockEntry.objects.filter(name=name).exists():
        raise ValidationException(f"Phiếu nhập '{name}' đã tồn tại")

    # Tạo phiếu nhập
    stock_entry = StockEntry.objects.create(
        name=name,
        purpose="receipt",
        posting_date=posting_date,
        remarks=remarks,
        status="draft",
    )

    # Thêm chi tiết
    for detail in details:
        item = Item.objects.filter(id=detail["item_id"]).first()
        if not item:
            raise NotFoundException(f"Item với ID {detail['item_id']} không tồn tại")

        warehouse = Warehouse.objects.filter(id=detail["target_warehouse_id"]).first()
        if not warehouse:
            raise NotFoundException(f"Warehouse với ID {detail['target_warehouse_id']} không tồn tại")

        StockEntryDetail.objects.create(
            parent=stock_entry,
            item=item,
            quantity=detail["quantity"],
            target_warehouse=warehouse,
        )

    # Ghi log
    create_system_log(
        user=user,
        action="create",
        table_name="stock_entry",
        record_id=str(stock_entry.id),
        new_value={
            "name": stock_entry.name,
            "purpose": stock_entry.purpose,
            "status": stock_entry.status,
        },
    )

    return stock_entry


@transaction.atomic
def stock_in_approve(
    *,
    user: User,
    stock_entry_id: str,
) -> StockEntry:
    """
    Phê duyệt phiếu nhập kho và ghi sổ cái.
    """
    # Kiểm tra phân quyền
    PermissionChecker.check_permission(user, "inventory.stock_in_approve")

    # Lấy và khóa phiếu kho
    stock_entry = StockEntry.objects.select_for_update().filter(id=stock_entry_id).first()
    if not stock_entry:
        raise NotFoundException(f"Stock Entry với ID {stock_entry_id} không tồn tại")

    if stock_entry.status != "draft":
        raise ValidationException(
            f"Chỉ có thể phê duyệt phiếu ở trạng thái Draft. Phiếu hiện tại: {stock_entry.status}"
        )

    # Khóa các dòng sản phẩm (Item) liên quan theo thứ tự ID tăng dần để ngăn race condition và deadlock
    detail_item_ids = list(stock_entry.details.values_list("item_id", flat=True))
    Item.objects.select_for_update().filter(id__in=detail_item_ids).order_by("id")

    # Ghi sổ cái cho từng chi tiết
    for detail in stock_entry.details.all():
        if not detail.target_warehouse:
            raise ValidationException(f"Dòng sản phẩm '{detail.item.item_code}' chưa được chỉ định kho nhập.")

        StockLedger.objects.create(
            item=detail.item,
            warehouse=detail.target_warehouse,
            posting_date=stock_entry.posting_date,
            actual_quantity=detail.quantity,
            voucher_number=stock_entry.name,
            voucher_type="Stock In",
        )

    # Cập nhật trạng thái
    stock_entry.status = "posted"
    stock_entry.save()

    # Kích hoạt tính toán lại trạng thái Đơn mua hàng liên kết (nếu có)
    if stock_entry.purchase_order:
        from apps.purchasing.services import purchase_order_update_status

        purchase_order_update_status(stock_entry.purchase_order)

    # Ghi log
    create_system_log(
        user=user,
        action="approve",
        table_name="stock_entry",
        record_id=str(stock_entry.id),
        new_value={"status": stock_entry.status},
    )

    return stock_entry


# ======================== Stock Out / Issue (Xuất Kho) ========================


@transaction.atomic
def stock_issue_create(
    *,
    user: User,
    name: str,
    posting_date: str,
    source_warehouse_id: str,
    details: List[Dict[str, Any]],
    remarks: Optional[str] = None,
) -> StockEntry:
    """
    Tạo phiếu xuất kho.

    Args:
        user: User thực hiện hành động
        name: Tên phiếu xuất
        posting_date: Ngày hạch toán
        source_warehouse_id: ID của kho nguồn
        details: Danh sách chi tiết [{"item_id": "...", "quantity": 10}]
        remarks: Ghi chú

    Returns:
        StockEntry object

    Raises:
        PermissionException: Nếu user không có quyền
        NotFoundException: Nếu kho hoặc item không tồn tại
        ValidationException: Nếu không đủ tồn kho
    """
    # Kiểm tra phân quyền
    PermissionChecker.check_permission(user, "inventory.stock_issue")

    # Lấy kho nguồn
    warehouse = Warehouse.objects.filter(id=source_warehouse_id).first()
    if not warehouse:
        raise NotFoundException(f"Warehouse với ID {source_warehouse_id} không tồn tại")

    if not details:
        raise ValidationException("Chi tiết phiếu xuất không được để trống")

    # Prefetch items (H-06)
    item_ids = [str(detail["item_id"]) for detail in details]
    items_map = {
        str(item.id): item for item in Item.objects.filter(id__in=item_ids).only("id", "item_code", "item_name")
    }

    # Check missing items
    missing_ids = set(item_ids) - set(items_map.keys())
    if missing_ids:
        raise NotFoundException(f"Item với ID {', '.join(str(i) for i in missing_ids)} không tồn tại")

    # Kiểm tra tồn kho cho từng linh kiện
    insufficient_items = []
    for detail in details:
        item = items_map[str(detail["item_id"])]
        required_qty = detail["quantity"]
        available_qty = _get_available_stock(item, warehouse)

        if available_qty < required_qty:
            insufficient_items.append(
                {
                    "item_code": item.item_code,
                    "required": required_qty,
                    "available": available_qty,
                }
            )

    if insufficient_items:
        error_msg = "Không đủ tồn kho:\n"
        for i_item in insufficient_items:
            error_msg += f"- {i_item['item_code']}: cần {i_item['required']}, có {i_item['available']}\n"
        raise ValidationException(error_msg)

    # Tạo phiếu xuất
    stock_entry = StockEntry.objects.create(
        name=name,
        purpose="issue",
        posting_date=posting_date,
        remarks=remarks,
        status="draft",
    )

    # Thêm chi tiết
    for detail in details:
        item = items_map[str(detail["item_id"])]
        StockEntryDetail.objects.create(
            parent=stock_entry,
            item=item,
            quantity=detail["quantity"],
            source_warehouse=warehouse,
        )

    # Ghi log
    create_system_log(
        user=user,
        action="create",
        table_name="stock_entry",
        record_id=str(stock_entry.id),
        new_value={
            "name": stock_entry.name,
            "purpose": stock_entry.purpose,
            "source_warehouse": str(warehouse.id),
        },
    )

    return stock_entry


@transaction.atomic
def stock_issue_approve(
    *,
    user: User,
    stock_entry_id: str,
) -> StockEntry:
    """
    Phê duyệt phiếu xuất kho và ghi sổ cái.
    """
    # Kiểm tra phân quyền
    PermissionChecker.check_permission(user, "inventory.stock_issue_approve")

    # Lấy và khóa phiếu kho
    stock_entry = StockEntry.objects.select_for_update().filter(id=stock_entry_id).first()
    if not stock_entry:
        raise NotFoundException(f"Stock Entry với ID {stock_entry_id} không tồn tại")

    if stock_entry.status != "draft":
        raise ValidationException(
            f"Chỉ có thể phê duyệt phiếu ở trạng thái Draft. Phiếu hiện tại: {stock_entry.status}"
        )

    # Ghi sổ cái cho từng chi tiết (âm tính vì là xuất kho)
    # Sắp xếp các chi tiết theo item_id trước khi thực hiện khóa hàng loạt để tránh deadlock
    details = list(stock_entry.details.select_related("item", "source_warehouse").all())
    details.sort(key=lambda d: d.item_id)

    for detail in details:
        if not detail.source_warehouse:
            raise ValidationException(f"Dòng sản phẩm '{detail.item.item_code}' chưa được chỉ định kho xuất.")

        # Khóa dòng sản phẩm (Item) để ngăn race condition trong tính toán tồn kho khả dụng
        Item.objects.select_for_update().get(id=detail.item_id)

        # Kiểm tra tồn kho khả dụng tại thời điểm duyệt
        available_qty = _get_available_stock(detail.item, detail.source_warehouse)
        if available_qty < detail.quantity:
            raise ValidationException(
                f"Không đủ tồn kho cho sản phẩm '{detail.item.item_code}' tại kho '{detail.source_warehouse.name}'. "
                f"Khả dụng: {available_qty}, Yêu cầu: {detail.quantity}"
            )

        StockLedger.objects.create(
            item=detail.item,
            warehouse=detail.source_warehouse,
            posting_date=stock_entry.posting_date,
            actual_quantity=-detail.quantity,  # Âm vì là xuất
            voucher_number=stock_entry.name,
            voucher_type="Stock Issue",
        )

    # Cập nhật trạng thái
    stock_entry.status = "posted"
    stock_entry.save()

    # Kích hoạt tính toán lại trạng thái Đơn bán hàng liên kết (nếu có)
    if stock_entry.sales_order:
        from apps.sales.services import sales_order_update_status

        sales_order_update_status(stock_entry.sales_order)

    # Ghi log
    create_system_log(
        user=user,
        action="approve",
        table_name="stock_entry",
        record_id=str(stock_entry.id),
        new_value={"status": stock_entry.status},
    )

    return stock_entry


# ======================== Internal Transfer (Chuyển Kho Nội Bộ) ========================


@transaction.atomic
def stock_transfer_create(
    *,
    user: User,
    name: str,
    posting_date: str,
    source_warehouse_id: str,
    target_warehouse_id: str,
    details: List[Dict[str, Any]],
    remarks: Optional[str] = None,
) -> StockEntry:
    """
    Tạo phiếu chuyển kho nội bộ.

    Args:
        user: User thực hiện hành động
        name: Tên phiếu chuyển
        posting_date: Ngày hạch toán
        source_warehouse_id: ID của kho nguồn
        target_warehouse_id: ID của kho đích
        details: Danh sách chi tiết [{"item_id": "...", "quantity": 10}]
        remarks: Ghi chú

    Returns:
        StockEntry object
    """
    # Kiểm tra phân quyền
    PermissionChecker.check_permission(user, "inventory.stock_transfer")

    # Lấy các kho
    source_warehouse = Warehouse.objects.filter(id=source_warehouse_id).first()
    if not source_warehouse:
        raise NotFoundException(f"Kho nguồn với ID {source_warehouse_id} không tồn tại")

    target_warehouse = Warehouse.objects.filter(id=target_warehouse_id).first()
    if not target_warehouse:
        raise NotFoundException(f"Kho đích với ID {target_warehouse_id} không tồn tại")

    # Kiểm tra xem kho có khác nhau không
    if source_warehouse_id == target_warehouse_id:
        raise ValidationException("Kho nguồn và kho đích phải khác nhau")

    if not details:
        raise ValidationException("Chi tiết chuyển kho không được để trống")

    # Prefetch items (H-06)
    item_ids = [str(detail["item_id"]) for detail in details]
    items_map = {
        str(item.id): item for item in Item.objects.filter(id__in=item_ids).only("id", "item_code", "item_name")
    }

    # Check missing items
    missing_ids = set(item_ids) - set(items_map.keys())
    if missing_ids:
        raise NotFoundException(f"Item với ID {', '.join(str(i) for i in missing_ids)} không tồn tại")

    # Kiểm tra tồn kho cho từng item
    for detail in details:
        item = items_map[str(detail["item_id"])]
        available_qty = _get_available_stock(item, source_warehouse)
        if available_qty < detail["quantity"]:
            raise ValidationException(
                f"Không đủ tồn kho cho {item.item_code}. Cần {detail['quantity']}, có {available_qty}"
            )

    # Tạo phiếu chuyển
    stock_entry = StockEntry.objects.create(
        name=name,
        purpose="transfer",
        posting_date=posting_date,
        remarks=remarks,
        status="draft",
    )

    # Thêm chi tiết
    for detail in details:
        item = items_map[str(detail["item_id"])]
        StockEntryDetail.objects.create(
            parent=stock_entry,
            item=item,
            quantity=detail["quantity"],
            source_warehouse=source_warehouse,
            target_warehouse=target_warehouse,
        )

    # Ghi log
    create_system_log(
        user=user,
        action="create",
        table_name="stock_entry",
        record_id=str(stock_entry.id),
        new_value={
            "name": stock_entry.name,
            "purpose": stock_entry.purpose,
            "source_warehouse": str(source_warehouse.id),
            "target_warehouse": str(target_warehouse.id),
        },
    )

    return stock_entry


@transaction.atomic
def stock_transfer_approve(
    *,
    user: User,
    stock_entry_id: str,
) -> StockEntry:
    """
    Phê duyệt phiếu chuyển kho (Double Transaction).
    Ghi cả trừ kho nguồn và cộng kho đích trong một transaction.

    Args:
        user: User thực hiện hành động
        stock_entry_id: ID của phiếu chuyển

    Returns:
        StockEntry object
    """
    # Kiểm tra phân quyền
    PermissionChecker.check_permission(user, "inventory.stock_transfer_approve")

    # Lấy và khóa phiếu kho
    stock_entry = StockEntry.objects.select_for_update().filter(id=stock_entry_id).first()
    if not stock_entry:
        raise NotFoundException(f"Stock Entry với ID {stock_entry_id} không tồn tại")

    if stock_entry.status != "draft":
        raise ValidationException(
            f"Chỉ có thể phê duyệt phiếu ở trạng thái Draft. Phiếu hiện tại: {stock_entry.status}"
        )

    # Sắp xếp các chi tiết theo item_id trước khi thực hiện khóa hàng loạt để tránh deadlock
    details = list(stock_entry.details.select_related("item", "source_warehouse", "target_warehouse").all())
    details.sort(key=lambda d: d.item_id)

    # Double Transaction: Ghi sổ cái cho cả kho nguồn (âm) và kho đích (dương)
    for detail in details:
        if not detail.source_warehouse:
            raise ValidationException(f"Dòng sản phẩm '{detail.item.item_code}' chưa được chỉ định kho xuất.")
        if not detail.target_warehouse:
            raise ValidationException(f"Dòng sản phẩm '{detail.item.item_code}' chưa được chỉ định kho nhập.")

        # Khóa dòng sản phẩm (Item) để ngăn race condition trong tính toán tồn kho khả dụng kho nguồn
        Item.objects.select_for_update().get(id=detail.item_id)

        # Kiểm tra tồn kho khả dụng tại thời điểm duyệt của kho nguồn
        available_qty = _get_available_stock(detail.item, detail.source_warehouse)
        if available_qty < detail.quantity:
            raise ValidationException(
                f"Không đủ tồn kho cho sản phẩm '{detail.item.item_code}' tại kho nguồn '{detail.source_warehouse.name}'. "
                f"Khả dụng: {available_qty}, Yêu cầu: {detail.quantity}"
            )

        # Trừ kho nguồn
        StockLedger.objects.create(
            item=detail.item,
            warehouse=detail.source_warehouse,
            posting_date=stock_entry.posting_date,
            actual_quantity=-detail.quantity,
            voucher_number=stock_entry.name,
            voucher_type="Stock Transfer Out",
        )

        # Cộng kho đích
        StockLedger.objects.create(
            item=detail.item,
            warehouse=detail.target_warehouse,
            posting_date=stock_entry.posting_date,
            actual_quantity=detail.quantity,
            voucher_number=stock_entry.name,
            voucher_type="Stock Transfer In",
        )

    # Cập nhật trạng thái
    stock_entry.status = "posted"
    stock_entry.save()

    # Ghi log
    create_system_log(
        user=user,
        action="approve",
        table_name="stock_entry",
        record_id=str(stock_entry.id),
        new_value={"status": stock_entry.status},
    )

    return stock_entry


# ======================== Utility Functions ========================


def _get_available_stock(item: Item, warehouse: Warehouse) -> Decimal:
    """
    Tính tồn kho hiện tại của một item trong một warehouse.

    Args:
        item: Item object
        warehouse: Warehouse object

    Returns:
        Số lượng tồn kho
    """
    total = StockLedger.objects.filter(
        item=item,
        warehouse=warehouse,
    ).aggregate(
        total=Sum("actual_quantity", output_field=DecimalField())
    )["total"]

    if total is None:
        return Decimal("0.00")
    return Decimal(str(total))


@transaction.atomic
def stock_entry_update(
    *,
    user: User,
    stock_entry_id: str,
    details: List[Dict[str, Any]],
    remarks: Optional[str] = None,
) -> StockEntry:
    """
    Cập nhật thông tin chi tiết và ghi chú của một phiếu kho nháp (draft).
    Cho phép thủ kho chỉ định/chọn kho nguồn/đích cho từng dòng sản phẩm.
    """
    stock_entry = StockEntry.objects.select_for_update().filter(id=stock_entry_id).first()
    if not stock_entry:
        raise NotFoundException(f"Stock Entry với ID {stock_entry_id} không tồn tại")

    # Xác định quyền dựa theo purpose của phiếu kho
    purpose = stock_entry.purpose
    if purpose == "receipt":
        permission = "inventory.stock_in"
    elif purpose == "issue":
        permission = "inventory.stock_issue"
    elif purpose == "transfer":
        permission = "inventory.stock_transfer"
    else:
        permission = "inventory.stock_in"  # Fallback

    PermissionChecker.check_permission(user, permission)

    if stock_entry.status != "draft":
        raise ValidationException("Chỉ được phép cập nhật phiếu kho khi đang ở trạng thái Draft")

    if remarks is not None:
        stock_entry.remarks = remarks

    # Kiểm tra xem details truyền vào có chứa detail_id hay không
    if details and "detail_id" in details[0]:
        # Cập nhật các dòng chi tiết hiện tại (không xóa đi tạo lại)
        for detail in details:
            dt_obj = stock_entry.details.filter(id=detail["detail_id"]).first()
            if not dt_obj:
                raise NotFoundException(
                    f"Chi tiết phiếu kho với ID {detail['detail_id']} không tồn tại hoặc không thuộc phiếu kho này"
                )

            if "source_warehouse_id" in detail:
                source_wh = None
                if detail["source_warehouse_id"]:
                    source_wh = Warehouse.objects.filter(id=detail["source_warehouse_id"]).first()
                    if not source_wh:
                        raise NotFoundException(f"Warehouse nguồn với ID {detail['source_warehouse_id']} không tồn tại")
                dt_obj.source_warehouse = source_wh

            if "target_warehouse_id" in detail:
                target_wh = None
                if detail["target_warehouse_id"]:
                    target_wh = Warehouse.objects.filter(id=detail["target_warehouse_id"]).first()
                    if not target_wh:
                        raise NotFoundException(f"Warehouse đích với ID {detail['target_warehouse_id']} không tồn tại")
                dt_obj.target_warehouse = target_wh

            if "quantity" in detail:
                dt_obj.quantity = detail["quantity"]

            dt_obj.save()
    else:
        # Xóa các chi tiết cũ và tạo lại mới
        stock_entry.details.all().delete()

        for detail in details:
            item = Item.objects.filter(id=detail["item_id"]).first()
            if not item:
                raise NotFoundException(f"Sản phẩm với ID {detail['item_id']} không tồn tại")

            source_wh = None
            if detail.get("source_warehouse_id"):
                source_wh = Warehouse.objects.filter(id=detail["source_warehouse_id"]).first()
                if not source_wh:
                    raise NotFoundException(f"Warehouse nguồn với ID {detail['source_warehouse_id']} không tồn tại")

            target_wh = None
            if detail.get("target_warehouse_id"):
                target_wh = Warehouse.objects.filter(id=detail["target_warehouse_id"]).first()
                if not target_wh:
                    raise NotFoundException(f"Warehouse đích với ID {detail['target_warehouse_id']} không tồn tại")

            StockEntryDetail.objects.create(
                parent=stock_entry,
                item=item,
                quantity=detail["quantity"],
                source_warehouse=source_wh,
                target_warehouse=target_wh,
            )

    stock_entry.save()

    create_system_log(
        user=user,
        action="update",
        table_name="stock_entry",
        record_id=str(stock_entry.id),
        new_value={"remarks": remarks},
    )

    return stock_entry


@transaction.atomic
def stock_entry_cancel(
    *,
    user: User,
    stock_entry: StockEntry,
) -> StockEntry:
    """
    Chuyển trạng thái phiếu kho Draft sang Cancelled.
    """
    # Khóa phiếu kho bằng select_for_update() để chống race condition khi hủy
    stock_entry = StockEntry.objects.select_for_update().get(id=stock_entry.id)

    purpose = stock_entry.purpose
    if purpose == "receipt":
        permission = "inventory.stock_in"
    elif purpose == "issue":
        permission = "inventory.stock_issue"
    elif purpose == "transfer":
        permission = "inventory.stock_transfer"
    else:
        permission = "inventory.stock_in"

    PermissionChecker.check_permission(user, permission)

    if stock_entry.status != "draft":
        raise ValidationException("Chỉ có thể hủy phiếu kho ở trạng thái Draft.")

    stock_entry.status = "cancelled"
    stock_entry.save()

    create_system_log(
        user=user,
        action="cancel",
        table_name="stock_entry",
        record_id=str(stock_entry.id),
        new_value={"status": "cancelled"},
    )
    return stock_entry


@transaction.atomic
def stock_entry_reverse(
    *,
    user: User,
    original_entry: StockEntry,
    remarks: str,
) -> StockEntry:
    """
    Tạo một phiếu kho đảo ngược (đối ứng) ở trạng thái posted, và ghi sổ cái đối ứng.
    """
    purpose = original_entry.purpose
    if purpose == "receipt":
        permission = "inventory.stock_in_approve"
        reverse_purpose = "issue"
    elif purpose == "issue":
        permission = "inventory.stock_issue_approve"
        reverse_purpose = "receipt"
    else:
        permission = "inventory.stock_in_approve"
        reverse_purpose = "receipt"

    PermissionChecker.check_permission(user, permission)

    if original_entry.status != "posted":
        raise ValidationException("Chỉ có thể đảo ngược phiếu kho đã ghi sổ (posted).")

    import uuid

    from django.utils import timezone

    reverse_name = f"ST-REV-{reverse_purpose.upper()}-{str(uuid.uuid4())[:8]}"
    reverse_entry = StockEntry(
        name=reverse_name,
        purpose=reverse_purpose,
        posting_date=timezone.now(),
        remarks=remarks,
        status="posted",
        purchase_order=original_entry.purchase_order,
        sales_order=original_entry.sales_order,
    )
    reverse_entry.save()

    details_to_create = []
    ledgers_to_create = []

    for detail in original_entry.details.all():
        if original_entry.purpose == "receipt":
            source_wh = detail.target_warehouse
            target_wh = None
            qty_sign = -1
            ledger_voucher_type = "Stock Issue (Reversal)"
        elif original_entry.purpose == "issue":
            source_wh = None
            target_wh = detail.source_warehouse
            qty_sign = 1
            ledger_voucher_type = "Stock In (Reversal)"
        else:
            source_wh = detail.target_warehouse
            target_wh = detail.source_warehouse
            qty_sign = -1
            ledger_voucher_type = "Stock Reversal"

        rev_detail = StockEntryDetail(
            parent=reverse_entry,
            item=detail.item,
            quantity=detail.quantity,
            source_warehouse=source_wh,
            target_warehouse=target_wh,
        )
        details_to_create.append(rev_detail)

        rev_ledger = StockLedger(
            item=detail.item,
            warehouse=source_wh if source_wh else target_wh,
            posting_date=reverse_entry.posting_date,
            actual_quantity=qty_sign * detail.quantity,
            voucher_number=reverse_entry.name,
            voucher_type=ledger_voucher_type,
        )
        ledgers_to_create.append(rev_ledger)

    if details_to_create:
        StockEntryDetail.objects.bulk_create(details_to_create, batch_size=1000)
    if ledgers_to_create:
        StockLedger.objects.bulk_create(ledgers_to_create, batch_size=1000)

    create_system_log(
        user=user,
        action="approve",
        table_name="stock_entry",
        record_id=str(reverse_entry.id),
        new_value={
            "name": reverse_entry.name,
            "status": reverse_entry.status,
            "is_reversal": True,
            "original_entry_id": str(original_entry.id),
        },
    )

    return reverse_entry
