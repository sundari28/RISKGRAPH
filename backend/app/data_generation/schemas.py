"""CSV schemas for model inputs and separately stored evaluation labels."""

from dataclasses import dataclass
from typing import Dict


CUSTOMER_COLUMNS = [
    "customer_id",
    "account_created_at",
    "account_age_days",
    "historical_transaction_count",
    "historical_refund_count",
    "historical_success_rate",
]

TRANSACTION_COLUMNS = [
    "transaction_id",
    "customer_id",
    "merchant_id",
    "amount",
    "timestamp",
    "payment_method",
    "payment_status",
    "device_id",
    "ip_address",
    "billing_address_id",
    "shipping_address_id",
    "refund_status",
    "refund_amount",
]

MERCHANT_COLUMNS = [
    "merchant_id",
    "merchant_category",
]

REFUND_COLUMNS = [
    "refund_id",
    "original_transaction_id",
    "refund_timestamp",
    "refund_amount",
    "refund_status",
]

GROUND_TRUTH_COLUMNS = [
    "entity_type",
    "entity_id",
    "scenario",
    "cluster_id",
    "is_coordinated_abuse",
    "dataset_split",
    "generator_seed",
]


@dataclass(frozen=True)
class DatasetResult:
    """In-memory result and summary returned by one deterministic generation run."""

    customers: list[Dict[str, str]]
    merchants: list[Dict[str, str]]
    transactions: list[Dict[str, str]]
    refunds: list[Dict[str, str]]
    ground_truth: list[Dict[str, str]]
    scenario_counts: Dict[str, int]
