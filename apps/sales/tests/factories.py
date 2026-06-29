import factory
from django.utils import timezone
from factory import fuzzy

from apps.inventory.tests.factories import CustomerFactory, ItemFactory
from apps.sales.models import SalesInvoice, SalesInvoiceLine, SalesOrder, SalesOrderLine


class SalesOrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SalesOrder

    customer = factory.SubFactory(CustomerFactory)
    status = SalesOrder.Status.DRAFT
    total_amount = fuzzy.FuzzyDecimal(100.00, 10000.00, 2)
    advance_paid_amount = 0
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


class SalesOrderLineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SalesOrderLine

    order = factory.SubFactory(SalesOrderFactory)
    item = factory.SubFactory(ItemFactory)
    quantity = fuzzy.FuzzyDecimal(1.0, 100.0, 2)
    unit_price = fuzzy.FuzzyDecimal(10.00, 1000.00, 2)
    line_total = factory.LazyAttribute(lambda o: o.quantity * o.unit_price)


class SalesInvoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SalesInvoice

    order = factory.SubFactory(SalesOrderFactory)
    customer = factory.SelfAttribute("order.customer")
    status = SalesInvoice.Status.UNPAID
    total_amount = fuzzy.FuzzyDecimal(100.00, 10000.00, 2)
    paid_amount = 0
    due_date = factory.LazyFunction(lambda: timezone.now().date())
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


class SalesInvoiceLineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SalesInvoiceLine

    invoice = factory.SubFactory(SalesInvoiceFactory)
    item = factory.SubFactory(ItemFactory)
    quantity = fuzzy.FuzzyDecimal(1.0, 100.0, 2)
    unit_price = fuzzy.FuzzyDecimal(10.00, 1000.00, 2)
    vat_tax = 0
    line_total = factory.LazyAttribute(lambda o: (o.quantity * o.unit_price) + o.vat_tax)
