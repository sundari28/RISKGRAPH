"""Deterministic factual signals; this module deliberately does not score risk."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Dict, Iterable, Optional, Sequence, Set, Tuple

from .schemas import ClusterSignals, InputDataset, SharedResource


PEAK_WINDOW = timedelta(hours=4)
SHORT_REFUND_DELAY = timedelta(hours=2)


def peak_window(transactions: Sequence[object]) -> tuple[tuple[str, ...], int]:
    """Return transaction IDs in the densest deterministic four-hour event window."""
    ordered = sorted(transactions, key=lambda transaction: (transaction.timestamp, transaction.transaction_id))
    best: tuple[object, ...] = ()
    left = 0
    for right, transaction in enumerate(ordered):
        while transaction.timestamp - ordered[left].timestamp > PEAK_WINDOW:
            left += 1
        window = tuple(ordered[left : right + 1])
        if len(window) > len(best) or (len(window) == len(best) and tuple(item.transaction_id for item in window) < tuple(item.transaction_id for item in best)):
            best = window
    return tuple(item.transaction_id for item in best), len({item.customer_id for item in best})


def build_cluster_signals(dataset: InputDataset, member_customer_ids: Sequence[str], shared_resources: Sequence[SharedResource]) -> tuple[ClusterSignals, tuple[str, ...]]:
    members = set(member_customer_ids)
    resource_transaction_ids = {transaction_id for resource in shared_resources for transaction_id in resource.transaction_ids}
    linked_transactions = [transaction for transaction in dataset.transactions.values() if transaction.transaction_id in resource_transaction_ids and transaction.customer_id in members]
    linked_transactions.sort(key=lambda transaction: transaction.transaction_id)
    peak_ids, peak_customers = peak_window(linked_transactions)
    by_type: Dict[str, int] = defaultdict(int)
    for resource in shared_resources:
        by_type[resource.resource_type] += 1
    refund_by_transaction = {refund.original_transaction_id: refund for refund in dataset.refunds.values()}
    linked_refunds = [refund_by_transaction[transaction.transaction_id] for transaction in linked_transactions if transaction.transaction_id in refund_by_transaction]
    short_delays = [int((refund.refund_timestamp - dataset.transactions[refund.original_transaction_id].timestamp).total_seconds() // 60) for refund in linked_refunds if refund.refund_timestamp - dataset.transactions[refund.original_transaction_id].timestamp <= SHORT_REFUND_DELAY]
    timestamps = [transaction.timestamp for transaction in linked_transactions]
    activity_span_days = int((max(timestamps) - min(timestamps)).total_seconds() // 86_400) if timestamps else 0
    signals = ClusterSignals(
        member_count=len(members),
        shared_device_count=by_type["device"],
        shared_ip_count=by_type["ip_address"],
        shared_billing_address_count=by_type["billing_address"],
        shared_shipping_address_count=by_type["shipping_address"],
        shared_identifier_type_count=len(by_type),
        linked_transaction_count=len(linked_transactions),
        peak_window_minutes=int(PEAK_WINDOW.total_seconds() // 60),
        peak_window_transaction_count=len(peak_ids),
        peak_window_customer_count=peak_customers,
        temporal_burst_present=len(peak_ids) >= max(8, len(members)) and peak_customers >= min(5, len(members)),
        merchant_fanout_count=len({transaction.merchant_id for transaction in linked_transactions}),
        refund_count=len(linked_refunds),
        refund_rate=round(len(linked_refunds) / len(linked_transactions), 4) if linked_transactions else 0.0,
        short_refund_count=len(short_delays),
        short_refund_delay_min_minutes=min(short_delays) if short_delays else None,
        short_refund_delay_max_minutes=max(short_delays) if short_delays else None,
        activity_span_days=activity_span_days,
    )
    return signals, peak_ids
