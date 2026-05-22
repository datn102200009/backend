from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.sales.selectors import sales_invoice_detail, sales_invoice_list, sales_order_detail, sales_order_list
from apps.sales.services import (
    sales_order_approve,
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
        orders = sales_order_list()
        return Response(SalesOrderSerializer(orders, many=True).data)

    def post(self, request, *args, **kwargs):
        serializer = SalesOrderInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = sales_order_create(
            user=request.user,
            customer_id=str(serializer.validated_data["customer_id"]),
            lines=serializer.validated_data["lines"],
        )
        return Response(SalesOrderSerializer(order).data, status=status.HTTP_201_CREATED)


class SalesOrderDetailUpdateDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        order = sales_order_detail(order_id=str(pk))
        return Response(SalesOrderSerializer(order).data)

    def put(self, request, pk, *args, **kwargs):
        serializer = SalesOrderInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = sales_order_update(
            user=request.user,
            order_id=str(pk),
            customer_id=str(serializer.validated_data["customer_id"]),
            status=serializer.validated_data.get("status", "draft"),
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
        order = sales_order_approve(user=request.user, order_id=str(pk))
        return Response(SalesOrderSerializer(order).data, status=status.HTTP_200_OK)


class SalesInvoiceListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        invoices = sales_invoice_list()
        return Response(SalesInvoiceSerializer(invoices, many=True).data)


class SalesInvoiceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        invoice = sales_invoice_detail(invoice_id=str(pk))
        return Response(SalesInvoiceSerializer(invoice).data)
