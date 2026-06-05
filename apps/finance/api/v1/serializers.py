from decimal import Decimal

from rest_framework import serializers

from apps.finance.models import CashFlowTransaction, FixedAsset, FixedAssetDepreciationLog


class CashFlowTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashFlowTransaction
        fields = [
            "id",
            "name",
            "payment_type",
            "category",
            "payment_method",
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
    payment_method = serializers.ChoiceField(
        choices=[
            ("cash", "Cash"),
            ("bank_transfer", "Bank Transfer"),
            ("credit_card", "Credit Card"),
            ("other", "Other"),
        ],
        default="bank_transfer",
        required=False,
    )

    purchase_order_id = serializers.UUIDField(required=False, allow_null=True)
    sales_order_id = serializers.UUIDField(required=False, allow_null=True)
    purchase_invoice_id = serializers.UUIDField(required=False, allow_null=True)
    sales_invoice_id = serializers.UUIDField(required=False, allow_null=True)

    remarks = serializers.CharField(required=False, allow_blank=True)


class FixedAssetDepreciationLogSerializer(serializers.ModelSerializer):
    asset_code = serializers.CharField(source="asset.asset_code", read_only=True)
    asset_name = serializers.CharField(source="asset.asset_name", read_only=True)

    class Meta:
        model = FixedAssetDepreciationLog
        fields = [
            "id",
            "asset",
            "asset_code",
            "asset_name",
            "period",
            "depreciation_amount",
            "remarks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class FixedAssetSerializer(serializers.ModelSerializer):
    remaining_value = serializers.SerializerMethodField()

    class Meta:
        model = FixedAsset
        fields = [
            "id",
            "asset_code",
            "asset_name",
            "original_value",
            "salvage_value",
            "depreciation_method",
            "useful_life_months",
            "remaining_life_months",
            "designed_capacity",
            "accumulated_depreciation",
            "remaining_value",
            "department",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "remaining_life_months",
            "accumulated_depreciation",
            "remaining_value",
            "created_at",
            "updated_at",
        ]

    def get_remaining_value(self, obj) -> float:
        return float(obj.original_value - obj.salvage_value - obj.accumulated_depreciation)


class FixedAssetCreateInputSerializer(serializers.Serializer):
    asset_code = serializers.CharField(max_length=100)
    asset_name = serializers.CharField(max_length=255)
    original_value = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)
    salvage_value = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=0, required=False, default=Decimal("0.00")
    )
    depreciation_method = serializers.ChoiceField(
        choices=[("straight_line", "Đường thẳng"), ("unit_of_production", "Sản lượng")]
    )
    useful_life_months = serializers.IntegerField(min_value=1)
    designed_capacity = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=0.01, required=False, allow_null=True
    )
    department = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)


class FixedAssetUpdateInputSerializer(serializers.Serializer):
    asset_name = serializers.CharField(max_length=255, required=False)
    original_value = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01, required=False)
    salvage_value = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0, required=False)
    depreciation_method = serializers.ChoiceField(
        choices=[("straight_line", "Đường thẳng"), ("unit_of_production", "Sản lượng")], required=False
    )
    useful_life_months = serializers.IntegerField(min_value=1, required=False)
    designed_capacity = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=0.01, required=False, allow_null=True
    )
    department = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)


class RunDepreciationInputSerializer(serializers.Serializer):
    period = serializers.CharField(max_length=7)  # Format: YYYY-MM
