"""Scenario definitions and fixed volume plan for the synthetic corpus."""

from dataclasses import dataclass
from enum import Enum


class Scenario(str, Enum):
    NORMAL_CUSTOMER = "NORMAL_CUSTOMER"
    LEGITIMATE_HIGH_VALUE = "LEGITIMATE_HIGH_VALUE"
    SUSPICIOUS_INDIVIDUAL = "SUSPICIOUS_INDIVIDUAL"
    COORDINATED_ABUSE_RING = "COORDINATED_ABUSE_RING"
    BENIGN_SHARED_INFRASTRUCTURE = "BENIGN_SHARED_INFRASTRUCTURE"


@dataclass(frozen=True)
class ScenarioPlan:
    scenario: Scenario
    customer_count: int
    transaction_count: int


# Exactly 10,000 transactions. The balance intentionally makes normal behaviour
# dominant while leaving several non-abusive shared-infrastructure examples.
SCENARIO_PLANS = (
    ScenarioPlan(Scenario.NORMAL_CUSTOMER, 300, 5_000),
    ScenarioPlan(Scenario.LEGITIMATE_HIGH_VALUE, 35, 1_200),
    ScenarioPlan(Scenario.SUSPICIOUS_INDIVIDUAL, 45, 900),
    ScenarioPlan(Scenario.COORDINATED_ABUSE_RING, 100, 2_100),
    ScenarioPlan(Scenario.BENIGN_SHARED_INFRASTRUCTURE, 50, 800),
)

TOTAL_TRANSACTIONS = sum(plan.transaction_count for plan in SCENARIO_PLANS)
