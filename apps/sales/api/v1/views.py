from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.xlib.permissions import PermissionChecker
from apps.sales.selectors import sales_invoice_detail, sales_invoice_list, sales_order_detail, sales_order_list
from apps.sales.services import (
    approve_credit_bypass,
    sales_order_approve,
    sales_order_cancel,
    sales_order_create,
    sales_order_delete,
    sales_order_deliver_goods,
    sales_order_update,
)

from .serializers import (
    SalesInvoiceSerializer,
    SalesOrderDeliverInputSerializer,
    SalesOrderInputSerializer,
    SalesOrderSerializer,
)


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


class SalesOrderApproveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "sales.update_order")
        order = sales_order_approve(user=request.user, order_id=str(pk))
        return Response(SalesOrderSerializer(order).data, status=status.HTTP_200_OK)


class SalesOrderApproveCreditBypassAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "sales.approve_credit_bypass")
        order = approve_credit_bypass(user=request.user, order_id=str(pk))
        return Response(SalesOrderSerializer(order).data, status=status.HTTP_200_OK)


class SalesOrderCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "sales.cancel_order")
        order = sales_order_cancel(user=request.user, order_id=str(pk))
        return Response(SalesOrderSerializer(order).data, status=status.HTTP_200_OK)


class SalesInvoiceListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "sales.view_invoice")
        invoices = sales_invoice_list()

        status_filter = request.query_params.get("status")
        if status_filter:
            if "," in status_filter:
                status_list = [s.strip() for s in status_filter.split(",")]
                invoices = invoices.filter(status__in=status_list)
            else:
                invoices = invoices.filter(status=status_filter)

        page_param = request.query_params.get("page")
        limit_param = request.query_params.get("limit")

        if page_param or limit_param:
            from rest_framework.pagination import PageNumberPagination

            paginator = PageNumberPagination()
            paginator.page_size = int(limit_param) if limit_param else 10
            page = paginator.paginate_queryset(invoices, request, view=self)
            if page is not None:
                serializer = SalesInvoiceSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)

        serializer = SalesInvoiceSerializer(invoices, many=True)
        return Response(serializer.data)


class SalesInvoiceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "sales.view_invoice")
        invoice = sales_invoice_detail(invoice_id=str(pk))
        return Response(SalesInvoiceSerializer(invoice).data)
