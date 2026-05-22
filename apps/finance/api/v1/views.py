from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.selectors import cash_flow_detail, cash_flow_list
from apps.finance.services import cash_flow_create

from .serializers import CashFlowInputSerializer, CashFlowTransactionSerializer


class CashFlowListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        transactions = cash_flow_list()
        return Response(CashFlowTransactionSerializer(transactions, many=True).data)

    def post(self, request, *args, **kwargs):
        serializer = CashFlowInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        transaction = cash_flow_create(
            user=request.user,
            payment_type=data["payment_type"],
            amount=data["amount"],
            payment_date=data["payment_date"],
            category=data.get("category"),
            purchase_order_id=data.get("purchase_order_id") and str(data["purchase_order_id"]),
            sales_order_id=data.get("sales_order_id") and str(data["sales_order_id"]),
            purchase_invoice_id=data.get("purchase_invoice_id") and str(data["purchase_invoice_id"]),
            sales_invoice_id=data.get("sales_invoice_id") and str(data["sales_invoice_id"]),
            remarks=data.get("remarks"),
        )
        return Response(CashFlowTransactionSerializer(transaction).data, status=status.HTTP_201_CREATED)


class CashFlowDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        transaction = cash_flow_detail(transaction_id=str(pk))
        return Response(CashFlowTransactionSerializer(transaction).data)
