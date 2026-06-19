"""
Serializers for inventory API v1.

Handles validation and transformation of data.
"""

from rest_framework import serializers

from apps.inventory.models import StockEntry, StockEntryDetail, StockLedger
from apps.master_data.models import BOM, BOMItem, Item, Warehouse

# ======================== Stock Entry Serializers ========================


class StockEntryDetailSerializer(serializers.ModelSerializer):
    """Serializer cho chi tiết phiếu stock entry."""

    item_id = serializers.UUIDField(read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    uom_name = serializers.CharField(source="item.stock_uom.name", read_only=True)
    source_warehouse_id = serializers.UUIDField(read_only=True, allow_null=True)
    source_warehouse_name = serializers.CharField(source="source_warehouse.name", read_only=True)
    target_warehouse_id = serializers.UUIDField(read_only=True, allow_null=True)
    target_warehouse_name = serializers.CharField(source="target_warehouse.name", read_only=True)

    class Meta:
        model = StockEntryDetail
        fields = [
            "id",
            "item_id",
            "item_code",
            "item_name",
            "uom_name",
            "quantity",
            "source_warehouse_id",
            "source_warehouse_name",
            "target_warehouse_id",
            "target_warehouse_name",
        ]
        read_only_fields = [
            "id",
            "item_id",
            "item_code",
            "item_name",
            "uom_name",
            "source_warehouse_id",
            "source_warehouse_name",
            "target_warehouse_id",
            "target_warehouse_name",
        ]


class StockEntryDetailCreateSerializer(serializers.Serializer):
    """Serializer để tạo chi tiết stock entry (input)."""

    item_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=2)
    source_warehouse_id = serializers.UUIDField(required=False, allow_null=True)
    target_warehouse_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Số lượng phải lớn hơn 0")
        return value


class StockEntrySerializer(serializers.ModelSerializer):
    """Serializer cho phiếu stock entry (read)."""

    details = StockEntryDetailSerializer(many=True, read_only=True)
    created_at_formatted = serializers.DateTimeField(source="created_at", format="%Y-%m-%d %H:%M:%S", read_only=True)
    posting_date_formatted = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    posted_at_formatted = serializers.DateTimeField(source="posted_at", format="%Y-%m-%d %H:%M:%S", read_only=True)
    purchase_order_id = serializers.UUIDField(read_only=True, allow_null=True)
    sales_order_id = serializers.UUIDField(read_only=True, allow_null=True)
    vendor_name = serializers.CharField(source="purchase_order.vendor.supplier_name", read_only=True, allow_null=True)
    shipment_id = serializers.UUIDField(source="shipment.id", read_only=True, allow_null=True)
    shipment_num = serializers.CharField(source="shipment.shipment_num", read_only=True, allow_null=True)
    shipment_status = serializers.CharField(source="shipment.status", read_only=True, allow_null=True)

    class Meta:
        model = StockEntry
        fields = [
            "id",
            "name",
            "purpose",
            "posting_date",
            "posting_date_formatted",
            "posted_at",
            "posted_at_formatted",
            "remarks",
            "status",
            "purchase_order_id",
            "sales_order_id",
            "vendor_name",
            "shipment_id",
            "shipment_num",
            "shipment_status",
            "details",
            "created_at",
            "created_at_formatted",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "created_at_formatted",
            "updated_at",
            "posting_date_formatted",
            "posted_at_formatted",
        ]


class StockInCreateSerializer(serializers.Serializer):
    """Serializer để tạo phiếu nhập kho."""

    name = serializers.CharField(max_length=255)
    remarks = serializers.CharField(required=False, allow_blank=True)
    details = StockEntryDetailCreateSerializer(many=True)

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Tên phiếu không được để trống")
        return value

    def validate_details(self, value):
        if not value:
            raise serializers.ValidationError("Phiếu phải có ít nhất một chi tiết")
        return value


class StockIssueCreateSerializer(serializers.Serializer):
    """Serializer để tạo phiếu xuất kho."""

    name = serializers.CharField(max_length=255)
    source_warehouse_id = serializers.UUIDField()
    remarks = serializers.CharField(required=False, allow_blank=True)
    details = StockEntryDetailCreateSerializer(many=True)

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Tên phiếu không được để trống")
        return value

    def validate_details(self, value):
        if not value:
            raise serializers.ValidationError("Phiếu phải có ít nhất một chi tiết")
        return value


