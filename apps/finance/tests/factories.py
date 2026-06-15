import factory
from django.utils import timezone
from factory import fuzzy

from apps.finance.models import CashFlowTransaction, FixedAsset, FixedAssetDepreciationLog


class CashFlowTransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CashFlowTransaction
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"CF-TEST-{n:04d}")
    payment_type = fuzzy.FuzzyChoice(["receive", "pay"])
    amount = fuzzy.FuzzyDecimal(10.00, 1000.00, 2)
    payment_date = factory.LazyFunction(timezone.now)
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


class FixedAssetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FixedAsset
        django_get_or_create = ("asset_code",)

    asset_code = factory.Sequence(lambda n: f"ASSET-{n:04d}")
    asset_name = factory.Faker("word")
    original_value = fuzzy.FuzzyDecimal(1000.00, 10000.00, 2)
    salvage_value = fuzzy.FuzzyDecimal(0.00, 500.00, 2)
    depreciation_method = "straight_line"

    @factory.lazy_attribute
    def useful_life_months(self):
        if self.depreciation_method == "unit_of_production":
            return None
        return 24

    @factory.lazy_attribute
    def remaining_life_months(self):
        if self.depreciation_method == "unit_of_production":
            return None
        return self.useful_life_months

    @factory.lazy_attribute
    def designed_capacity(self):
        if self.depreciation_method == "straight_line":
            return None
        return 10000

    accumulated_depreciation = fuzzy.FuzzyDecimal(0, 0, 2)
    department = factory.Faker("word")
    status = "active"
    purchase_date = factory.LazyFunction(lambda: timezone.now().date())
    disposal_date = None
    disposal_value = None


class FixedAssetDepreciationLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FixedAssetDepreciationLog

    asset = factory.SubFactory(FixedAssetFactory)
    period = "2026-06"
    depreciation_amount = fuzzy.FuzzyDecimal(10.00, 100.00, 2)
    remarks = factory.Faker("sentence")
