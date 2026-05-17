"""
Serializers for master_data API v1.

Handles validation and transformation of data.
"""

from rest_framework import serializers

from apps.master_data.models import UOM, Item, Warehouse


class UOMOutputSerializer(serializers.ModelSerializer):
    """
    Serializer for UOM output.
    """

    class Meta:
        model = UOM
        fields = [
            "id",
            "name",
        ]


class WarehouseOutputSerializer(serializers.ModelSerializer):
    """
    Serializer for Warehouse output.
    """

    class Meta:
        model = Warehouse
        fields = [
            "id",
            "name",
        ]


class ItemOutputSerializer(serializers.ModelSerializer):
    """
    Serializer for item output.
    """

    stock_uom_name = serializers.CharField(source="stock_uom.name", read_only=True)

    class Meta:
        model = Item
        fields = [
            "id",
            "item_code",
            "item_name",
            "item_group_id",
            "stock_uom_id",
            "stock_uom_name",
            "hs_code",
            "recycling_coef_a",
            "vat_group",
            "is_import",
            "status",
            "description",
            "created_at",
            "updated_at",
        ]


class ItemCreateInputSerializer(serializers.Serializer):
    """
    Serializer for item creation input validation.
    """

    item_code = serializers.CharField(max_length=100)
    item_name = serializers.CharField(max_length=255)
    item_group_id = serializers.UUIDField(required=False, allow_null=True)
    stock_uom_id = serializers.UUIDField(required=False, allow_null=True)
    hs_code = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    recycling_coef_a = serializers.DecimalField(
        max_digits=5, decimal_places=3, required=False, allow_null=True, min_value=0
    )
    vat_group = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    is_import = serializers.BooleanField(default=False)
    status = serializers.ChoiceField(choices=["active", "inactive", "discontinued"], default="active")
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ItemUpdateInputSerializer(serializers.Serializer):
    """
    Serializer for item update input validation.
    """

    item_name = serializers.CharField(max_length=255, required=False)
    item_group_id = serializers.UUIDField(required=False, allow_null=True)
    stock_uom_id = serializers.UUIDField(required=False, allow_null=True)
    hs_code = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    recycling_coef_a = serializers.DecimalField(
        max_digits=5, decimal_places=3, required=False, allow_null=True, min_value=0
    )
    vat_group = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    is_import = serializers.BooleanField(required=False)
    status = serializers.ChoiceField(choices=["active", "inactive", "discontinued"], required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
