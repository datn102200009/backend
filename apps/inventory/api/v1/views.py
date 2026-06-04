"""
Views for inventory API v1.

Orchestrates request processing: validate input, call services/selectors, return response.
"""

import logging

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.inventory.api.v1.serializers import (
    BOMSerializer,
    ItemCreateUpdateSerializer,
    ItemSerializer,
    StockEntrySerializer,
    StockEntryUpdateSerializer,
    StockInCreateSerializer,
    StockIssueCreateSerializer,
    StockLedgerSerializer,
    StockTransferCreateSerializer,
)
from apps.inventory.models import StockEntry
from apps.inventory.selectors import (
    bom_by_item,
    bom_list_active,
    item_check_duplicate_code,
    item_list_active,
    item_list_by_group,
    item_search,
    stock_entry_detail_list,
    stock_entry_list_by_status,
    stock_ledger_balance,
    stock_ledger_balance_by_item_warehouse,
    stock_ledger_list_by_item,
    stock_ledger_list_by_warehouse,
)
from apps.inventory.services import (
    stock_entry_update,
    stock_in_approve,
    stock_in_create,
    stock_issue_approve,
    stock_issue_create,
    stock_transfer_approve,
    stock_transfer_create,
)
from apps.master_data.models import BOM, Item, Warehouse

logger = logging.getLogger(__name__)

# ======================== Stock In (Nhập Kho) ========================


@api_view(["POST"])
def stock_in_create_view(request):
    """
    Tạo phiếu nhập kho.

    POST /api/v1/inventory/stock-in/create/
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "inventory.stock_in")

    # Validate input
    serializer = StockInCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Gọi service
    stock_entry = stock_in_create(
        user=user,
        name=serializer.validated_data["name"],
        posting_date=serializer.validated_data["posting_date"],
        details=serializer.validated_data["details"],
        remarks=serializer.validated_data.get("remarks", ""),
    )

    # Return response
    return Response(
        StockEntrySerializer(stock_entry).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def stock_in_approve_view(request, stock_entry_id):
    """
    Phê duyệt phiếu nhập kho.

    POST /api/v1/inventory/stock-in/{stock_entry_id}/approve/
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "inventory.stock_in_approve")

    stock_entry = stock_in_approve(
        user=user,
        stock_entry_id=stock_entry_id,
    )

    return Response(
        StockEntrySerializer(stock_entry).data,
        status=status.HTTP_200_OK,
    )


# ======================== Stock Issue (Xuất Kho) ========================


@api_view(["POST"])
def stock_issue_create_view(request):
    """
    Tạo phiếu xuất kho.

    POST /api/v1/inventory/stock-issue/create/
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "inventory.stock_issue")

    serializer = StockIssueCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    stock_entry = stock_issue_create(
        user=user,
        name=serializer.validated_data["name"],
        posting_date=serializer.validated_data["posting_date"],
        source_warehouse_id=str(serializer.validated_data["source_warehouse_id"]),
        details=serializer.validated_data["details"],
        remarks=serializer.validated_data.get("remarks", ""),
    )

    return Response(
        StockEntrySerializer(stock_entry).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def stock_issue_approve_view(request, stock_entry_id):
    """
    Phê duyệt phiếu xuất kho.

    POST /api/v1/inventory/stock-issue/{stock_entry_id}/approve/
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "inventory.stock_issue_approve")

    stock_entry = stock_issue_approve(
        user=user,
        stock_entry_id=stock_entry_id,
    )

    return Response(
        StockEntrySerializer(stock_entry).data,
        status=status.HTTP_200_OK,
    )


# ======================== Stock Transfer (Chuyển Kho) ========================


@api_view(["POST"])
def stock_transfer_create_view(request):
    """
    Tạo phiếu chuyển kho nội bộ.

    POST /api/v1/inventory/stock-transfer/create/
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "inventory.stock_transfer")

    serializer = StockTransferCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    stock_entry = stock_transfer_create(
        user=user,
        name=serializer.validated_data["name"],
        posting_date=serializer.validated_data["posting_date"],
        source_warehouse_id=str(serializer.validated_data["source_warehouse_id"]),
        target_warehouse_id=str(serializer.validated_data["target_warehouse_id"]),
        details=serializer.validated_data["details"],
        remarks=serializer.validated_data.get("remarks", ""),
    )

    return Response(
        StockEntrySerializer(stock_entry).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def stock_transfer_approve_view(request, stock_entry_id):
    """
    Phê duyệt phiếu chuyển kho.

    POST /api/v1/inventory/stock-transfer/{stock_entry_id}/approve/
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "inventory.stock_transfer_approve")

    stock_entry = stock_transfer_approve(
        user=user,
        stock_entry_id=stock_entry_id,
    )

    return Response(
        StockEntrySerializer(stock_entry).data,
        status=status.HTTP_200_OK,
    )


# ======================== Stock Ledger Query ========================


@api_view(["GET"])
def stock_ledger_balance_view(request):
    """
    Lấy tồn kho của một warehouse.

    GET /api/v1/inventory/stock-ledger/balance/?warehouse_id=...
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "inventory.view")

    warehouse_id = request.query_params.get("warehouse_id")
    warehouse = None
    if warehouse_id:
        try:
            warehouse = Warehouse.objects.filter(id=warehouse_id).first()
        except (ValidationError, ValueError):
            raise ValidationException("warehouse_id không hợp lệ (phải là UUID)")
        if not warehouse:
            raise NotFoundException(f"Warehouse với ID {warehouse_id} không tồn tại")

    detailed = request.query_params.get("detailed", "false").lower() == "true"
    data = stock_ledger_balance(warehouse, detailed=detailed)
    return Response(list(data), status=status.HTTP_200_OK)


# ======================== Stock Entry List ========================


@api_view(["GET"])
def stock_entry_list_view(request):
    """
    Lấy danh sách phiếu stock entry theo trạng thái.

    GET /api/v1/inventory/stock-entry/list/?status=draft&purpose=receipt
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "inventory.view")

    status_param = request.query_params.get("status", "draft")
    purpose = request.query_params.get("purpose")

    entries = stock_entry_list_by_status(status_param, purpose)
    serializer = StockEntrySerializer(entries, many=True)

    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
def stock_entry_update_view(request, stock_entry_id):
    """
    Cập nhật thông tin chi tiết (kho nguồn/đích) của phiếu kho nháp trước khi duyệt.

    POST /api/v1/inventory/stock-entry/{stock_entry_id}/update/
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Lấy StockEntry trước để check purpose cho phân quyền động
    stock_entry = StockEntry.objects.filter(id=stock_entry_id).first()
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

    serializer = StockEntryUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    updated_entry = stock_entry_update(
        user=user, stock_entry_id=stock_entry_id, details=serializer.validated_data["details"]
    )

    return Response(StockEntrySerializer(updated_entry).data, status=status.HTTP_200_OK)
