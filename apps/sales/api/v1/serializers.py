from rest_framework import serializers

from apps.sales.models import SalesInvoice, SalesInvoiceLine, SalesOrder, SalesOrderLine


# --- ORDER SERIALIZERS ---
class SalesOrderLineSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)

    class Meta:
        model = SalesOrderLine
        fields = ["id", "item", "item_name", "item_code", "quantity", "unit_price", "line_total"]
        read_only_fields = ["id", "line_total"]


class SalesOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    lines = SalesOrderLineSerializer(many=True, read_only=True)
    invoices = serializers.SerializerMethodField()
    stock_entries = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrder
        fields = [
            "id",
            "customer",
            "customer_name",
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


class SalesOrderLineInputSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0)


class SalesOrderInputSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=SalesOrder.Status.choices, required=False)
    lines = serializers.ListField(child=SalesOrderLineInputSerializer(), allow_empty=False)


class SalesOrderDeliverInputSerializer(serializers.Serializer):
    source_warehouse_id = serializers.UUIDField()


# --- INVOICE SERIALIZERS ---
class SalesInvoiceLineSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)

    class Meta:
        model = SalesInvoiceLine
        fields = ["id", "item", "item_name", "item_code", "quantity", "unit_price", "vat_tax", "line_total"]
        read_only_fields = ["id", "line_total"]


class SalesInvoiceSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    lines = SalesInvoiceLineSerializer(many=True, read_only=True)
    stock_entry_name = serializers.CharField(source="stock_entry.name", read_only=True)

    class Meta:
        model = SalesInvoice
        fields = [
            "id",
            "order",
            "stock_entry",
            "stock_entry_name",
            "customer",
            "customer_name",
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
            "customer",
            "status",
            "total_amount",
            "paid_amount",
            "created_at",
            "updated_at",
        ]
