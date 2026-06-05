from rest_framework import serializers

from apps.purchasing.models import PurchaseInvoice, PurchaseInvoiceLine, PurchaseOrder, PurchaseOrderLine


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
    lines = serializers.ListField(child=PurchaseOrderLineInputSerializer(), allow_empty=False)


class PurchaseOrderReceiveInputSerializer(serializers.Serializer):
    target_warehouse_id = serializers.UUIDField()


class PurchaseOrderCancelInputSerializer(serializers.Serializer):
    refund_deposit = serializers.BooleanField(required=False, default=True)
    keep_goods = serializers.BooleanField(required=False, default=False)


# --- INVOICE SERIALIZERS ---
class PurchaseInvoiceLineSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    qc_status = serializers.SerializerMethodField()
    latest_cert = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseInvoiceLine
        fields = [
            "id",
            "item",
            "item_name",
            "item_code",
            "quantity",
            "unit_price",
            "import_tax",
            "vat_tax",
            "line_total",
            "qty_fulfillment_rate",
            "qc_status",
            "latest_cert",
        ]
        read_only_fields = ["id", "line_total"]

    def get_qc_status(self, obj):
        from apps.finance.models import TechnicalCertification

        stock_entry = obj.invoice.stock_entry
        if not stock_entry:
            return "PENDING"
        cert = (
            TechnicalCertification.objects.filter(item=obj.item, stock_entry=stock_entry)
            .order_by("-issue_date", "-id")
            .first()
        )
        if cert:
            return cert.result
        return "PENDING"

    def get_latest_cert(self, obj):
        from apps.finance.models import TechnicalCertification

        stock_entry = obj.invoice.stock_entry
        if not stock_entry:
            return None
        cert = (
            TechnicalCertification.objects.filter(item=obj.item, stock_entry=stock_entry)
            .order_by("-issue_date", "-id")
            .first()
        )
        if cert:
            return {
                "id": str(cert.id),
                "cert_id": cert.cert_id,
                "result": cert.result,
                "remarks": cert.remarks,
                "issue_date": cert.issue_date.isoformat() if cert.issue_date else None,
            }
        return None


class PurchaseInvoiceSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.supplier_name", read_only=True)
    lines = PurchaseInvoiceLineSerializer(many=True, read_only=True)
    stock_entry_name = serializers.CharField(source="stock_entry.name", read_only=True)

    class Meta:
        model = PurchaseInvoice
        fields = [
            "id",
            "order",
            "stock_entry",
            "stock_entry_name",
            "vendor",
            "vendor_name",
            "status",
            "total_amount",
            "paid_amount",
            "block_reason",
            "due_date",
            "qty_fulfillment_rate",
            "created_at",
            "updated_at",
            "lines",
        ]
        read_only_fields = [
            "id",
            "order",
            "stock_entry",
            "vendor",
            "status",
            "total_amount",
            "paid_amount",
            "block_reason",
            "due_date",
            "qty_fulfillment_rate",
            "created_at",
            "updated_at",
        ]


class PayInvoiceInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)
    payment_method = serializers.ChoiceField(
        choices=[("cash", "Tiền mặt"), ("bank_transfer", "Chuyển khoản ngân hàng")], default="bank_transfer"
    )


class LandedCostAllocationInputSerializer(serializers.Serializer):
    shipment_id = serializers.UUIDField()
    total_logistic_fees = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)


class ShipmentSerializer(serializers.ModelSerializer):
    stock_entries = serializers.SerializerMethodField()
    stock_entries_details = serializers.SerializerMethodField()

    class Meta:
        from apps.purchasing.models import Shipment

        model = Shipment
        fields = [
            "id",
            "shipment_num",
            "name",
            "total_logistic_fees",
            "status",
            "remarks",
            "stock_entries",
            "stock_entries_details",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

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


class TechnicalCertificationSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    stock_entry_name = serializers.CharField(source="stock_entry.name", read_only=True)

    class Meta:
        from apps.finance.models import TechnicalCertification

        model = TechnicalCertification
        fields = [
            "id",
            "cert_id",
            "item",
            "item_name",
            "item_code",
            "stock_entry",
            "stock_entry_name",
            "cert_type",
            "assessment_fee",
            "expiry_date",
            "issue_date",
            "result",
            "remarks",
        ]
        read_only_fields = ["id", "issue_date"]


class TechnicalCertificationCreateInputSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    stock_entry_id = serializers.UUIDField()
    cert_type = serializers.CharField(max_length=100)
    assessment_fee = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    result = serializers.ChoiceField(choices=[("PASSED", "Đạt"), ("FAILED", "Không đạt")], default="PASSED")
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ShipmentInputSerializer(serializers.Serializer):
    shipment_num = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=255)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    stock_entry_ids = serializers.ListField(child=serializers.UUIDField(), required=False)


class APAgingSerializer(serializers.Serializer):
    vendor_id = serializers.UUIDField()
    vendor_code = serializers.CharField()
    vendor_name = serializers.CharField()
    total_unpaid = serializers.DecimalField(max_digits=15, decimal_places=2)
    not_due = serializers.DecimalField(max_digits=15, decimal_places=2)
    overdue_1_30 = serializers.DecimalField(max_digits=15, decimal_places=2)
    overdue_above_30 = serializers.DecimalField(max_digits=15, decimal_places=2)
