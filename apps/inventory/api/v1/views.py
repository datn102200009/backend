"""
Views for inventory API v1.

Orchestrates request processing: validate input, call services/selectors, return response.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.common.xlib.exceptions import NotFoundException, PermissionException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.inventory.api.v1.serializers import (
    BOMSerializer,
    ItemCreateUpdateSerializer,
    ItemSerializer,
    StockEntrySerializer,
    StockInCreateSerializer,
    StockIssueForManufacturingSerializer,
    StockLedgerSerializer,
    StockTransferCreateSerializer,
)
from apps.inventory.selectors import (
    bom_by_item,
    bom_list_active,
    item_check_duplicate_code,
    item_list_active,
    item_list_by_group,
    item_search,
    stock_entry_detail_list,
    stock_entry_list_by_status,
    stock_ledger_balance_by_item_warehouse,
    stock_ledger_balance_by_warehouse,
    stock_ledger_list_by_item,
    stock_ledger_list_by_warehouse,
)
from apps.inventory.services import (
    stock_in_approve,
    stock_in_create,
    stock_issue_approve,
    stock_issue_for_manufacturing_create,
    stock_transfer_approve,
    stock_transfer_create,
)
from apps.master_data.models import BOM, Item, Warehouse

# ======================== Stock In (Nhập Kho) ========================


@api_view(["POST"])
def stock_in_create_view(request):
    """
    Tạo phiếu nhập kho.

    POST /api/v1/inventory/stock-in/create/
    {
        "name": "SI-001",
        "posting_date": "2024-01-15T10:00:00Z",
        "remarks": "Nhập từ nhà cung cấp ABC",
        "details": [
            {
                "item_id": "...",
                "quantity": 100,
                "target_warehouse_id": "..."
            }
        ]
    }
    """
    try:
        # Kiểm tra user
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        PermissionChecker.check_permission(user, "inventory.stock_in")

        # Validate input
        serializer = StockInCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

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

    except PermissionException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )
    except ValidationException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except NotFoundException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Lỗi server: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
def stock_in_approve_view(request, stock_entry_id):
    """
    Phê duyệt phiếu nhập kho.

    POST /api/v1/inventory/stock-in/{stock_entry_id}/approve/
    """
    try:
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

    except PermissionException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )
    except ValidationException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except NotFoundException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Lỗi server: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ======================== Stock Issue (Xuất Kho) ========================


@api_view(["POST"])
def stock_issue_for_manufacturing_view(request):
    """
    Tạo phiếu xuất kho cho sản xuất.

    POST /api/v1/inventory/stock-issue/create/
    {
        "name": "SI-001",
        "posting_date": "2024-01-15T10:00:00Z",
        "work_order_id": "...",
        "source_warehouse_id": "...",
        "remarks": "Xuất cho lệnh sản xuất"
    }
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        PermissionChecker.check_permission(user, "inventory.stock_issue")

        serializer = StockIssueForManufacturingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stock_entry = stock_issue_for_manufacturing_create(
            user=user,
            name=serializer.validated_data["name"],
            posting_date=serializer.validated_data["posting_date"],
            work_order_id=str(serializer.validated_data["work_order_id"]),
            source_warehouse_id=str(serializer.validated_data["source_warehouse_id"]),
            remarks=serializer.validated_data.get("remarks", ""),
        )

        return Response(
            StockEntrySerializer(stock_entry).data,
            status=status.HTTP_201_CREATED,
        )

    except PermissionException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )
    except ValidationException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except NotFoundException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Lỗi server: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
def stock_issue_approve_view(request, stock_entry_id):
    """
    Phê duyệt phiếu xuất kho.

    POST /api/v1/inventory/stock-issue/{stock_entry_id}/approve/
    """
    try:
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

    except PermissionException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )
    except ValidationException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except NotFoundException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Lỗi server: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ======================== Stock Transfer (Chuyển Kho) ========================


@api_view(["POST"])
def stock_transfer_create_view(request):
    """
    Tạo phiếu chuyển kho nội bộ.

    POST /api/v1/inventory/stock-transfer/create/
    {
        "name": "ST-001",
        "posting_date": "2024-01-15T10:00:00Z",
        "source_warehouse_id": "...",
        "target_warehouse_id": "...",
        "remarks": "Chuyển kho",
        "details": [
            {
                "item_id": "...",
                "quantity": 50
            }
        ]
    }
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        PermissionChecker.check_permission(user, "inventory.stock_transfer")

        serializer = StockTransferCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

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

    except PermissionException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )
    except ValidationException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except NotFoundException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Lỗi server: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
def stock_transfer_approve_view(request, stock_entry_id):
    """
    Phê duyệt phiếu chuyển kho.

    POST /api/v1/inventory/stock-transfer/{stock_entry_id}/approve/
    """
    try:
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

    except PermissionException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )
    except ValidationException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except NotFoundException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Lỗi server: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ======================== Stock Ledger Query ========================


@api_view(["GET"])
def stock_ledger_balance_view(request):
    """
    Lấy tồn kho của một warehouse.

    GET /api/v1/inventory/stock-ledger/balance/?warehouse_id=...
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Kiểm tra quyền xem
        PermissionChecker.check_permission(user, "inventory.view")

        warehouse_id = request.query_params.get("warehouse_id")
        if not warehouse_id:
            return Response(
                {"error": "warehouse_id là bắt buộc"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        warehouse = Warehouse.objects.filter(id=warehouse_id).first()
        if not warehouse:
            return Response(
                {"error": f"Warehouse với ID {warehouse_id} không tồn tại"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = stock_ledger_balance_by_warehouse(warehouse)
        return Response(list(data), status=status.HTTP_200_OK)

    except PermissionException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        return Response(
            {"error": f"Lỗi server: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ======================== Stock Entry List ========================


@api_view(["GET"])
def stock_entry_list_view(request):
    """
    Lấy danh sách phiếu stock entry theo trạng thái.

    GET /api/v1/inventory/stock-entry/list/?status=draft&purpose=receipt
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Kiểm tra quyền xem
        PermissionChecker.check_permission(user, "inventory.view")

        status_param = request.query_params.get("status", "draft")
        purpose = request.query_params.get("purpose")

        entries = stock_entry_list_by_status(status_param, purpose)
        serializer = StockEntrySerializer(entries, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    except PermissionException as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        return Response(
            {"error": f"Lỗi server: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
