from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.purchasing.selectors import (
    purchase_invoice_detail,
    purchase_invoice_list,
    purchase_order_detail,
    purchase_order_list,
)
from apps.purchasing.services import (
    purchase_order_approve,
    purchase_order_create,
    purchase_order_delete,
    purchase_order_receive_goods,
    purchase_order_update,
)

from .serializers import (
    PurchaseInvoiceSerializer,
    PurchaseOrderInputSerializer,
    PurchaseOrderReceiveInputSerializer,
    PurchaseOrderSerializer,
)


class PurchaseOrderListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        orders = purchase_order_list()
        return Response(PurchaseOrderSerializer(orders, many=True).data)

    def post(self, request, *args, **kwargs):
        serializer = PurchaseOrderInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = purchase_order_create(
            user=request.user,
            vendor_id=serializer.validated_data["vendor_id"],
            lines=serializer.validated_data["lines"],
        )
        return Response(PurchaseOrderSerializer(order).data, status=status.HTTP_201_CREATED)


class PurchaseOrderDetailUpdateDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        order = purchase_order_detail(order_id=str(pk))
        return Response(PurchaseOrderSerializer(order).data)

    def put(self, request, pk, *args, **kwargs):
        serializer = PurchaseOrderInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = purchase_order_update(
            user=request.user,
            order_id=str(pk),
            vendor_id=serializer.validated_data["vendor_id"],
            status=serializer.validated_data.get("status", "draft"),
            lines=serializer.validated_data["lines"],
        )
        return Response(PurchaseOrderSerializer(order).data)

    def delete(self, request, pk, *args, **kwargs):
        purchase_order_delete(user=request.user, order_id=str(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PurchaseOrderReceiveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        serializer = PurchaseOrderReceiveInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invoice = purchase_order_receive_goods(
            user=request.user,
            order_id=str(pk),
            target_warehouse_id=str(serializer.validated_data["target_warehouse_id"]),
        )
        # Returns the generated invoice
        return Response(PurchaseInvoiceSerializer(invoice).data, status=status.HTTP_200_OK)


class PurchaseOrderApproveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        order = purchase_order_approve(user=request.user, order_id=str(pk))
        return Response(PurchaseOrderSerializer(order).data, status=status.HTTP_200_OK)


class PurchaseInvoiceListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        invoices = purchase_invoice_list()
        return Response(PurchaseInvoiceSerializer(invoices, many=True).data)


class PurchaseInvoiceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        invoice = purchase_invoice_detail(invoice_id=str(pk))
        return Response(PurchaseInvoiceSerializer(invoice).data)
