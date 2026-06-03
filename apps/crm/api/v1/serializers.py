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
            "credit_limit",
            "payment_terms",
            "is_credit_locked",
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
    credit_limit = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, default=0.00)
    payment_terms = serializers.CharField(max_length=50, required=False, default="NET30")
    is_credit_locked = serializers.BooleanField(required=False, default=False)
