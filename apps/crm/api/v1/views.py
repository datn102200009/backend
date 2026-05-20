from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.xlib.exceptions import NotFoundException, PermissionException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.crm.selectors import customer_detail, customer_list
from apps.crm.services import customer_create, customer_delete, customer_update

from .serializers import CustomerInputSerializer, CustomerSerializer


class CustomerListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            PermissionChecker.check_permission(request.user, "crm.customer_view")
            customers = customer_list()
            return Response(CustomerSerializer(customers, many=True).data)
        except PermissionException as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationException as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except NotFoundException as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, *args, **kwargs):
        try:
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
            )
            return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)
        except PermissionException as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationException as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except NotFoundException as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)


class CustomerDetailUpdateDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        try:
            PermissionChecker.check_permission(request.user, "crm.customer_view")
            customer = customer_detail(customer_id=str(pk))
            return Response(CustomerSerializer(customer).data)
        except PermissionException as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationException as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except NotFoundException as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk, *args, **kwargs):
        try:
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
            )
            return Response(CustomerSerializer(customer).data)
        except PermissionException as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationException as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except NotFoundException as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk, *args, **kwargs):
        try:
            customer_delete(user=request.user, customer_id=str(pk))
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PermissionException as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationException as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except NotFoundException as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
