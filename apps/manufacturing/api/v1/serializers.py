"""
Serializers for manufacturing API v1.

Handles validation and transformation of data for BOM and WorkOrder.
"""

from rest_framework import serializers

from apps.master_data.models import BOM, BOMItem, WorkOrder

# ======================== BOM Serializers ========================


class BOMItemCreateUpdateSerializer(serializers.Serializer):
    """Serializer cho việc tạo/cập nhật chi tiết BOM (chỉ nhận input)."""

    item_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0)


class BOMCreateSerializer(serializers.Serializer):
    """Serializer cho request tạo BOM."""

    name = serializers.CharField(max_length=255)
    item_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01, required=False, default=1)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    items = BOMItemCreateUpdateSerializer(many=True)


class BOMUpdateSerializer(serializers.Serializer):
    """Serializer cho request cập nhật BOM."""

    name = serializers.CharField(max_length=255, required=False)
    quantity = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01, required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    items = BOMItemCreateUpdateSerializer(many=True, required=False)


class BOMItemSerializer(serializers.ModelSerializer):
    """Serializer cho output chi tiết BOM."""

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


class BOMListSerializer(serializers.ModelSerializer):
    """Serializer cho danh sách BOM (không kèm chi tiết items để nhẹ API)."""

    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    items_count = serializers.IntegerField(source="items.count", read_only=True)

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
            "items_count",
            "created_at",
            "updated_at",
        ]


class BOMDetailSerializer(BOMListSerializer):
    """Serializer cho chi tiết BOM (kèm items)."""

    items = BOMItemSerializer(many=True, read_only=True)

    class Meta(BOMListSerializer.Meta):
        fields = BOMListSerializer.Meta.fields + ["items"]


# ======================== Work Order Serializers ========================


class WorkOrderCreateSerializer(serializers.Serializer):
    """Serializer cho request tạo Work Order."""

    name = serializers.CharField(max_length=255)
    bom_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)
    source_warehouse_id = serializers.UUIDField()
    target_warehouse_id = serializers.UUIDField()
    production_warehouse_id = serializers.UUIDField()
    planned_start_date = serializers.DateField()
    planned_end_date = serializers.DateField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    fixed_asset_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        help_text="Danh sách ID tài sản cố định (UOP) sử dụng cho lệnh sản xuất.",
    )


class WorkOrderDeclareProductionSerializer(serializers.Serializer):
    """Serializer cho request nhập liệu sản xuất."""

    produced_qty = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)


class WorkOrderDeclarePreviewRequestSerializer(serializers.Serializer):
    """Serializer cho request preview nguyên liệu nhập liệu."""

    produced_qty = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)


class WorkOrderCompleteSerializer(serializers.Serializer):
    """Serializer cho request hoàn thành Work Order."""

    pass  # Không nhận data gì thêm, ID lấy từ URL


class WorkOrderCancelSerializer(serializers.Serializer):
    """Serializer cho request hủy Work Order."""

    pass  # Không nhận data gì thêm, ID lấy từ URL


class MaterialPreviewRequestSerializer(serializers.Serializer):
    """Serializer cho request preview nguyên liệu."""

    bom_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)
    source_warehouse_id = serializers.UUIDField()


class WorkOrderFixedAssetOutputSerializer(serializers.ModelSerializer):
    """Output cho 1 dòng link WorkOrder ↔ FixedAsset."""

    fixed_asset_id = serializers.UUIDField(read_only=True)
    asset_code = serializers.CharField(source="fixed_asset.asset_code", read_only=True)
    asset_name = serializers.CharField(source="fixed_asset.asset_name", read_only=True)
    depreciation_method = serializers.CharField(source="fixed_asset.depreciation_method", read_only=True)

    class Meta:
        from apps.master_data.models import WorkOrderFixedAsset

        model = WorkOrderFixedAsset
        fields = ["id", "fixed_asset_id", "asset_code", "asset_name", "depreciation_method"]


class WorkOrderSerializer(serializers.ModelSerializer):
    """Serializer cho output Work Order."""

    bom_name = serializers.CharField(source="bom.name", read_only=True)
    production_item_code = serializers.CharField(source="production_item.item_code", read_only=True)
    production_item_name = serializers.CharField(source="production_item.item_name", read_only=True)
    production_uom = serializers.CharField(source="production_item.stock_uom.name", read_only=True, allow_null=True)
    source_warehouse = serializers.CharField(source="source_warehouse.name", read_only=True)
    target_warehouse = serializers.CharField(source="target_warehouse.name", read_only=True)
    production_warehouse = serializers.CharField(source="production_warehouse.name", read_only=True)
    fixed_assets = WorkOrderFixedAssetOutputSerializer(source="fixed_asset_links", many=True, read_only=True)

    class Meta:
        model = WorkOrder
        fields = [
            "id",
            "name",
            "bom",
            "bom_name",
            "production_item",
            "production_item_code",
            "production_item_name",
            "production_uom",
            "quantity",
            "produced_qty",
            "source_warehouse",
            "target_warehouse",
            "production_warehouse",
            "status",
            "planned_start_date",
            "planned_end_date",
            "actual_end_date",
            "remarks",
            "fixed_assets",
            "created_at",
            "updated_at",
        ]


class WorkOrderMaterialSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    item_code = serializers.CharField()
    item_name = serializers.CharField()
    uom = serializers.CharField(allow_null=True)
    required_qty = serializers.FloatField()
    consumed_qty = serializers.FloatField()


class WorkOrderDetailWithMaterialsSerializer(WorkOrderSerializer):
    materials = WorkOrderMaterialSerializer(many=True, read_only=True)

    class Meta(WorkOrderSerializer.Meta):
        fields = WorkOrderSerializer.Meta.fields + ["materials"]


class WorkOrderFixedAssetsUpdateSerializer(serializers.Serializer):
    fixed_asset_ids = serializers.ListField(
        child=serializers.UUIDField(),
        default=list,
    )
