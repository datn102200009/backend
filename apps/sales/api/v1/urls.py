from django.urls import path

from .views import (
    SalesOrderApproveAPIView,
    SalesOrderApproveCreditBypassAPIView,
    SalesOrderCancelAPIView,
    SalesOrderDeliverAPIView,
    SalesOrderDetailUpdateDeleteAPIView,
    SalesOrderListCreateAPIView,
)

urlpatterns = [
    # Orders
    path("orders/", SalesOrderListCreateAPIView.as_view(), name="sales-order-list-create"),
    path("orders/<uuid:pk>/", SalesOrderDetailUpdateDeleteAPIView.as_view(), name="sales-order-detail-update-delete"),
    path("orders/<uuid:pk>/deliver/", SalesOrderDeliverAPIView.as_view(), name="sales-order-deliver"),
    path("orders/<uuid:pk>/approve/", SalesOrderApproveAPIView.as_view(), name="sales-order-approve"),
    path(
        "orders/<uuid:pk>/approve-credit-bypass/",
        SalesOrderApproveCreditBypassAPIView.as_view(),
        name="sales-order-approve-credit-bypass",
    ),
    path("orders/<uuid:pk>/cancel/", SalesOrderCancelAPIView.as_view(), name="sales-order-cancel"),
]