class StockTransferCreateSerializer(serializers.Serializer):
    """Serializer để tạo phiếu chuyển kho nội bộ."""

    name = serializers.CharField(max_length=255)
    source_warehouse_id = serializers.UUIDField()
    target_warehouse_id = serializers.UUIDField()
    remarks = serializers.CharField(required=False, allow_blank=True)
    details = StockEntryDetailCreateSerializer(many=True)

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Tên phiếu không được để trống")
        return value

    def validate_details(self, value):
        if not value:
            raise serializers.ValidationError("Phiếu phải có ít nhất một chi tiết")
        return value


# ======================== Stock Ledger Serializers ========================


class StockLedgerSerializer(serializers.ModelSerializer):
    """Serializer cho sổ cái kho."""

    item_id = serializers.UUIDField(read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    warehouse_id = serializers.UUIDField(read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    posting_date_formatted = serializers.DateTimeField(
        source="posting_date", format="%Y-%m-%d %H:%M:%S", read_only=True
    )

    class Meta:
        model = StockLedger
        fields = [
            "id",
            "item_id",
            "item_code",
            "item_name",
            "warehouse_id",
            "warehouse_name",
            "posting_date",
            "posting_date_formatted",
            "actual_quantity",
            "voucher_number",
            "voucher_type",
        ]
        read_only_fields = [
            "id",
            "item_id",
            "item_code",
            "item_name",
            "warehouse_id",
            "warehouse_name",
            "posting_date_formatted",
        ]


# ======================== Item Serializers ========================


class ItemSerializer(serializers.ModelSerializer):
    """Serializer cho sản phẩm."""

    item_group_name = serializers.CharField(source="item_group.name", read_only=True)
    stock_uom_name = serializers.CharField(source="stock_uom.name", read_only=True)

    class Meta:
        model = Item
        fields = [
            "id",
            "item_code",
            "item_name",
            "item_group",
            "item_group_name",
            "stock_uom",
            "stock_uom_name",
            "hs_code",
            "recycling_coef_a",
            "vat_group",
            "is_import",
            "status",
            "description",
        ]
        read_only_fields = [
            "id",
            "item_group_name",
            "stock_uom_name",
        ]


class ItemCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer để tạo hoặc cập nhật sản phẩm."""

    class Meta:
        model = Item
        fields = [
            "item_code",
            "item_name",
            "item_group",
            "stock_uom",
            "hs_code",
            "recycling_coef_a",
            "vat_group",
            "is_import",
            "status",
            "description",
        ]

    def validate_item_code(self, value):
        if not value.strip():
            raise serializers.ValidationError("Mã sản phẩm không được để trống")
        return value

    def validate_item_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Tên sản phẩm không được để trống")
        return value


# ======================== BOM Serializers ========================


class BOMItemSerializer(serializers.ModelSerializer):
    """Serializer cho chi tiết BOM."""

    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)

    class Meta:
        model = BOMItem
        fields = [
            "id",
            "item",
            "item_code",
            "item_name",
            "quantity",
        ]
        read_only_fields = [
            "id",
            "item_code",
            "item_name",
        ]


class BOMSerializer(serializers.ModelSerializer):
    """Serializer cho BOM."""

    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    items = BOMItemSerializer(many=True, read_only=True)

    class Meta:
        model = BOM
        fields = [
            "id",
            "name",
            "item",
            "item_code",
            "item_name",
            "quantity",
            "is_active",
            "description",
            "items",
        ]
        read_only_fields = [
            "id",
            "item_code",
            "item_name",
        ]


# ======================== Stock Entry Update Serializers ========================


class StockEntryUpdateDetailSerializer(serializers.Serializer):
    detail_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    source_warehouse_id = serializers.UUIDField(required=False, allow_null=True)
    target_warehouse_id = serializers.UUIDField(required=False, allow_null=True)


class StockEntryUpdateSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    details = serializers.ListField(child=StockEntryUpdateDetailSerializer(), allow_empty=False)
