from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.xlib.permissions import PermissionChecker
from apps.finance.api.v1.serializers import SalesInvoiceSerializer
from apps.sales.selectors import sales_order_detail, sales_order_list
from apps.sales.services import (
    approve_credit_bypass,
    sales_order_approve,
    sales_order_cancel,
    sales_order_create,
    sales_order_delete,
    sales_order_deliver_goods,
    sales_order_update,
)

from .serializers import SalesOrderDeliverInputSerializer, SalesOrderInputSerializer, SalesOrderSerializer


class SalesOrderListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "sales.view_order")
        orders = sales_order_list()
        return Response(SalesOrderSerializer(orders, many=True).data)

    def post(self, request, *args, **kwargs):
        serializer = SalesOrderInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = sales_order_create(
            user=request.user,
            customer_id=str(serializer.validated_data["customer_id"]),
            advance_paid_amount=serializer.validated_data.get("advance_paid_amount", 0),
            due_date=serializer.validated_data.get("due_date"),
            lines=serializer.validated_data["lines"],
        )
        return Response(SalesOrderSerializer(order).data, status=status.HTTP_201_CREATED)


class SalesOrderDetailUpdateDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "sales.view_order")
        order = sales_order_detail(order_id=str(pk))
        return Response(SalesOrderSerializer(order).data)

    def put(self, request, pk, *args, **kwargs):
        serializer = SalesOrderInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = sales_order_update(
            user=request.user,
            order_id=str(pk),
            customer_id=str(serializer.validated_data["customer_id"]),
            advance_paid_amount=serializer.validated_data.get("advance_paid_amount", 0),
            due_date=serializer.validated_data.get("due_date"),
            lines=serializer.validated_data["lines"],
        )
        return Response(SalesOrderSerializer(order).data)

    def delete(self, request, pk, *args, **kwargs):
        sales_order_delete(user=request.user, order_id=str(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class SalesOrderDeliverAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        serializer = SalesOrderDeliverInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invoice = sales_order_deliver_goods(
            user=request.user,
            order_id=str(pk),
            source_warehouse_id=str(serializer.validated_data["source_warehouse_id"]),
        )
        # Returns the generated invoice
        return Response(SalesInvoiceSerializer(invoice).data, status=status.HTTP_200_OK)


class SalesOrderApproveInputSerializer(serializers.Serializer):
    due_date = serializers.DateField(required=True)

    def validate_due_date(self, value):
        from django.utils import timezone

        if value < timezone.now().date():
            raise serializers.ValidationError("Hạn thanh toán không thể ở quá khứ.")
        return value


class SalesOrderApproveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "sales.update_order")
        serializer = SalesOrderApproveInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        due_date = serializer.validated_data["due_date"]
        order = sales_order_approve(user=request.user, order_id=str(pk), due_date=due_date)
        return Response(SalesOrderSerializer(order).data, status=status.HTTP_200_OK)


class SalesOrderApproveCreditBypassAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "finance.approve_credit_bypass")
        order = approve_credit_bypass(user=request.user, order_id=str(pk))
        return Response(SalesOrderSerializer(order).data, status=status.HTTP_200_OK)


class SalesOrderCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "sales.cancel_order")
        order = sales_order_cancel(user=request.user, order_id=str(pk))
        return Response(SalesOrderSerializer(order).data, status=status.HTTP_200_OK)
