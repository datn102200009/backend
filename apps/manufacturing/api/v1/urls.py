"""
URL routing for manufacturing API v1.
"""

from django.urls import path

from apps.manufacturing.api.v1.views import (
    bom_create_view,
    bom_delete_view,
    bom_detail_view,
    bom_list_view,
    bom_update_view,
    material_preview_view,
    work_order_approve_view,
    work_order_cancel_view,
    work_order_complete_view,
    work_order_create_view,
    work_order_declare_production_view,
    work_order_detail_view,
    work_order_list_view,
)

urlpatterns = [
    # BOM endpoints
    path("bom/create/", bom_create_view, name="bom-create"),
    path("bom/<uuid:bom_id>/update/", bom_update_view, name="bom-update"),
    path("bom/<uuid:bom_id>/delete/", bom_delete_view, name="bom-delete"),
    path("bom/list/", bom_list_view, name="bom-list"),
    path("bom/<uuid:bom_id>/", bom_detail_view, name="bom-detail"),
    # Work Order endpoints
    path("material-preview/", material_preview_view, name="material-preview"),
    path("work-order/create/", work_order_create_view, name="work-order-create"),
    path(
        "work-order/<uuid:work_order_id>/approve/",
        work_order_approve_view,
        name="work-order-approve",
    ),
    path(
        "work-order/<uuid:work_order_id>/declare/",
        work_order_declare_production_view,
        name="work-order-declare",
    ),
    path(
        "work-order/<uuid:work_order_id>/complete/",
        work_order_complete_view,
        name="work-order-complete",
    ),
    path(
        "work-order/<uuid:work_order_id>/cancel/",
        work_order_cancel_view,
        name="work-order-cancel",
    ),
    path("work-order/list/", work_order_list_view, name="work-order-list"),
    path(
        "work-order/<uuid:work_order_id>/",
        work_order_detail_view,
        name="work-order-detail",
    ),
]
