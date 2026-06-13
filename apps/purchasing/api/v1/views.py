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
    purchase_order_approve,
    purchase_order_cancel,
    purchase_order_create,
    purchase_order_delete,
    purchase_order_receive_goods,
    purchase_order_update,
    record_shipment_logistic_fees,
    shipment_create,
    shipment_update,
)

from .serializers import (
    APAgingSerializer,
    LandedCostAllocationInputSerializer,
    PurchaseInvoiceSerializer,
    PurchaseOrderCancelInputSerializer,
    PurchaseOrderInputSerializer,
    PurchaseOrderReceiveInputSerializer,
    PurchaseOrderSerializer,
    ShipmentCompleteInputSerializer,
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
        PermissionChecker.check_permission(request.user, "purchasing.update_order")
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

        status_filter = request.query_params.get("status")
        if status_filter:
            if "," in status_filter:
                status_list = [s.strip() for s in status_filter.split(",")]
                invoices = invoices.filter(status__in=status_list)
            else:
                invoices = invoices.filter(status=status_filter)

        from rest_framework.pagination import PageNumberPagination

        paginator = PageNumberPagination()
        limit_param = request.query_params.get("limit")
        paginator.page_size = int(limit_param) if limit_param else 10
        page = paginator.paginate_queryset(invoices, request, view=self)
        serializer = PurchaseInvoiceSerializer(page, many=True)
        return Response(
            {
                "count": paginator.page.paginator.count,
                "total_pages": paginator.page.paginator.num_pages,
                "current_page": paginator.page.number,
                "results": serializer.data,
            }
        )


class PurchaseInvoiceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.view_invoice")
        invoice = purchase_invoice_detail(invoice_id=str(pk))
        return Response(PurchaseInvoiceSerializer(invoice).data)


class ShipmentListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.allocate_landed_cost")
        from apps.purchasing.models import Shipment

        shipments = (
            Shipment.objects.select_related("purchase_order")
            .prefetch_related(
                "purchase_order__lines__item",
                "purchase_order__lines__item__stock_uom",
                "stock_entries__details__item",
                "stock_entries__details__target_warehouse",
            )
            .order_by("-created_at", "id")
        )
        return Response(ShipmentSerializer(shipments, many=True).data)

    def post(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.allocate_landed_cost")
        serializer = ShipmentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        purchase_order_id = serializer.validated_data.get("purchase_order_id")
        if purchase_order_id:
            from apps.purchasing.services import shipment_create_from_po

            shipment = shipment_create_from_po(
                user=request.user,
                shipment_num=serializer.validated_data["shipment_num"],
                name=serializer.validated_data["name"],
                purchase_order_id=str(purchase_order_id),
                remarks=serializer.validated_data.get("remarks"),
            )
        else:
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
            Shipment.objects.select_related("purchase_order")
            .prefetch_related(
                "purchase_order__lines__item",
                "purchase_order__lines__item__stock_uom",
                "stock_entries__details__item",
                "stock_entries__details__target_warehouse",
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


class ShipmentCompleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "purchasing.allocate_landed_cost")
        from apps.purchasing.services import shipment_complete

        serializer = ShipmentCompleteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shipment = shipment_complete(
            user=request.user,
            shipment_id=str(pk),
            details=serializer.validated_data["details"],
            total_logistic_fees=serializer.validated_data["total_logistic_fees"],
        )
        return Response(ShipmentSerializer(shipment).data, status=status.HTTP_200_OK)


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
