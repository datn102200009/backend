"""
Views for master_data API v1.

Orchestrates request processing: validate input, call services/selectors, return response.
"""

from django.db import IntegrityError
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.master_data.api.v1.serializers import (
    ItemCreateInputSerializer,
    ItemOutputSerializer,
    ItemUpdateInputSerializer,
)
from apps.master_data.models import Item
from apps.master_data.selectors import item_get_detail, item_list, uom_list, warehouse_list
from apps.master_data.services import item_create, item_delete, item_update


@api_view(["GET"])
def uom_list_view(request):
    """
    Xem danh sách UOM.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    qs = uom_list()
    from apps.master_data.api.v1.serializers import UOMOutputSerializer

    serializer = UOMOutputSerializer(qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
def warehouse_list_view(request):
    """
    Xem danh sách Warehouse.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    qs = warehouse_list()
    from apps.master_data.api.v1.serializers import WarehouseOutputSerializer

    serializer = WarehouseOutputSerializer(qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
def item_list_view(request):
    """
    Xem danh sách vật tư (Item).
    Hỗ trợ search, status filter.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "master_data.view_item")

    search = request.query_params.get("search")
    status_param = request.query_params.get("status")

    # Simple limit offset pagination
    try:
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
        limit = min(limit, 100)
    except ValueError:
        limit = 20
        offset = 0

    qs = item_list(search=search, status=status_param)
    count = qs.count()
    results = qs[offset : offset + limit]

    serializer = ItemOutputSerializer(results, many=True)
    return Response(
        {
            "count": count,
            "next": None,  # Not fully implemented for simplicity, frontend uses count
            "previous": None,
            "results": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
def item_detail_view(request, item_code):
    """
    Xem chi tiết thông tin vật tư.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "master_data.view_item")

    try:
        item = item_get_detail(item_code=item_code)
    except Item.DoesNotExist:
        raise NotFoundException("Không tìm thấy vật tư")

    serializer = ItemOutputSerializer(item)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def item_create_view(request):
    """
    Thêm mới vật tư (Item).
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "master_data.add_item")

    serializer = ItemCreateInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Trích xuất data
    item_data = serializer.validated_data
    item_code = item_data.pop("item_code")
    item_name = item_data.pop("item_name")

    try:
        item = item_create(item_code=item_code, item_name=item_name, **item_data)
    except IntegrityError:
        raise ValidationException("Dữ liệu bị trùng lặp hoặc vi phạm ràng buộc CSDL. Vui lòng kiểm tra lại.")
    except Exception as e:
        from django.core.exceptions import ValidationError as DjangoValidationError

        if isinstance(e, DjangoValidationError):
            raise ValidationException(str(e))
        raise

    out_serializer = ItemOutputSerializer(item)

    return Response(out_serializer.data, status=status.HTTP_201_CREATED)


@api_view(["PUT"])
@throttle_classes([UserRateThrottle])
def item_update_view(request, item_code):
    """
    Cập nhật thông tin vật tư.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "master_data.change_item")

    try:
        item = item_get_detail(item_code=item_code)
    except Item.DoesNotExist:
        raise NotFoundException("Không tìm thấy vật tư")

    serializer = ItemUpdateInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        updated_item = item_update(item=item, data=serializer.validated_data)
    except IntegrityError:
        raise ValidationException("Dữ liệu bị trùng lặp hoặc vi phạm ràng buộc CSDL. Vui lòng kiểm tra lại.")
    except Exception as e:
        from django.core.exceptions import ValidationError as DjangoValidationError

        if isinstance(e, DjangoValidationError):
            raise ValidationException(str(e))
        raise

    out_serializer = ItemOutputSerializer(updated_item)

    return Response(out_serializer.data, status=status.HTTP_200_OK)


@api_view(["DELETE"])
@throttle_classes([UserRateThrottle])
def item_delete_view(request, item_code):
    """
    Xóa vật tư (Item).
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response(
            {"error": "User không được xác thực"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    PermissionChecker.check_permission(user, "master_data.delete_item")

    try:
        item = item_get_detail(item_code=item_code)
    except Item.DoesNotExist:
        raise NotFoundException("Không tìm thấy vật tư")

    try:
        item_delete(item=item)
    except Exception as e:
        from django.core.exceptions import ValidationError as DjangoValidationError

        if isinstance(e, DjangoValidationError):
            raise ValidationException(str(e))
        raise

    return Response(status=status.HTTP_204_NO_CONTENT)
