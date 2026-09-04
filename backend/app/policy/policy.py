"""Deterministic policy and guardrails for RISKGRAPH."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class PolicyInput:
    """Observable inputs required for a policy decision."""

    risk_score: float
    classification: str
    shared_identifier_types: int
    temporal_burst_present: bool
    short_refund_count: int
    behaviour_novelty_present: bool
    established_legitimacy: bool


@dataclass(frozen=True)
class PolicyResult:
    """Deterministic routing result; never a fraud verdict."""

    routing: str
    priority: str
    reasons: Tuple[str, ...]
    ruleset_version: str = "m5-v1"


def evaluate_policy(policy_input: PolicyInput) -> PolicyResult:
    """
    Apply deterministic review guardrails.

    Possible routing values:
    - priority_review
    - investigate
    - monitor_only

    The policy never blocks, refunds, restricts, or declares fraud.
    """

    reasons: list[str] = []

        # Established legitimate behaviour always prevents priority routing.
    if policy_input.established_legitimacy:
        return PolicyResult(
            routing="monitor_only",
            priority="low",
            reasons=("established legitimate behaviour requires additional evidence",),
        )

    # High value alone can never create a priority case.
    if (
        policy_input.risk_score >= 70
        and policy_input.classification == "coordinated_abuse_candidate"
    ):
        evidence_categories = 0

        if policy_input.shared_identifier_types > 0:
            evidence_categories += 1
            reasons.append("shared infrastructure evidence")

        if policy_input.temporal_burst_present:
            evidence_categories += 1
            reasons.append("concentrated multi-customer activity")

        if policy_input.short_refund_count > 0:
            evidence_categories += 1
            reasons.append("short-delay refund evidence")

        if policy_input.behaviour_novelty_present:
            evidence_categories += 1
            reasons.append("behavioural novelty evidence")

        # Priority review requires at least two independent categories.
        if evidence_categories >= 2:
            return PolicyResult(
                routing="priority_review",
                priority="high",
                reasons=tuple(reasons),
            )

    # Established legitimate behaviour prevents automatic priority routing.
    if policy_input.established_legitimacy:
        return PolicyResult(
            routing="monitor_only",
            priority="low",
            reasons=("established legitimate behaviour requires additional evidence",),
        )

    # Coordinated candidates with some evidence go to investigation.
    if policy_input.classification == "coordinated_abuse_candidate":
        return PolicyResult(
            routing="investigate",
            priority="medium",
            reasons=("coordinated-abuse evidence requires human investigation",),
        )

    # Benign shared infrastructure stays monitor-only.
    if policy_input.classification == "benign_shared_infrastructure_candidate":
        return PolicyResult(
            routing="monitor_only",
            priority="low",
            reasons=("shared infrastructure has benign behavioural context",),
        )

    return PolicyResult(
        routing="monitor_only",
        priority="low",
        reasons=("insufficient evidence for elevated review",),
    ) 