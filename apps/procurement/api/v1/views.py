from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.xlib.exceptions import NotFoundException, PermissionException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.procurement.selectors import supplier_detail, supplier_list
from apps.procurement.services import supplier_create, supplier_delete, supplier_update

from .serializers import SupplierInputSerializer, SupplierSerializer


class SupplierListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            PermissionChecker.check_permission(request.user, "procurement.supplier_view")
            suppliers = supplier_list()
            return Response(SupplierSerializer(suppliers, many=True).data)
        except PermissionException as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationException as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except NotFoundException as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, *args, **kwargs):
        try:
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
        except PermissionException as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationException as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except NotFoundException as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)


class SupplierDetailUpdateDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        try:
            PermissionChecker.check_permission(request.user, "procurement.supplier_view")
            supplier = supplier_detail(supplier_id=str(pk))
            return Response(SupplierSerializer(supplier).data)
        except PermissionException as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationException as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except NotFoundException as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk, *args, **kwargs):
        try:
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
        except PermissionException as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationException as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except NotFoundException as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk, *args, **kwargs):
        try:
            supplier_delete(user=request.user, supplier_id=str(pk))
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PermissionException as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationException as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except NotFoundException as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
