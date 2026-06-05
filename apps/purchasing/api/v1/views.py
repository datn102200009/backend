from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.xlib.permissions import PermissionChecker
from apps.purchasing.selectors import (
    get_supplier_ap_aging,
    purchase_invoice_detail,
    purchase_invoice_list,
    purchase_order_detail,
    purchase_order_list,
)
from apps.purchasing.services import (
    pay_purchase_invoice,
    purchase_order_approve,
    purchase_order_cancel,
    purchase_order_create,
    purchase_order_delete,
    purchase_order_receive_goods,
    purchase_order_update,
    record_shipment_logistic_fees,
    shipment_create,
    shipment_update,
    technical_certification_create,
    verify_4_way_matching,
)

from .serializers import (
    APAgingSerializer,
    LandedCostAllocationInputSerializer,
    PayInvoiceInputSerializer,
    PurchaseInvoiceSerializer,
    PurchaseOrderCancelInputSerializer,
    PurchaseOrderInputSerializer,
    PurchaseOrderReceiveInputSerializer,
    PurchaseOrderSerializer,
    ShipmentInputSerializer,
    ShipmentSerializer,
)


class PurchaseOrderListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.view_order")
        orders = purchase_order_list()
        return Response(PurchaseOrderSerializer(orders, many=True).data)

    def post(self, request, *args, **kwargs):
        serializer = PurchaseOrderInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = purchase_order_create(
            user=request.user,
            vendor_id=serializer.validated_data["vendor_id"],
            advance_paid_amount=serializer.validated_data.get("advance_paid_amount", 0),
            expected_delivery_date=serializer.validated_data.get("expected_delivery_date"),
            lines=serializer.validated_data["lines"],
        )
        return Response(PurchaseOrderSerializer(order).data, status=status.HTTP_201_CREATED)


class PurchaseOrderDetailUpdateDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.view_order")
        order = purchase_order_detail(order_id=str(pk))
        return Response(PurchaseOrderSerializer(order).data)

    def put(self, request, pk, *args, **kwargs):
        serializer = PurchaseOrderInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = purchase_order_update(
            user=request.user,
            order_id=str(pk),
            vendor_id=serializer.validated_data["vendor_id"],
            advance_paid_amount=serializer.validated_data.get("advance_paid_amount", 0),
            expected_delivery_date=serializer.validated_data.get("expected_delivery_date"),
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


class PurchaseOrderCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.cancel_order")
        serializer = PurchaseOrderCancelInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = purchase_order_cancel(
            user=request.user,
            order_id=str(pk),
            refund_deposit=serializer.validated_data.get("refund_deposit", True),
            keep_goods=serializer.validated_data.get("keep_goods", False),
        )
        return Response(PurchaseOrderSerializer(order).data, status=status.HTTP_200_OK)


class PurchaseInvoiceListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.view_invoice")
        invoices = purchase_invoice_list()
        return Response(PurchaseInvoiceSerializer(invoices, many=True).data)


class PurchaseInvoiceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.view_invoice")
        invoice = purchase_invoice_detail(invoice_id=str(pk))
        return Response(PurchaseInvoiceSerializer(invoice).data)


class PurchaseInvoiceVerifyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.verify_matching")
        verify_4_way_matching(invoice_id=str(pk))
        invoice = purchase_invoice_detail(invoice_id=str(pk))
        return Response(PurchaseInvoiceSerializer(invoice).data, status=status.HTTP_200_OK)


class PurchaseInvoicePayAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.pay_invoice")
        serializer = PayInvoiceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pay_purchase_invoice(
            user=request.user,
            invoice_id=str(pk),
            amount=serializer.validated_data["amount"],
            payment_method=serializer.validated_data["payment_method"],
        )

        invoice = purchase_invoice_detail(invoice_id=str(pk))
        return Response(PurchaseInvoiceSerializer(invoice).data, status=status.HTTP_200_OK)


class ShipmentListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.allocate_landed_cost")
        from apps.purchasing.models import Shipment

        shipments = Shipment.objects.prefetch_related(
            "stock_entries__details__item", "stock_entries__details__target_warehouse"
        ).order_by("-created_at", "id")
        return Response(ShipmentSerializer(shipments, many=True).data)

    def post(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.allocate_landed_cost")
        serializer = ShipmentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shipment = shipment_create(
            user=request.user,
            shipment_num=serializer.validated_data["shipment_num"],
            name=serializer.validated_data["name"],
            remarks=serializer.validated_data.get("remarks"),
            stock_entry_ids=serializer.validated_data.get("stock_entry_ids"),
        )
        return Response(ShipmentSerializer(shipment).data, status=status.HTTP_201_CREATED)


class ShipmentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.allocate_landed_cost")
        from apps.purchasing.models import Shipment

        shipment = (
            Shipment.objects.prefetch_related(
                "stock_entries__details__item", "stock_entries__details__target_warehouse"
            )
            .filter(id=pk)
            .first()
        )
        if not shipment:
            return Response({"detail": "Lô hàng không tồn tại"}, status=status.HTTP_404_NOT_FOUND)
        return Response(ShipmentSerializer(shipment).data)

    def put(self, request, pk, *args, **kwargs):
        shipment = shipment_update(
            user=request.user,
            shipment_id=str(pk),
            status=request.data.get("status"),
            remarks=request.data.get("remarks"),
        )
        return Response(ShipmentSerializer(shipment).data)


class TechnicalCertificationListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.manage_qc")
        from rest_framework.pagination import PageNumberPagination

        from apps.finance.models import TechnicalCertification

        from .serializers import TechnicalCertificationSerializer

        queryset = TechnicalCertification.objects.select_related("item", "stock_entry").order_by("-issue_date", "-id")

        item_id = request.query_params.get("item_id")
        if item_id:
            queryset = queryset.filter(item_id=item_id)

        stock_entry_id = request.query_params.get("stock_entry_id")
        if stock_entry_id:
            queryset = queryset.filter(stock_entry_id=stock_entry_id)

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is not None:
            serializer = TechnicalCertificationSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = TechnicalCertificationSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        from .serializers import TechnicalCertificationCreateInputSerializer, TechnicalCertificationSerializer

        serializer = TechnicalCertificationCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cert = technical_certification_create(
            user=request.user,
            item_id=str(serializer.validated_data["item_id"]),
            stock_entry_id=str(serializer.validated_data["stock_entry_id"]),
            cert_type=serializer.validated_data["cert_type"],
            assessment_fee=serializer.validated_data.get("assessment_fee"),
            expiry_date=serializer.validated_data.get("expiry_date"),
            result=serializer.validated_data["result"],
            remarks=serializer.validated_data.get("remarks"),
        )
        return Response(TechnicalCertificationSerializer(cert).data, status=status.HTTP_201_CREATED)


class LandedCostAllocateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.allocate_landed_cost")
        serializer = LandedCostAllocationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shipment = record_shipment_logistic_fees(
            user=request.user,
            shipment_id=str(serializer.validated_data["shipment_id"]),
            total_logistic_fees=serializer.validated_data["total_logistic_fees"],
        )
        return Response(ShipmentSerializer(shipment).data, status=status.HTTP_200_OK)


class APAgingReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.view_ap_aging")
        supplier_id = request.query_params.get("supplier_id")
        report = get_supplier_ap_aging(supplier_id=supplier_id)
        return Response(APAgingSerializer(report, many=True).data, status=status.HTTP_200_OK)
