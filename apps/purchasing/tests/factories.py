import factory
from django.utils import timezone
from factory import fuzzy

from apps.inventory.tests.factories import ItemFactory, SupplierFactory
from apps.purchasing.models import PurchaseInvoice, PurchaseInvoiceLine, PurchaseOrder, PurchaseOrderLine


class PurchaseOrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PurchaseOrder

    vendor = factory.SubFactory(SupplierFactory)
    status = PurchaseOrder.Status.DRAFT
    total_amount = fuzzy.FuzzyDecimal(100.00, 10000.00, 2)
    advance_paid_amount = 0
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


class PurchaseOrderLineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PurchaseOrderLine

    order = factory.SubFactory(PurchaseOrderFactory)
    item = factory.SubFactory(ItemFactory)
    quantity = fuzzy.FuzzyDecimal(1.0, 100.0, 2)
    unit_price = fuzzy.FuzzyDecimal(10.00, 1000.00, 2)
    line_total = factory.LazyAttribute(lambda o: o.quantity * o.unit_price)


class PurchaseInvoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PurchaseInvoice

    order = factory.SubFactory(PurchaseOrderFactory)
    vendor = factory.SelfAttribute("order.vendor")
    status = PurchaseInvoice.Status.UNPAID
    total_amount = fuzzy.FuzzyDecimal(100.00, 10000.00, 2)
    paid_amount = 0
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


class PurchaseInvoiceLineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PurchaseInvoiceLine

    invoice = factory.SubFactory(PurchaseInvoiceFactory)
    item = factory.SubFactory(ItemFactory)
    quantity = fuzzy.FuzzyDecimal(1.0, 100.0, 2)
    unit_price = fuzzy.FuzzyDecimal(10.00, 1000.00, 2)
    import_tax = 0
    vat_tax = 0
    line_total = factory.LazyAttribute(lambda o: (o.quantity * o.unit_price) + o.import_tax + o.vat_tax)
