from django.urls import path

from .views import CashFlowDetailAPIView, CashFlowListCreateAPIView

urlpatterns = [
    path("cash-flows/", CashFlowListCreateAPIView.as_view(), name="cash-flow-list-create"),
    path("cash-flows/<uuid:pk>/", CashFlowDetailAPIView.as_view(), name="cash-flow-detail"),
]
