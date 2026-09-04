"""Typed records and outputs for the M3 graph-analysis pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Mapping, Optional, Tuple


@dataclass(frozen=True)
class CustomerRecord:
    customer_id: str
    account_created_at: datetime
    account_age_days: int
    historical_transaction_count: int
    historical_refund_count: int
    historical_success_rate: float


@dataclass(frozen=True)
class MerchantRecord:
    merchant_id: str
    merchant_category: str


@dataclass(frozen=True)
class TransactionRecord:
    transaction_id: str
    customer_id: str
    merchant_id: str
    amount: Decimal
    timestamp: datetime
    payment_method: str
    payment_status: str
    device_id: str
    ip_address: str
    billing_address_id: str
    shipping_address_id: str
    refund_status: str
    refund_amount: Decimal


@dataclass(frozen=True)
class RefundRecord:
    refund_id: str
    original_transaction_id: str
    refund_timestamp: datetime
    refund_amount: Decimal
    refund_status: str


@dataclass(frozen=True)
class InputDataset:
    split: str
    customers: Mapping[str, CustomerRecord]
    merchants: Mapping[str, MerchantRecord]
    transactions: Mapping[str, TransactionRecord]
    refunds: Mapping[str, RefundRecord]


@dataclass(frozen=True)
class SharedResource:
    resource_type: str
    resource_id: str
    customer_ids: Tuple[str, ...]
    transaction_ids: Tuple[str, ...]


@dataclass(frozen=True)
class ClusterSignals:
    member_count: int
    shared_device_count: int
    shared_ip_count: int
    shared_billing_address_count: int
    shared_shipping_address_count: int
    shared_identifier_type_count: int
    linked_transaction_count: int
    peak_window_minutes: int
    peak_window_transaction_count: int
    peak_window_customer_count: int
    temporal_burst_present: bool
    merchant_fanout_count: int
    refund_count: int
    refund_rate: float
    short_refund_count: int
    short_refund_delay_min_minutes: Optional[int]
    short_refund_delay_max_minutes: Optional[int]
    activity_span_days: int


@dataclass(frozen=True)
class ClusterAnalysis:
    cluster_id: str
    member_customer_ids: Tuple[str, ...]
    transaction_ids: Tuple[str, ...]
    refund_ids: Tuple[str, ...]
    shared_resources: Tuple[SharedResource, ...]
    signals: ClusterSignals
    classification: str
    reasons: Tuple[str, ...]
    subgraph_node_ids: Tuple[str, ...]


@dataclass(frozen=True)
class CustomerAnalysis:
    customer_id: str
    candidate_cluster_id: Optional[str]
    transaction_count: int
    in_window_device_count: int
    in_window_ip_count: int
    in_window_billing_address_count: int
    in_window_shipping_address_count: int
    account_age_days: int
    historical_transaction_count: int
    historical_refund_count: int
    historical_success_rate: float


@dataclass(frozen=True)
class TransactionAnalysis:
    transaction_id: str
    candidate_cluster_id: Optional[str]
    shared_resource_ids: Tuple[str, ...]
    participates_in_peak_window: bool
    refund_id: Optional[str]


@dataclass(frozen=True)
class GraphAnalysisResult:
    split: str
    full_graph_node_count: int
    full_graph_edge_count: int
    candidate_cluster_count: int
    clusters: Tuple[ClusterAnalysis, ...]
    customers: Tuple[CustomerAnalysis, ...]
    transactions: Tuple[TransactionAnalysis, ...]
