from rest_framework import serializers

from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine


# --- ORDER SERIALIZERS ---
class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)

    class Meta:
        model = PurchaseOrderLine
        fields = [
            "id",
            "item",
            "item_name",
            "item_code",
            "quantity",
            "unit_price",
            "line_total",
            "receipt_fulfillment_rate",
        ]
        read_only_fields = ["id", "line_total", "receipt_fulfillment_rate"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.supplier_name", read_only=True)
    lines = PurchaseOrderLineSerializer(many=True, read_only=True)
    invoices = serializers.SerializerMethodField()
    stock_entries = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "vendor",
            "vendor_name",
            "status",
            "total_amount",
            "advance_paid_amount",
            "expected_delivery_date",
            "due_date",
            "receipt_fulfillment_rate",
            "payment_fulfillment_rate",
            "created_at",
            "updated_at",
            "lines",
            "invoices",
            "stock_entries",
        ]
        read_only_fields = [
            "id",
            "status",
            "total_amount",
            "advance_paid_amount",
            "receipt_fulfillment_rate",
            "payment_fulfillment_rate",
            "created_at",
            "updated_at",
        ]

    def get_invoices(self, obj):
        return [
            {
                "id": str(i.id),
                "status": i.status,
                "total_amount": float(i.total_amount),
                "paid_amount": float(i.paid_amount),
            }
            for i in obj.invoices.all()
        ]

    def get_stock_entries(self, obj):
        return [
            {"id": str(s.id), "name": s.name, "status": s.status, "purpose": s.purpose} for s in obj.stock_entries.all()
        ]


class PurchaseOrderLineInputSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0)


class PurchaseOrderInputSerializer(serializers.Serializer):
    vendor_id = serializers.UUIDField()
    status = serializers.CharField(read_only=True)
    advance_paid_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, default=0, min_value=0
    )
    expected_delivery_date = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=True)
    lines = serializers.ListField(child=PurchaseOrderLineInputSerializer(), allow_empty=False)

    def validate_due_date(self, value):
        from django.utils import timezone

        if value < timezone.now().date():
            raise serializers.ValidationError("Hạn thanh toán không thể ở quá khứ.")
        return value


class PurchaseOrderReceiveInputSerializer(serializers.Serializer):
    target_warehouse_id = serializers.UUIDField()


class PurchaseOrderCancelInputSerializer(serializers.Serializer):
    refund_deposit = serializers.BooleanField(required=False, default=True)
    keep_goods = serializers.BooleanField(required=False, default=False)


class LandedCostAllocationInputSerializer(serializers.Serializer):
    shipment_id = serializers.UUIDField()
    total_logistic_fees = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)


class ShipmentSerializer(serializers.ModelSerializer):
    stock_entries = serializers.SerializerMethodField()
    stock_entries_details = serializers.SerializerMethodField()
    purchase_order_lines = serializers.SerializerMethodField()
    cash_flows = serializers.SerializerMethodField()

    class Meta:
        from apps.purchasing.models import Shipment

        model = Shipment
        fields = [
            "id",
            "shipment_num",
            "name",
            "purchase_order",
            "purchase_order_lines",
            "total_logistic_fees",
            "status",
            "remarks",
            "stock_entries",
            "stock_entries_details",
            "cash_flows",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def get_cash_flows(self, obj):
        return [
            {
                "id": str(cf.id),
                "name": cf.name,
                "status": cf.status,
                "amount": float(cf.amount),
                "remarks": cf.remarks,
            }
            for cf in obj.cash_flows.all()
        ]

    def get_stock_entries(self, obj):
        return [
            {"id": str(s.id), "name": s.name, "status": s.status, "purpose": s.purpose} for s in obj.stock_entries.all()
        ]

    def get_stock_entries_details(self, obj):
        details_data = []
        from apps.inventory.api.v1.serializers import StockEntryDetailSerializer

        for se in obj.stock_entries.all():
            for detail in se.details.all():
                serialized = StockEntryDetailSerializer(detail).data
                serialized["stock_entry_id"] = str(se.id)
                serialized["stock_entry_name"] = se.name
                serialized["stock_entry_status"] = se.status
                details_data.append(serialized)
        return details_data

    def get_purchase_order_lines(self, obj):
        po = obj.purchase_order
        if not po:
            return []

        # Tính số lượng đã nhận trước đó (loại trừ chính shipment hiện tại nếu là draft/inspecting)
        from decimal import Decimal

        from django.db.models import Sum

        from apps.inventory.models import StockEntryDetail

        # Tổng đã nhận từ TẤT CẢ các shipment của PO này (kể cả shipment hiện tại nếu đã posted)
        received_qs = (
            StockEntryDetail.objects.filter(parent__purchase_order=po, parent__status="posted")
            .values("item_id")
            .annotate(total_qty=Sum("quantity"))
        )
        received_map = {str(r["item_id"]): r["total_qty"] for r in received_qs}

        # Tính số lượng đã nhận trong shipment hiện tại (chỉ áp dụng khi shipment ở trạng thái inspecting/draft)
        current_received_map = {}
        if obj.status in ["draft", "inspecting"]:
            for se in obj.stock_entries.all():
                for d in se.details.all():
                    current_received_map[str(d.item_id)] = (
                        current_received_map.get(str(d.item_id), Decimal("0.00")) + d.quantity
                    )

        result = []
        for line in po.lines.all():
            item_id_str = str(line.item.id)
            total_received = Decimal(str(received_map.get(item_id_str, "0")))
            # Trừ phần đã nhận trong chính shipment hiện tại (vì user đang sửa trên UI)
            already_in_other_shipments = total_received - Decimal(str(current_received_map.get(item_id_str, "0")))
            remaining = max(Decimal("0.00"), line.quantity - already_in_other_shipments)

            result.append(
                {
                    "id": str(line.id),
                    "item_id": item_id_str,
                    "item_code": line.item.item_code,
                    "item_name": line.item.item_name,
                    "quantity": str(line.quantity),  # số lượng đặt gốc (giữ cho audit)
                    "remaining_quantity": str(remaining),  # SL CÒN LẠI - dùng để hiển thị chính
                    "received_quantity": str(already_in_other_shipments),  # ĐÃ NHẬN TRƯỚC - hiển thị phụ
                    "unit": line.item.stock_uom.name if line.item.stock_uom else "",
                }
            )
        return result


class ShipmentDetailCompleteSerializer(serializers.Serializer):
    po_line_id = serializers.UUIDField()
    item_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=2)
    target_warehouse_id = serializers.UUIDField(required=False, allow_null=True)


class ShipmentCompleteInputSerializer(serializers.Serializer):
    total_logistic_fees = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0)
    details = ShipmentDetailCompleteSerializer(many=True)


class ShipmentInputSerializer(serializers.Serializer):
    shipment_num = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=255)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    purchase_order_id = serializers.UUIDField(required=False, allow_null=True)
    stock_entry_ids = serializers.ListField(child=serializers.UUIDField(), required=False)


class APAgingSerializer(serializers.Serializer):
    vendor_id = serializers.UUIDField()
    vendor_code = serializers.CharField()
    vendor_name = serializers.CharField()
    total_unpaid = serializers.DecimalField(max_digits=15, decimal_places=2)
    not_due = serializers.DecimalField(max_digits=15, decimal_places=2)
    overdue_1_30 = serializers.DecimalField(max_digits=15, decimal_places=2)
    overdue_above_30 = serializers.DecimalField(max_digits=15, decimal_places=2)
