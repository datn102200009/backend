from rest_framework import serializers

from apps.finance.models import CashFlowTransaction


class CashFlowTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashFlowTransaction
        fields = [
            "id",
            "name",
            "payment_type",
            "category",
            "amount",
            "payment_date",
            "remarks",
            "purchase_order",
            "sales_order",
            "purchase_invoice",
            "sales_invoice",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "name", "created_at", "updated_at"]


class CashFlowInputSerializer(serializers.Serializer):
    payment_type = serializers.ChoiceField(choices=[("receive", "Receive Money"), ("pay", "Pay Money")])
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)
    payment_date = serializers.DateField()
    category = serializers.CharField(required=False, allow_blank=True, max_length=100)

    purchase_order_id = serializers.UUIDField(required=False, allow_null=True)
    sales_order_id = serializers.UUIDField(required=False, allow_null=True)
    purchase_invoice_id = serializers.UUIDField(required=False, allow_null=True)
    sales_invoice_id = serializers.UUIDField(required=False, allow_null=True)

    remarks = serializers.CharField(required=False, allow_blank=True)
