"""The local ledger mirrors reservation and settlement rules used in cloud."""

import unittest

from app.budget import (BudgetExceeded, MemoryBudget, MONTHLY_LIMIT_MICRO_USD,
                        RESERVATION_MICRO_USD, period_now)


class BudgetTests(unittest.TestCase):
    def test_reservations_limit_concurrent_requests(self):
        budget = MemoryBudget()
        reservations = [budget.reserve() for _ in range(MONTHLY_LIMIT_MICRO_USD // RESERVATION_MICRO_USD)]
        with self.assertRaises(BudgetExceeded):
            budget.reserve()
        budget.settle(reservations[0], 100)
        self.assertEqual(budget.totals[period_now()]["spent"], 100)
        budget.reserve()

    def test_unknown_usage_keeps_reservation(self):
        budget = MemoryBudget()
        token = budget.reserve()
        budget.settle(token, None)
        budget.settle(token, 0)
        self.assertEqual(budget.totals[period_now()]["spent"], RESERVATION_MICRO_USD)


if __name__ == "__main__":
    unittest.main()
