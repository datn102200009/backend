"""
URL routing for master_data API v1.
"""

from django.urls import path

from apps.master_data.api.v1 import views

app_name = "master_data_v1"

urlpatterns = [
    path("warehouses/list/", views.warehouse_list_view, name="warehouse_list"),
    path("uoms/list/", views.uom_list_view, name="uom_list"),
    path("items/list/", views.item_list_view, name="item_list"),
    path("items/create/", views.item_create_view, name="item_create"),
    path("items/<str:item_code>/detail/", views.item_detail_view, name="item_detail"),
    path("items/<str:item_code>/update/", views.item_update_view, name="item_update"),
    path("items/<str:item_code>/delete/", views.item_delete_view, name="item_delete"),
]
