from django.urls import path

from .views import SupplierDetailUpdateDeleteAPIView, SupplierListCreateAPIView

urlpatterns = [
    path("suppliers/", SupplierListCreateAPIView.as_view(), name="supplier-list-create"),
    path("suppliers/<uuid:pk>/", SupplierDetailUpdateDeleteAPIView.as_view(), name="supplier-detail-update-delete"),
]
