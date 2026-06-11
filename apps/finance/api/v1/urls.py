from django.urls import path

from .views import (
    CashFlowApproveAPIView,
    CashFlowDetailAPIView,
    CashFlowListCreateAPIView,
    DepreciationLogListAPIView,
    DepreciationRunAPIView,
    FixedAssetDetailAPIView,
    FixedAssetListCreateAPIView,
    PurchaseInvoicePayAPIView,
)

urlpatterns = [
    path("cash-flows/", CashFlowListCreateAPIView.as_view(), name="cash-flow-list-create"),
    path("cash-flows/<uuid:pk>/", CashFlowDetailAPIView.as_view(), name="cash-flow-detail"),
    path("cash-flows/<uuid:pk>/approve/", CashFlowApproveAPIView.as_view(), name="cash-flow-approve"),
    path("fixed-assets/", FixedAssetListCreateAPIView.as_view(), name="fixed-asset-list-create"),
    path("fixed-assets/depreciation/", DepreciationRunAPIView.as_view(), name="depreciation-run"),
    path("fixed-assets/depreciation-logs/", DepreciationLogListAPIView.as_view(), name="depreciation-log-list"),
    path("fixed-assets/<uuid:pk>/", FixedAssetDetailAPIView.as_view(), name="fixed-asset-detail"),
    path("invoices/purchase/<uuid:pk>/pay/", PurchaseInvoicePayAPIView.as_view(), name="purchase-invoice-pay"),
]
