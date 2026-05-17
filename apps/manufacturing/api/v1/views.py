"""
Views for manufacturing API v1.

Orchestrates request processing: validate input, call services/selectors, return response.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.common.xlib.exceptions import NotFoundException, PermissionException, ValidationException
from apps.manufacturing.api.v1.serializers import (
    BOMCreateSerializer,
    BOMDetailSerializer,
    BOMListSerializer,
    BOMUpdateSerializer,
    MaterialPreviewRequestSerializer,
    WorkOrderCancelSerializer,
    WorkOrderCompleteSerializer,
    WorkOrderCreateSerializer,
    WorkOrderDeclareProductionSerializer,
    WorkOrderSerializer,
)
from apps.manufacturing.selectors import bom_detail, bom_list, get_material_preview, work_order_detail, work_order_list
from apps.manufacturing.services import (
    bom_create,
    bom_delete,
    bom_update,
    work_order_approve,
    work_order_cancel,
    work_order_complete,
    work_order_create,
    work_order_declare_production,
)


def _handle_exception(e: Exception) -> Response:
    """Helper xử lý chung các exception thành HTTP Response."""
    if isinstance(e, PermissionException):
        return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
    elif isinstance(e, ValidationException):
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    elif isinstance(e, NotFoundException):
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    else:
        return Response(
            {"error": f"Lỗi server: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ======================== BOM APIs ========================


@api_view(["POST"])
def bom_create_view(request):
    """
    Tạo định mức (BOM) mới.
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = BOMCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        bom = bom_create(
            user=user,
            name=serializer.validated_data["name"],
            item_id=str(serializer.validated_data["item_id"]),
            quantity=serializer.validated_data.get("quantity"),
            description=serializer.validated_data.get("description"),
            items=serializer.validated_data["items"],
        )

        # Lấy BOM full chi tiết qua selector để trả về
        result = bom_detail(bom_id=str(bom.id))
        return Response(BOMDetailSerializer(result).data, status=status.HTTP_201_CREATED)

    except Exception as e:
        return _handle_exception(e)


@api_view(["PUT"])
def bom_update_view(request, bom_id):
    """
    Cập nhật định mức (BOM).
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = BOMUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        bom = bom_update(
            user=user,
            bom_id=bom_id,
            name=serializer.validated_data.get("name"),
            quantity=serializer.validated_data.get("quantity"),
            description=serializer.validated_data.get("description"),
            items=serializer.validated_data.get("items"),
        )

        result = bom_detail(bom_id=str(bom.id))
        return Response(BOMDetailSerializer(result).data, status=status.HTTP_200_OK)

    except Exception as e:
        return _handle_exception(e)


@api_view(["DELETE"])
def bom_delete_view(request, bom_id):
    """
    Xóa định mức (BOM).
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        bom_delete(user=user, bom_id=bom_id)

        return Response({"message": "Xóa định mức thành công"}, status=status.HTTP_200_OK)

    except Exception as e:
        return _handle_exception(e)


