import pytest

from apps.finance.selectors import cash_flow_list
from apps.finance.tests.factories import CashFlowTransactionFactory

pytestmark = pytest.mark.django_db


class TestFinanceSelectors:
    def test_cash_flow_list(self):
        CashFlowTransactionFactory.create_batch(3)
        transactions = cash_flow_list()
        assert transactions.count() == 3
