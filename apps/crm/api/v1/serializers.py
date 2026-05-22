from rest_framework import serializers

from apps.crm.models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "customer_name",
            "customer_group",
            "contact_email",
            "contact_phone",
            "address",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CustomerInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    customer_name = serializers.CharField(max_length=255)
    customer_group = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
