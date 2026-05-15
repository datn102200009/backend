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

    Args:
        user: User thực hiện hành động
        stock_entry_id: ID của phiếu nhập

    Returns:
        StockEntry object

    Raises:
        PermissionException: Nếu user không có quyền
        NotFoundException: Nếu phiếu không tồn tại
        ValidationException: Nếu phiếu ở trạng thái không hợp lệ
    """
    # Kiểm tra phân quyền
    PermissionChecker.check_permission(user, "inventory.stock_in_approve")

    # Lấy phiếu
    stock_entry = StockEntry.objects.filter(id=stock_entry_id).first()
    if not stock_entry:
        raise NotFoundException(f"Stock Entry với ID {stock_entry_id} không tồn tại")

    if stock_entry.status != "draft":
        raise ValidationException(
            f"Chỉ có thể phê duyệt phiếu ở trạng thái Draft. Phiếu hiện tại: {stock_entry.status}"
        )

    # Ghi sổ cái cho từng chi tiết
    for detail in stock_entry.details.all():
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
def stock_issue_for_manufacturing_create(
    *,
    user: User,
    name: str,
    posting_date: str,
    work_order_id: str,
    source_warehouse_id: str,
    remarks: Optional[str] = None,
) -> StockEntry:
    """
    Tạo phiếu xuất kho cho sản xuất dựa trên BOM của sản phẩm.

    Args:
        user: User thực hiện hành động
        name: Tên phiếu xuất
        posting_date: Ngày hạch toán
        work_order_id: ID của lệnh sản xuất
        source_warehouse_id: ID của kho nguồn
        remarks: Ghi chú

    Returns:
        StockEntry object

    Raises:
        PermissionException: Nếu user không có quyền
        NotFoundException: Nếu lệnh hoặc BOM không tồn tại
        ValidationException: Nếu không đủ tồn kho
    """
    # Kiểm tra phân quyền
    PermissionChecker.check_permission(user, "inventory.stock_issue")

    from apps.master_data.models import WorkOrder

    # Lấy lệnh sản xuất
    work_order = WorkOrder.objects.filter(id=work_order_id).first()
    if not work_order:
        raise NotFoundException(f"Work Order với ID {work_order_id} không tồn tại")

    # Lấy BOM
    bom = BOM.objects.filter(item=work_order.item, status="active").first()
    if not bom:
        raise NotFoundException(f"Không tìm thấy BOM hoạt động cho sản phẩm {work_order.item.item_code}")

    # Lấy kho nguồn
    warehouse = Warehouse.objects.filter(id=source_warehouse_id).first()
    if not warehouse:
        raise NotFoundException(f"Warehouse với ID {source_warehouse_id} không tồn tại")

    # Kiểm tra tồn kho cho từng linh kiện
    insufficient_items = []
    for bom_item in bom.items.all():
        required_qty = bom_item.qty * work_order.qty
        available_qty = _get_available_stock(bom_item.item, warehouse)

        if available_qty < required_qty:
            insufficient_items.append(
                {
                    "item_code": bom_item.item.item_code,
                    "required": required_qty,
                    "available": available_qty,
                }
            )

    if insufficient_items:
        error_msg = "Không đủ tồn kho:\n"
        for item in insufficient_items:
            error_msg += f"- {item['item_code']}: cần {item['required']}, " f"có {item['available']}\n"
        raise ValidationException(error_msg)

    # Tạo phiếu xuất
    stock_entry = StockEntry.objects.create(
        name=name,
        purpose="issue",
        posting_date=posting_date,
        remarks=remarks,
        status="draft",
    )

    # Thêm chi tiết từ BOM
    for bom_item in bom.items.all():
        required_qty = bom_item.qty * work_order.qty
        StockEntryDetail.objects.create(
            parent=stock_entry,
            item=bom_item.item,
            quantity=required_qty,
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
            "work_order_id": work_order_id,
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

    Args:
        user: User thực hiện hành động
        stock_entry_id: ID của phiếu xuất

    Returns:
        StockEntry object
    """
    # Kiểm tra phân quyền
    PermissionChecker.check_permission(user, "inventory.stock_issue_approve")

    # Lấy phiếu
    stock_entry = StockEntry.objects.filter(id=stock_entry_id).first()
    if not stock_entry:
        raise NotFoundException(f"Stock Entry với ID {stock_entry_id} không tồn tại")

    if stock_entry.status != "draft":
        raise ValidationException(
            f"Chỉ có thể phê duyệt phiếu ở trạng thái Draft. Phiếu hiện tại: {stock_entry.status}"
        )

    # Ghi sổ cái cho từng chi tiết (âm tính vì là xuất kho)
    for detail in stock_entry.details.all():
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

    # Kiểm tra tồn kho cho từng item
    for detail in details:
        item = Item.objects.filter(id=detail["item_id"]).first()
        if not item:
            raise NotFoundException(f"Item với ID {detail['item_id']} không tồn tại")

        available_qty = _get_available_stock(item, source_warehouse)
        if available_qty < detail["quantity"]:
            raise ValidationException(
                f"Không đủ tồn kho cho {item.item_code}. " f"Cần {detail['quantity']}, có {available_qty}"
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
        item = Item.objects.filter(id=detail["item_id"]).first()
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

    # Lấy phiếu
    stock_entry = StockEntry.objects.filter(id=stock_entry_id).first()
    if not stock_entry:
        raise NotFoundException(f"Stock Entry với ID {stock_entry_id} không tồn tại")

    if stock_entry.status != "draft":
        raise ValidationException(
            f"Chỉ có thể phê duyệt phiếu ở trạng thái Draft. Phiếu hiện tại: {stock_entry.status}"
        )

    # Double Transaction: Ghi sổ cái cho cả kho nguồn (âm) và kho đích (dương)
    for detail in stock_entry.details.all():
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
