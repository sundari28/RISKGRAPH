"""Deterministic risk scoring for RISKGRAPH."""

from dataclasses import dataclass
from typing import Tuple

from app.graph_analysis.schemas import ClusterAnalysis


@dataclass(frozen=True)
class RiskAssessment:
    cluster_id: str
    score: float
    band: str
    components: Tuple[Tuple[str, float], ...]
    reasons: Tuple[str, ...]


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _normalise(value: float, maximum: float) -> float:
    if maximum <= 0:
        return 0.0
    return _clamp(value / maximum)


def calculate_risk_score(cluster: ClusterAnalysis) -> RiskAssessment:
    """Calculate an explainable 0-100 risk score from M3 observable signals."""

    signals = cluster.signals

    # 35% — strength of customer coordination.
    coordination = _normalise(
        signals.member_count * signals.shared_identifier_type_count,
        60,
    )

    # 20% — shared devices/IPs/addresses.
    shared_identifier = _normalise(
        signals.shared_device_count
        + signals.shared_ip_count
        + signals.shared_billing_address_count
        + signals.shared_shipping_address_count,
        8,
    )

    # 15% — concentrated multi-customer activity.
    burst = 1.0 if signals.temporal_burst_present else 0.0

    # 15% — short-delay refunds.
    refund_anomaly = _normalise(
        signals.short_refund_count,
        max(5, signals.refund_count),
    )

    # M3 does not yet provide a historical novelty baseline.
    behaviour_novelty = 0.0

    # Transaction value is intentionally not available at cluster level.
    # High-value transactions must not independently create a risk finding.
    transaction_value = 0.0

    # Strong legitimacy characteristics reduce risk.
    legitimacy = 0.0

    if (
        signals.member_count >= 5
        and signals.shared_device_count == 0
        and signals.temporal_burst_present is False
        and signals.short_refund_count == 0
    ):
        legitimacy = 1.0

    components = (
        ("coordination_strength", round(35 * coordination, 2)),
        ("shared_identifier_risk", round(20 * shared_identifier, 2)),
        ("temporal_burst_risk", round(15 * burst, 2)),
        ("refund_anomaly_risk", round(15 * refund_anomaly, 2)),
        ("behaviour_novelty_risk", round(10 * behaviour_novelty, 2)),
        ("transaction_value_context_risk", round(5 * transaction_value, 2)),
        ("established_legitimacy_offset", round(-20 * legitimacy, 2)),
    )

    score = _clamp(sum(value for _, value in components))

    if score >= 70:
        band = "priority_review"
    elif score >= 40:
        band = "investigate"
    else:
        band = "monitor"

    reasons = []

    if signals.member_count > 1:
        reasons.append(
            f"{signals.member_count} customers participate in the candidate cluster."
        )

    if signals.shared_identifier_type_count > 0:
        reasons.append(
            f"{signals.shared_identifier_type_count} types of shared identifiers connect customers."
        )

    if signals.temporal_burst_present:
        reasons.append(
            f"Concentrated activity was detected across "
            f"{signals.peak_window_customer_count} customers."
        )

    if signals.short_refund_count > 0:
        reasons.append(
            f"{signals.short_refund_count} refunds occurred with short refund timing."
        )

    if signals.merchant_fanout_count > 0:
        reasons.append(
            f"Activity spans {signals.merchant_fanout_count} distinct merchants."
        )

    if legitimacy:
        reasons.append(
            "Stable shared-infrastructure characteristics reduced the risk assessment."
        )

    if not reasons:
        reasons.append("No significant coordination evidence was detected.")

    return RiskAssessment(
        cluster_id=cluster.cluster_id,
        score=round(score, 2),
        band=band,
        components=components,
        reasons=tuple(reasons),
    )


def score_clusters(
    clusters: Tuple[ClusterAnalysis, ...],
) -> Tuple[RiskAssessment, ...]:
    """Score all detected clusters deterministically."""
    return tuple(calculate_risk_score(cluster) for cluster in clusters)