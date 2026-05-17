from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.inventory.tests.factories import BOMFactory, BOMItemFactory, ItemFactory, WarehouseFactory, WorkOrderFactory


@pytest.mark.django_db
class TestBOMAPIViews:
    def test_bom_create_unauthorized(self, api_client):
        url = "/api/v1/manufacturing/bom/create/"
        response = api_client.post(url, data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_bom_create_authorized(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        finished_item = ItemFactory()
        component_item = ItemFactory()

        url = "/api/v1/manufacturing/bom/create/"
        data = {
            "name": "API-BOM",
            "item_id": str(finished_item.id),
            "quantity": "1.0",
            "items": [{"item_id": str(component_item.id), "quantity": "5.0"}],
        }

        response = api_client.post(url, data=data, format="json")
        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data["name"] == "API-BOM"
        assert response.data["quantity"] == "1.00"

    def test_bom_update(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        bom = BOMFactory(name="Old Name")
        BOMItemFactory(parent=bom)
        new_component = ItemFactory()

        url = f"/api/v1/manufacturing/bom/{bom.id}/update/"
        data = {
            "name": "Updated API BOM",
            "quantity": "10.0",
            "items": [{"item_id": str(new_component.id), "quantity": "2.0"}],
        }

        response = api_client.put(url, data=data, format="json")
        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["name"] == "Updated API BOM"
        assert response.data["quantity"] == "10.00"
        assert len(response.data["items"]) == 1

    def test_bom_update_duplicate_name(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        BOMFactory(name="Existing Name")
        bom = BOMFactory(name="Old Name")
        BOMItemFactory(parent=bom)

        url = f"/api/v1/manufacturing/bom/{bom.id}/update/"
        data = {"name": "Existing Name", "quantity": "10.0"}

        response = api_client.put(url, data=data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "error" in response.data or "errors" in response.data

    def test_bom_delete(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        bom = BOMFactory()

        url = f"/api/v1/manufacturing/bom/{bom.id}/delete/"
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_200_OK

    def test_bom_list(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        BOMFactory.create_batch(3)

        url = "/api/v1/manufacturing/bom/list/"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 3

    def test_bom_detail(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        bom = BOMFactory()
        BOMItemFactory(parent=bom)

        url = f"/api/v1/manufacturing/bom/{bom.id}/"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(bom.id)


@pytest.mark.django_db
class TestWorkOrderAPIViews:
    def test_work_order_create_authorized(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        bom = BOMFactory(is_active=True)
        source = WarehouseFactory()
        target = WarehouseFactory()
        production = WarehouseFactory()

        url = "/api/v1/manufacturing/work-order/create/"
        data = {
            "name": "API-WO",
            "bom_id": str(bom.id),
            "quantity": 50,
            "source_warehouse_id": str(source.id),
            "target_warehouse_id": str(target.id),
            "production_warehouse_id": str(production.id),
            "planned_start_date": timezone.now().date().isoformat(),
        }

        response = api_client.post(url, data=data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "API-WO"

    def test_work_order_approve(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        bom = BOMFactory(is_active=True, quantity=Decimal("1.0"))
        BOMItemFactory(parent=bom, quantity=Decimal("2.0"))
        source = WarehouseFactory()
        target = WarehouseFactory()
        production = WarehouseFactory()
        wo = WorkOrderFactory(
            bom=bom,
            status="pending_approval",
            quantity=10,
            source_warehouse=source,
            target_warehouse=target,
            production_warehouse=production,
        )

        url = f"/api/v1/manufacturing/work-order/{wo.id}/approve/"
        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "in_progress"

    def test_work_order_declare_production(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        bom = BOMFactory(is_active=True, quantity=Decimal("1.0"))
        BOMItemFactory(parent=bom, quantity=Decimal("2.0"))
        source = WarehouseFactory()
        target = WarehouseFactory()
        production = WarehouseFactory()
        wo = WorkOrderFactory(
            bom=bom,
            production_item=bom.item,
            status="in_progress",
            source_warehouse=source,
            target_warehouse=target,
            production_warehouse=production,
        )

        url = f"/api/v1/manufacturing/work-order/{wo.id}/declare/"
        data = {"produced_qty": "5.0"}
        response = api_client.post(url, data=data, format="json")

        assert response.status_code == status.HTTP_200_OK

    def test_work_order_material_preview(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        bom = BOMFactory(is_active=True, quantity=Decimal("1.0"))
        BOMItemFactory(parent=bom, quantity=Decimal("2.0"))
        warehouse = WarehouseFactory()

        url = "/api/v1/manufacturing/material-preview/"
        data = {
            "bom_id": str(bom.id),
            "quantity": "10.0",
            "source_warehouse_id": str(warehouse.id),
        }
        response = api_client.post(url, data=data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert "missing_qty" in response.data[0]

    def test_work_order_complete(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        bom = BOMFactory(is_active=True)
        wo = WorkOrderFactory(
            bom=bom,
            production_item=bom.item,
            status="in_progress",
            quantity=100,
            produced_qty=100,
        )

        url = f"/api/v1/manufacturing/work-order/{wo.id}/complete/"
        data = {}

        response = api_client.post(url, data=data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "completed"

    def test_work_order_cancel(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        bom = BOMFactory(is_active=True)
        wo = WorkOrderFactory(bom=bom, production_item=bom.item, status="pending_approval")

        url = f"/api/v1/manufacturing/work-order/{wo.id}/cancel/"
        data = {}

        response = api_client.post(url, data=data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "cancelled"

    def test_work_order_list(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        WorkOrderFactory.create_batch(3)

        url = "/api/v1/manufacturing/work-order/list/"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 3

    def test_work_order_detail(self, api_client, production_user):
        api_client.force_authenticate(user=production_user)
        wo = WorkOrderFactory()

        url = f"/api/v1/manufacturing/work-order/{wo.id}/"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(wo.id)
