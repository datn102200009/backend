import pytest
from django.db.utils import IntegrityError

from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.crm.models import Customer
from apps.crm.services import customer_create, customer_delete, customer_update
from apps.inventory.tests.factories import CustomerFactory, UserFactory
from apps.sales.models import SalesOrder


@pytest.mark.django_db
class TestCustomerServices:
    def test_customer_create_success(self):
        user = UserFactory()
        customer = customer_create(
            user=user,
            name="CUST-001",
            customer_name="Test Customer 1",
            customer_group="Retail",
            contact_email="cust1@example.com",
            contact_phone="0987654321",
            address="123 Street",
        )
        assert customer.id is not None
        assert customer.name == "CUST-001"
        assert customer.customer_name == "Test Customer 1"
        assert Customer.objects.filter(id=customer.id).exists()

    def test_customer_create_duplicate_name(self):
        user = UserFactory()
        CustomerFactory(name="CUST-001")

        with pytest.raises(ValidationException, match="Mã khách hàng đã tồn tại"):
            customer_create(user=user, name="CUST-001", customer_name="Test Customer 2")

    def test_customer_update_success(self):
        user = UserFactory()
        customer = CustomerFactory(name="CUST-001", customer_name="Old Name")

        updated = customer_update(
            user=user,
            customer_id=str(customer.id),
            name="CUST-001-NEW",
            customer_name="New Name",
            customer_group="Wholesale",
            contact_email="new@example.com",
            contact_phone="0123456789",
            address="456 Avenue",
        )

        assert updated.name == "CUST-001-NEW"
        assert updated.customer_name == "New Name"
        assert updated.customer_group == "Wholesale"
        assert updated.contact_email == "new@example.com"
        assert updated.contact_phone == "0123456789"
        assert updated.address == "456 Avenue"

    def test_customer_update_not_found(self):
        user = UserFactory()
        import uuid

        with pytest.raises(NotFoundException, match="Khách hàng không tồn tại"):
            customer_update(user=user, customer_id=str(uuid.uuid4()), name="CUST-002", customer_name="Name")

    def test_customer_update_duplicate_name(self):
        user = UserFactory()
        CustomerFactory(name="CUST-001")
        customer2 = CustomerFactory(name="CUST-002")

        with pytest.raises(ValidationException, match="Mã khách hàng đã tồn tại ở bản ghi khác"):
            customer_update(user=user, customer_id=str(customer2.id), name="CUST-001", customer_name="Name")

    def test_customer_delete_success(self):
        user = UserFactory()
        customer = CustomerFactory()

        customer_delete(user=user, customer_id=str(customer.id))
        assert not Customer.objects.filter(id=customer.id).exists()

    def test_customer_delete_has_sales_order(self):
        user = UserFactory()
        customer = CustomerFactory()
        # Mock/Create SalesOrder referencing Customer
        from apps.sales.tests.factories import SalesOrderFactory

        SalesOrderFactory(customer=customer)

        with pytest.raises(ValidationException, match="Không thể xóa khách hàng đã có đơn bán hàng"):
            customer_delete(user=user, customer_id=str(customer.id))