@api_view(["GET"])
def bom_list_view(request):
    """
    Lấy danh sách định mức (BOM).
    """
    try:
        search = request.query_params.get("search")
        is_active_str = request.query_params.get("is_active")

        is_active = None
        if is_active_str is not None:
            is_active = is_active_str.lower() == "true"

        boms = bom_list(search=search, is_active=is_active)
        serializer = BOMListSerializer(boms, many=True)
        return Response({"count": len(boms), "results": serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        return _handle_exception(e)


@api_view(["GET"])
def bom_detail_view(request, bom_id):
    """
    Lấy chi tiết một định mức (BOM).
    """
    try:
        bom = bom_detail(bom_id=bom_id)
        if not bom:
            return Response(
                {"error": f"Định mức với ID {bom_id} không tồn tại"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = BOMDetailSerializer(bom)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return _handle_exception(e)


# ======================== Work Order APIs ========================


@api_view(["POST"])
def material_preview_view(request):
    """
    Xem trước nguyên liệu cần thiết cho Work Order.
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = MaterialPreviewRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        preview = get_material_preview(
            bom_id=str(serializer.validated_data["bom_id"]),
            quantity=serializer.validated_data["quantity"],
            source_warehouse_id=str(serializer.validated_data["source_warehouse_id"]),
        )
        return Response(preview, status=status.HTTP_200_OK)

    except Exception as e:
        return _handle_exception(e)


@api_view(["POST"])
def work_order_create_view(request):
    """
    Tạo lệnh sản xuất mới.
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = WorkOrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        work_order = work_order_create(
            user=user,
            name=serializer.validated_data["name"],
            bom_id=str(serializer.validated_data["bom_id"]),
            quantity=serializer.validated_data["quantity"],
            source_warehouse_id=str(serializer.validated_data["source_warehouse_id"]),
            target_warehouse_id=str(serializer.validated_data["target_warehouse_id"]),
            production_warehouse_id=str(serializer.validated_data["production_warehouse_id"]),
            planned_start_date=serializer.validated_data["planned_start_date"],
            planned_end_date=serializer.validated_data.get("planned_end_date"),
            remarks=serializer.validated_data.get("remarks"),
        )

        result = work_order_detail(work_order_id=str(work_order.id))
        return Response(WorkOrderSerializer(result).data, status=status.HTTP_201_CREATED)

    except Exception as e:
        return _handle_exception(e)


@api_view(["POST"])
def work_order_approve_view(request, work_order_id):
    """
    Phê duyệt lệnh sản xuất.
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        work_order = work_order_approve(
            user=user,
            work_order_id=work_order_id,
        )

        result = work_order_detail(work_order_id=str(work_order.id))
        return Response(WorkOrderSerializer(result).data, status=status.HTTP_200_OK)

    except Exception as e:
        return _handle_exception(e)


@api_view(["POST"])
def work_order_declare_production_view(request, work_order_id):
    """
    Nhập liệu sản xuất.
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = WorkOrderDeclareProductionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        work_order = work_order_declare_production(
            user=user,
            work_order_id=work_order_id,
            produced_qty=serializer.validated_data["produced_qty"],
        )

        result = work_order_detail(work_order_id=str(work_order.id))
        return Response(WorkOrderSerializer(result).data, status=status.HTTP_200_OK)

    except Exception as e:
        return _handle_exception(e)


@api_view(["POST"])
def work_order_complete_view(request, work_order_id):
    """
    Hoàn thành lệnh sản xuất.
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = WorkOrderCompleteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        work_order = work_order_complete(
            user=user,
            work_order_id=work_order_id,
        )

        result = work_order_detail(work_order_id=str(work_order.id))
        return Response(WorkOrderSerializer(result).data, status=status.HTTP_200_OK)

    except Exception as e:
        return _handle_exception(e)


@api_view(["GET"])
def work_order_list_view(request):
    """
    Lấy danh sách lệnh sản xuất.
    """
    try:
        search = request.query_params.get("search")
        status_param = request.query_params.get("status")

        work_orders = work_order_list(search=search, status=status_param)
        serializer = WorkOrderSerializer(work_orders, many=True)
        return Response(
            {"count": len(work_orders), "results": serializer.data},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return _handle_exception(e)


@api_view(["GET"])
def work_order_detail_view(request, work_order_id):
    """
    Lấy chi tiết một lệnh sản xuất.
    """
    try:
        work_order = work_order_detail(work_order_id=work_order_id)
        if not work_order:
            return Response(
                {"error": f"Lệnh sản xuất với ID {work_order_id} không tồn tại"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = WorkOrderSerializer(work_order)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return _handle_exception(e)


@api_view(["POST"])
def work_order_cancel_view(request, work_order_id):
    """
    Hủy lệnh sản xuất.
    """
    try:
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "User không được xác thực"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = WorkOrderCancelSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        work_order = work_order_cancel(
            user=user,
            work_order_id=work_order_id,
        )

        result = work_order_detail(work_order_id=str(work_order.id))
        return Response(WorkOrderSerializer(result).data, status=status.HTTP_200_OK)

    except Exception as e:
        return _handle_exception(e)
