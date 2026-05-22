import pytest

from apps.finance.models import CashFlowTransaction
from apps.finance.tests.factories import CashFlowTransactionFactory

pytestmark = pytest.mark.django_db


class TestCashFlowModel:
    def test_cash_flow_creation(self):
        transaction = CashFlowTransactionFactory(payment_type="receive", amount=150.0)
        assert transaction.id is not None
        assert transaction.payment_type == "receive"
        assert transaction.amount == 150.0
        assert str(transaction).startswith("CF-")
