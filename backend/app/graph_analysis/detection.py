"""Candidate classification using transparent, non-scoring rules."""

from __future__ import annotations

from typing import Sequence, Tuple

from .schemas import ClusterSignals


def classify_candidate(signals: ClusterSignals) -> tuple[str, Tuple[str, ...]]:
    """Return an investigation state, never a fraud decision or risk score."""
    coordinated = (
        signals.member_count >= 3
        and signals.shared_identifier_type_count >= 2
        and signals.temporal_burst_present
        and signals.short_refund_count >= 3
        and signals.merchant_fanout_count >= 4
    )
    if coordinated:
        return (
            "coordinated_abuse_candidate",
            (
                "Multiple customers share independent identity identifiers.",
                "Linked transactions show concentrated multi-customer activity in a four-hour window.",
                "Linked transactions include short-delay completed refunds.",
                "Activity spans multiple merchants.",
            ),
        )
    benign = (
        signals.member_count >= 2
        and signals.shared_device_count == 0
        and not signals.temporal_burst_present
        and signals.short_refund_count == 0
        and signals.activity_span_days >= 30
    )
    if benign:
        return (
            "benign_shared_infrastructure_candidate",
            (
                "Customers share network or address infrastructure but not a device.",
                "Activity is distributed over time rather than concentrated in a burst.",
                "No linked refund occurs within the short-delay threshold.",
            ),
        )
    return (
        "insufficient_evidence",
        ("Shared infrastructure exists, but corroborating coordinated-abuse evidence is insufficient.",),
    )
