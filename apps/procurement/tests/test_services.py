import pytest

from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.inventory.tests.factories import SupplierFactory, UserFactory
from apps.procurement.models import Supplier
from apps.procurement.services import supplier_create, supplier_delete, supplier_update


@pytest.mark.django_db
class TestSupplierServices:
    def test_supplier_create_success(self):
        user = UserFactory()
        supplier = supplier_create(
            user=user,
            name="SUPP-001",
            supplier_name="Test Supplier 1",
            supplier_group="Hardware",
            contact_email="supp1@example.com",
            contact_phone="0987654321",
            address="123 Street",
        )
        assert supplier.id is not None
        assert supplier.name == "SUPP-001"
        assert supplier.supplier_name == "Test Supplier 1"
        assert Supplier.objects.filter(id=supplier.id).exists()

    def test_supplier_create_duplicate_name(self):
        user = UserFactory()
        SupplierFactory(name="SUPP-001")

        with pytest.raises(ValidationException, match="Mã nhà cung cấp đã tồn tại"):
            supplier_create(user=user, name="SUPP-001", supplier_name="Test Supplier 2")

    def test_supplier_update_success(self):
        user = UserFactory()
        supplier = SupplierFactory(name="SUPP-001", supplier_name="Old Name")

        updated = supplier_update(
            user=user,
            supplier_id=str(supplier.id),
            name="SUPP-001-NEW",
            supplier_name="New Name",
            supplier_group="Software",
            contact_email="new@example.com",
            contact_phone="0123456789",
            address="456 Avenue",
        )

        assert updated.name == "SUPP-001-NEW"
        assert updated.supplier_name == "New Name"
        assert updated.supplier_group == "Software"
        assert updated.contact_email == "new@example.com"
        assert updated.contact_phone == "0123456789"
        assert updated.address == "456 Avenue"

    def test_supplier_update_not_found(self):
        user = UserFactory()
        import uuid

        with pytest.raises(NotFoundException, match="Nhà cung cấp không tồn tại"):
            supplier_update(user=user, supplier_id=str(uuid.uuid4()), name="SUPP-002", supplier_name="Name")

    def test_supplier_update_duplicate_name(self):
        user = UserFactory()
        SupplierFactory(name="SUPP-001")
        supplier2 = SupplierFactory(name="SUPP-002")

        with pytest.raises(ValidationException, match="Mã nhà cung cấp đã tồn tại ở bản ghi khác"):
            supplier_update(user=user, supplier_id=str(supplier2.id), name="SUPP-001", supplier_name="Name")

    def test_supplier_delete_success(self):
        user = UserFactory()
        supplier = SupplierFactory()

        supplier_delete(user=user, supplier_id=str(supplier.id))
        assert not Supplier.objects.filter(id=supplier.id).exists()

    def test_supplier_delete_has_purchase_order(self):
        user = UserFactory()
        supplier = SupplierFactory()

        # Create PurchaseOrder referencing Supplier
        from apps.purchasing.tests.factories import PurchaseOrderFactory

        PurchaseOrderFactory(vendor=supplier)

        with pytest.raises(ValidationException, match="Không thể xóa nhà cung cấp đã có đơn mua hàng"):
            supplier_delete(user=user, supplier_id=str(supplier.id))
