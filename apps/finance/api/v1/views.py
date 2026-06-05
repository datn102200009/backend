from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.xlib.permissions import PermissionChecker
from apps.finance.selectors import (
    cash_flow_detail,
    cash_flow_list,
    depreciation_log_list,
    fixed_asset_detail,
    fixed_asset_list,
)
from apps.finance.services import (
    cash_flow_create,
    fixed_asset_create,
    fixed_asset_delete,
    fixed_asset_update,
    run_fixed_asset_depreciation,
)

from .serializers import (
    CashFlowInputSerializer,
    CashFlowTransactionSerializer,
    FixedAssetCreateInputSerializer,
    FixedAssetDepreciationLogSerializer,
    FixedAssetSerializer,
    FixedAssetUpdateInputSerializer,
    RunDepreciationInputSerializer,
)


class CashFlowListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "finance.view_cash_flow")
        transactions = cash_flow_list()
        return Response(CashFlowTransactionSerializer(transactions, many=True).data)

    def post(self, request, *args, **kwargs):
        serializer = CashFlowInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        transaction = cash_flow_create(
            user=request.user,
            payment_type=data["payment_type"],
            amount=data["amount"],
            payment_date=data["payment_date"],
            category=data.get("category"),
            payment_method=data.get("payment_method", "bank_transfer"),
            purchase_order_id=data.get("purchase_order_id") and str(data["purchase_order_id"]),
            sales_order_id=data.get("sales_order_id") and str(data["sales_order_id"]),
            purchase_invoice_id=data.get("purchase_invoice_id") and str(data["purchase_invoice_id"]),
            sales_invoice_id=data.get("sales_invoice_id") and str(data["sales_invoice_id"]),
            remarks=data.get("remarks"),
        )
        return Response(CashFlowTransactionSerializer(transaction).data, status=status.HTTP_201_CREATED)


class CashFlowDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "finance.view_cash_flow")
        transaction = cash_flow_detail(transaction_id=str(pk))
        return Response(CashFlowTransactionSerializer(transaction).data)


class FixedAssetListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "finance.view_fixed_asset")
        assets = fixed_asset_list()

        # Simple pagination to satisfy rules_planning.md
        from django.core.paginator import Paginator

        limit = request.query_params.get("limit", 50)
        page = request.query_params.get("page", 1)
        try:
            paginator = Paginator(assets, int(limit))
            page_obj = paginator.get_page(int(page))
            data = FixedAssetSerializer(page_obj.object_list, many=True).data
            return Response(
                {
                    "count": paginator.count,
                    "total_pages": paginator.num_pages,
                    "current_page": page_obj.number,
                    "results": data,
                }
            )
        except Exception:
            return Response(FixedAssetSerializer(assets, many=True).data)

    def post(self, request, *args, **kwargs):
        serializer = FixedAssetCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        asset = fixed_asset_create(
            user=request.user,
            asset_code=data["asset_code"],
            asset_name=data["asset_name"],
            original_value=data["original_value"],
            salvage_value=data.get("salvage_value", Decimal("0.00")),
            depreciation_method=data["depreciation_method"],
            useful_life_months=data["useful_life_months"],
            designed_capacity=data.get("designed_capacity"),
            department=data.get("department"),
        )
        return Response(FixedAssetSerializer(asset).data, status=status.HTTP_201_CREATED)


class FixedAssetDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "finance.view_fixed_asset")
        asset = fixed_asset_detail(asset_id=str(pk))
        return Response(FixedAssetSerializer(asset).data)

    def patch(self, request, pk, *args, **kwargs):
        serializer = FixedAssetUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        asset = fixed_asset_update(
            user=request.user,
            asset_id=str(pk),
            asset_name=data.get("asset_name"),
            original_value=data.get("original_value"),
            salvage_value=data.get("salvage_value"),
            depreciation_method=data.get("depreciation_method"),
            useful_life_months=data.get("useful_life_months"),
            designed_capacity=data.get("designed_capacity"),
            department=data.get("department"),
        )
        return Response(FixedAssetSerializer(asset).data)

    def delete(self, request, pk, *args, **kwargs):
        fixed_asset_delete(user=request.user, asset_id=str(pk))
        return Response({"message": "Xóa tài sản cố định thành công"}, status=status.HTTP_200_OK)


class DepreciationRunAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = RunDepreciationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        logs = run_fixed_asset_depreciation(user=request.user, period=serializer.validated_data["period"])
        return Response(FixedAssetDepreciationLogSerializer(logs, many=True).data, status=status.HTTP_201_CREATED)


class DepreciationLogListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "finance.view_fixed_asset")
        period = request.query_params.get("period")
        asset_id = request.query_params.get("asset_id")
        logs = depreciation_log_list(period=period, asset_id=asset_id)

        # Simple pagination to satisfy rules_planning.md
        from django.core.paginator import Paginator

        limit = request.query_params.get("limit", 50)
        page = request.query_params.get("page", 1)
        try:
            paginator = Paginator(logs, int(limit))
            page_obj = paginator.get_page(int(page))
            data = FixedAssetDepreciationLogSerializer(page_obj.object_list, many=True).data
            return Response(
                {
                    "count": paginator.count,
                    "total_pages": paginator.num_pages,
                    "current_page": page_obj.number,
                    "results": data,
                }
            )
        except Exception:
            return Response(FixedAssetDepreciationLogSerializer(logs, many=True).data)
