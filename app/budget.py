"""Estimated OpenAI spending guard; Firestore is the shared cloud backend."""

import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.pricing import estimated_openai_cost


MONTHLY_LIMIT_MICRO_USD = 5_000_000
# 80 chunks x (20k input at $0.10/M + 4096 output at $0.50/M), rounded up.
RESERVATION_MICRO_USD = 325_000


class BudgetExceeded(Exception):
    pass


@dataclass(frozen=True)
class Reservation:
    period: str
    token: str


def period_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def actual_micro_usd(metadata: dict) -> int | None:
    estimate = estimated_openai_cost(metadata)
    return round(estimate * 1_000_000) if estimate is not None else None


class MemoryBudget:
    """Single-process development backend; never use for a shared cloud limit."""

    def __init__(self):
        self.lock = threading.Lock()
        self.totals: dict[str, dict[str, int]] = {}
        self.reservations: dict[str, tuple[str, int]] = {}

    def reserve(self) -> Reservation:
        period = period_now()
        with self.lock:
            total = self.totals.setdefault(period, {"spent": 0, "reserved": 0})
            if total["spent"] + total["reserved"] + RESERVATION_MICRO_USD > MONTHLY_LIMIT_MICRO_USD:
                raise BudgetExceeded("Estimated monthly OpenAI allowance has been reached")
            total["reserved"] += RESERVATION_MICRO_USD
            token = uuid.uuid4().hex
            self.reservations[token] = (period, RESERVATION_MICRO_USD)
            return Reservation(period, token)

    def settle(self, reservation: Reservation, actual: int | None) -> None:
        with self.lock:
            entry = self.reservations.pop(reservation.token, None)
            if entry is None:
                return
            period, reserved = entry
            total = self.totals[period]
            total["reserved"] -= reserved
            total["spent"] += reserved if actual is None else max(0, actual)


class FirestoreBudget:
    def __init__(self):
        from google.cloud import firestore

        self.firestore = firestore
        self.client = firestore.Client()

    def reserve(self) -> Reservation:
        period = period_now()
        token = uuid.uuid4().hex
        budget_ref = self.client.collection("document_intelligence_budgets").document(period)
        entry_ref = budget_ref.collection("reservations").document(token)

        @self.firestore.transactional
        def transaction_body(transaction):
            snapshot = budget_ref.get(transaction=transaction)
            data = snapshot.to_dict() or {}
            spent = int(data.get("spent_micro_usd", 0))
            reserved = int(data.get("reserved_micro_usd", 0))
            if spent + reserved + RESERVATION_MICRO_USD > MONTHLY_LIMIT_MICRO_USD:
                raise BudgetExceeded("Estimated monthly OpenAI allowance has been reached")
            transaction.set(budget_ref, {"spent_micro_usd": spent,
                                         "reserved_micro_usd": reserved + RESERVATION_MICRO_USD})
            transaction.create(entry_ref, {"reserved_micro_usd": RESERVATION_MICRO_USD,
                                           "state": "reserved"})

        transaction_body(self.client.transaction())
        return Reservation(period, token)

    def settle(self, reservation: Reservation, actual: int | None) -> None:
        budget_ref = self.client.collection("document_intelligence_budgets").document(reservation.period)
        entry_ref = budget_ref.collection("reservations").document(reservation.token)

        @self.firestore.transactional
        def transaction_body(transaction):
            budget = budget_ref.get(transaction=transaction).to_dict() or {}
            entry = entry_ref.get(transaction=transaction).to_dict() or {}
            if entry.get("state") != "reserved":
                return
            reserved = int(entry["reserved_micro_usd"])
            charge = reserved if actual is None else max(0, actual)
            transaction.set(budget_ref, {
                "spent_micro_usd": int(budget.get("spent_micro_usd", 0)) + charge,
                "reserved_micro_usd": int(budget.get("reserved_micro_usd", 0)) - reserved,
            })
            transaction.set(entry_ref, {"reserved_micro_usd": reserved, "state": "settled",
                                        "charged_micro_usd": charge})

        transaction_body(self.client.transaction())


def make_budget():
    backend = os.getenv("BUDGET_BACKEND", "memory")
    if backend == "firestore":
        return FirestoreBudget()
    if backend == "memory" and not os.getenv("K_SERVICE"):
        return MemoryBudget()
    raise RuntimeError("Cloud Run requires BUDGET_BACKEND=firestore")
