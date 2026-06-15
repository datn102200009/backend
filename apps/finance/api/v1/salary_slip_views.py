from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.services import (
    payroll_approve_slip,
    payroll_bulk_approve_and_pay,
    payroll_pay_slip,
    payroll_reject_slip,
)
from apps.hrm.api.v1.serializers import SalarySlipOutputSerializer

from .serializers import (
    SalarySlipBulkApprovePayInputSerializer,
    SalarySlipPaymentInputSerializer,
    SalarySlipRejectInputSerializer,
)


class SalarySlipApproveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id, *args, **kwargs):
        slip = payroll_approve_slip(user=request.user, salary_slip_id=str(id))
        out_serializer = SalarySlipOutputSerializer(slip)
        return Response(out_serializer.data, status=status.HTTP_200_OK)


class SalarySlipRejectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id, *args, **kwargs):
        serializer = SalarySlipRejectInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        slip = payroll_reject_slip(user=request.user, salary_slip_id=str(id), reason=reason)
        out_serializer = SalarySlipOutputSerializer(slip)
        return Response(out_serializer.data, status=status.HTTP_200_OK)


class SalarySlipPayAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id, *args, **kwargs):
        serializer = SalarySlipPaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment_method = serializer.validated_data.get("payment_method", "bank_transfer")

        slip = payroll_pay_slip(user=request.user, salary_slip_id=str(id), payment_method=payment_method)
        out_serializer = SalarySlipOutputSerializer(slip)
        return Response(out_serializer.data, status=status.HTTP_200_OK)


class SalarySlipBulkApprovePayAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = SalarySlipBulkApprovePayInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        salary_period = serializer.validated_data["salary_period"]
        payment_method = serializer.validated_data.get("payment_method", "bank_transfer")

        slips = payroll_bulk_approve_and_pay(
            salary_period=salary_period,
            payment_method=payment_method,
            creator=request.user,
        )
        out_serializer = SalarySlipOutputSerializer(slips, many=True)
        return Response(out_serializer.data, status=status.HTTP_200_OK)
