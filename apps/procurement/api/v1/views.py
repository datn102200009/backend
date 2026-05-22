from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.xlib.permissions import PermissionChecker
from apps.procurement.selectors import supplier_detail, supplier_list
from apps.procurement.services import supplier_create, supplier_delete, supplier_update

from .serializers import SupplierInputSerializer, SupplierSerializer


class SupplierListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "procurement.supplier_view")
        suppliers = supplier_list()
        return Response(SupplierSerializer(suppliers, many=True).data)

    def post(self, request, *args, **kwargs):
        serializer = SupplierInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        supplier = supplier_create(
            user=request.user,
            name=serializer.validated_data["name"],
            supplier_name=serializer.validated_data["supplier_name"],
            supplier_group=serializer.validated_data.get("supplier_group"),
            contact_email=serializer.validated_data.get("contact_email"),
            contact_phone=serializer.validated_data.get("contact_phone"),
            address=serializer.validated_data.get("address"),
        )
        return Response(SupplierSerializer(supplier).data, status=status.HTTP_201_CREATED)


class SupplierDetailUpdateDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        PermissionChecker.check_permission(request.user, "procurement.supplier_view")
        supplier = supplier_detail(supplier_id=str(pk))
        return Response(SupplierSerializer(supplier).data)

    def put(self, request, pk, *args, **kwargs):
        serializer = SupplierInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        supplier = supplier_update(
            user=request.user,
            supplier_id=str(pk),
            name=serializer.validated_data["name"],
            supplier_name=serializer.validated_data["supplier_name"],
            supplier_group=serializer.validated_data.get("supplier_group"),
            contact_email=serializer.validated_data.get("contact_email"),
            contact_phone=serializer.validated_data.get("contact_phone"),
            address=serializer.validated_data.get("address"),
        )
        return Response(SupplierSerializer(supplier).data)

    def delete(self, request, pk, *args, **kwargs):
        supplier_delete(user=request.user, supplier_id=str(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
