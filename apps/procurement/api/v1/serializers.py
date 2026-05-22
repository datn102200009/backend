from rest_framework import serializers

from apps.procurement.models import Supplier


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "supplier_name",
            "supplier_group",
            "contact_email",
            "contact_phone",
            "address",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SupplierInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    supplier_name = serializers.CharField(max_length=255)
    supplier_group = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
