from django.urls import path

from .views import (
    CashFlowDetailAPIView,
    CashFlowListCreateAPIView,
    DepreciationLogListAPIView,
    DepreciationRunAPIView,
    FixedAssetDetailAPIView,
    FixedAssetListCreateAPIView,
)

urlpatterns = [
    path("cash-flows/", CashFlowListCreateAPIView.as_view(), name="cash-flow-list-create"),
    path("cash-flows/<uuid:pk>/", CashFlowDetailAPIView.as_view(), name="cash-flow-detail"),
    path("fixed-assets/", FixedAssetListCreateAPIView.as_view(), name="fixed-asset-list-create"),
    path("fixed-assets/<uuid:pk>/", FixedAssetDetailAPIView.as_view(), name="fixed-asset-detail"),
    path("fixed-assets/depreciation/", DepreciationRunAPIView.as_view(), name="depreciation-run"),
    path("fixed-assets/depreciation-logs/", DepreciationLogListAPIView.as_view(), name="depreciation-log-list"),
]
