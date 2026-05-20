from rest_framework import serializers

from apps.purchasing.models import PurchaseInvoice, PurchaseInvoiceLine, PurchaseOrder, PurchaseOrderLine


# --- ORDER SERIALIZERS ---
class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)

    class Meta:
        model = PurchaseOrderLine
        fields = ["id", "item", "item_name", "item_code", "quantity", "unit_price", "line_total"]
        read_only_fields = ["id", "line_total"]


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
            "created_at",
            "updated_at",
            "lines",
            "invoices",
            "stock_entries",
        ]
        read_only_fields = ["id", "status", "total_amount", "advance_paid_amount", "created_at", "updated_at"]

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
    status = serializers.ChoiceField(choices=PurchaseOrder.Status.choices, required=False)
    lines = serializers.ListField(child=PurchaseOrderLineInputSerializer(), allow_empty=False)


class PurchaseOrderReceiveInputSerializer(serializers.Serializer):
    target_warehouse_id = serializers.UUIDField()


# --- INVOICE SERIALIZERS ---
class PurchaseInvoiceLineSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)

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
        ]
        read_only_fields = ["id", "line_total"]


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
            "created_at",
            "updated_at",
        ]
