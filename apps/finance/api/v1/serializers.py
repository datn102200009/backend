from decimal import Decimal

from rest_framework import serializers

from apps.finance.models import CashFlowTransaction, FixedAsset, FixedAssetDepreciationLog

# ARCHITECTURE NOTE:
# PurchaseInvoice/SalesInvoice được re-export từ purchasing/sales models.
# Xem chi tiết tại apps/finance/selectors.py docstring.
from apps.purchasing.models import PurchaseInvoice, PurchaseInvoiceLine
from apps.sales.models import SalesInvoice, SalesInvoiceLine


class CashFlowTransactionSerializer(serializers.ModelSerializer):
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True)
    fixed_asset_code = serializers.CharField(source="fixed_asset.asset_code", read_only=True)

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
            "fixed_asset",
            "fixed_asset_code",
            "status",
            "approved_by",
            "approved_by_username",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "name",
            "status",
            "approved_by",
            "approved_by_username",
            "approved_at",
            "fixed_asset_code",
            "created_at",
            "updated_at",
        ]


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
            "is_active",
            "status",
            "purchase_date",
            "disposal_date",
            "disposal_value",
            "vendor_name",
            "payment_method",
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

    def get_remaining_value(self, obj) -> str:
        # NOTE: salvage_value is removed from remaining_value calculation as per 2026-06 requirements
        value = obj.original_value - obj.accumulated_depreciation
        return str(value.quantize(Decimal("0.01")))


class FixedAssetPurchaseInputSerializer(serializers.Serializer):
    asset_name = serializers.CharField(max_length=255)
    original_value = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)
    depreciation_method = serializers.ChoiceField(
        choices=[("straight_line", "Đường thẳng"), ("unit_of_production", "Sản lượng")]
    )
    useful_life_months = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    designed_capacity = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=0.01, required=False, allow_null=True
    )
    vendor_name = serializers.CharField(max_length=255)
    payment_method = serializers.ChoiceField(
        choices=[("cash", "Cash"), ("bank_transfer", "Bank Transfer")], default="bank_transfer"
    )

    def validate(self, attrs):
        depreciation_method = attrs.get("depreciation_method")
        useful_life_months = attrs.get("useful_life_months")
        designed_capacity = attrs.get("designed_capacity")

        if depreciation_method == "straight_line":
            if useful_life_months is None:
                raise serializers.ValidationError(
                    {"useful_life_months": "Thời gian khấu hao là bắt buộc đối với phương pháp khấu hao đường thẳng."}
                )
            if designed_capacity is not None:
                raise serializers.ValidationError(
                    {
                        "designed_capacity": "Công suất thiết kế không được cung cấp đối với phương pháp khấu hao đường thẳng."
                    }
                )
        elif depreciation_method == "unit_of_production":
            if useful_life_months is not None:
                raise serializers.ValidationError(
                    {
                        "useful_life_months": "Thời gian khấu hao không được cung cấp đối với phương pháp khấu hao theo sản lượng."
                    }
                )
            if not designed_capacity or designed_capacity <= 0:
                raise serializers.ValidationError(
                    {
                        "designed_capacity": "Công suất thiết kế là bắt buộc và phải lớn hơn 0 đối với phương pháp khấu hao theo sản lượng."
                    }
                )
        return attrs


class FixedAssetRequestDisposeInputSerializer(serializers.Serializer):
    disposal_value = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0, default=Decimal("0.00"))
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class FixedAssetUpdateInputSerializer(serializers.Serializer):
    asset_name = serializers.CharField(max_length=255, required=False)
    useful_life_months = serializers.IntegerField(min_value=1, required=False)


class RunDepreciationInputSerializer(serializers.Serializer):
    period = serializers.CharField(max_length=7)  # Format: YYYY-MM


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
            "due_date",
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
            "due_date",
            "created_at",
            "updated_at",
        ]


class PayInvoiceInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)
    payment_method = serializers.ChoiceField(
        choices=[("cash", "Tiền mặt"), ("bank_transfer", "Chuyển khoản ngân hàng")],
        default="bank_transfer",
    )


class CollectInvoiceInputSerializer(serializers.Serializer):
    """Input cho AR collection (Sales Invoice)."""

    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)
    payment_method = serializers.ChoiceField(
        choices=[("cash", "Tiền mặt"), ("bank_transfer", "Chuyển khoản ngân hàng")],
        default="bank_transfer",
    )


class SalarySlipPaymentInputSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(
        choices=[("cash", "Cash"), ("bank_transfer", "Bank Transfer")],
        default="bank_transfer",
    )


class SalarySlipRejectInputSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10, required=True)


class SalarySlipBulkApprovePayInputSerializer(serializers.Serializer):
    salary_period = serializers.CharField(max_length=10, required=True)
    payment_method = serializers.ChoiceField(
        choices=[("cash", "Cash"), ("bank_transfer", "Bank Transfer")],
        default="bank_transfer",
    )
