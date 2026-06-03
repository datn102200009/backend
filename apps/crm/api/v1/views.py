from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.xlib.permissions import PermissionChecker
from apps.crm.selectors import customer_detail, customer_list
from apps.crm.services import customer_create, customer_delete, customer_update

from .serializers import CustomerInputSerializer, CustomerSerializer


class CustomerListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "crm.customer_view")
        customers = customer_list()
        return Response(CustomerSerializer(customers, many=True).data)

    def post(self, request, *args, **kwargs):
        serializer = CustomerInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer = customer_create(
            user=request.user,
            name=serializer.validated_data["name"],
            customer_name=serializer.validated_data["customer_name"],
            customer_group=serializer.validated_data.get("customer_group"),
            contact_email=serializer.validated_data.get("contact_email"),
            contact_phone=serializer.validated_data.get("contact_phone"),
            address=serializer.validated_data.get("address"),
            credit_limit=serializer.validated_data.get("credit_limit"),
            payment_terms=serializer.validated_data.get("payment_terms"),
            is_credit_locked=serializer.validated_data.get("is_credit_locked"),
        )
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)


class CustomerDetailUpdateDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "crm.customer_view")
        customer = customer_detail(customer_id=str(pk))
        return Response(CustomerSerializer(customer).data)

    def put(self, request, pk, *args, **kwargs):
        serializer = CustomerInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer = customer_update(
            user=request.user,
            customer_id=str(pk),
            name=serializer.validated_data["name"],
            customer_name=serializer.validated_data["customer_name"],
            customer_group=serializer.validated_data.get("customer_group"),
            contact_email=serializer.validated_data.get("contact_email"),
            contact_phone=serializer.validated_data.get("contact_phone"),
            address=serializer.validated_data.get("address"),
            credit_limit=serializer.validated_data.get("credit_limit"),
            payment_terms=serializer.validated_data.get("payment_terms"),
            is_credit_locked=serializer.validated_data.get("is_credit_locked"),
        )
        return Response(CustomerSerializer(customer).data)

    def delete(self, request, pk, *args, **kwargs):
        customer_delete(user=request.user, customer_id=str(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
