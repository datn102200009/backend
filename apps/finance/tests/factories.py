import factory
from django.utils import timezone
from factory import fuzzy

from apps.finance.models import CashFlowTransaction


class CashFlowTransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CashFlowTransaction

    name = factory.Sequence(lambda n: f"CF-TEST-{n:04d}")
    payment_type = fuzzy.FuzzyChoice(["receive", "pay"])
    amount = fuzzy.FuzzyDecimal(10.00, 1000.00, 2)
    payment_date = factory.LazyFunction(timezone.now)
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)
