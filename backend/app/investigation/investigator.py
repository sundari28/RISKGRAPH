"""Grounded investigator with deterministic fallback."""

from __future__ import annotations

from .schemas import InvestigationRequest, InvestigationResponse


def investigate(request: InvestigationRequest) -> InvestigationResponse:
    """Generate a grounded explanation using only supplied evidence.

    This MVP implementation is deterministic and requires no AI credentials.
    """

    evidence = request.evidence

    if not evidence:
        return InvestigationResponse(
            summary="Insufficient evidence is available for investigation.",
            observed_evidence=(),
            benign_alternatives=(
                "No structured evidence was supplied for this case.",
            ),
            uncertainty=(
                "The available evidence is insufficient to determine coordination.",
            ),
            review_questions=(
                "What additional customer, transaction, or relationship evidence is available?",
            ),
            recommendation="monitor_only",
            cited_evidence_ids=(),
        )

    cited_ids = tuple(item.evidence_id for item in evidence)

    observed = tuple(
        f"[{item.category}] {item.description}"
        for item in evidence
    )

    has_coordination = any(
        item.category in {
            "coordination",
            "shared_identifier",
            "temporal_burst",
            "refund_anomaly",
            "merchant_fanout",
        }
        for item in evidence
    )

    if has_coordination:
        summary = (
            f"Case {request.case_id} shows observable evidence consistent "
            "with coordinated activity and should be reviewed by a human."
        )
        recommendation = "human_review"
    else:
        summary = (
            f"Case {request.case_id} does not contain sufficient coordination "
            "evidence for escalation."
        )
        recommendation = "monitor_only"

    benign_alternatives = (
        "Shared infrastructure can have legitimate explanations such as "
        "family, office, or shared-network usage.",
    )

    uncertainty = (
        "This explanation is based only on the supplied structured evidence.",
        "It is a risk assessment and not a fraud finding.",
    )

    review_questions = (
        "Are the shared identifiers plausibly explained by legitimate shared infrastructure?",
        "Did multiple customers act within the same short time window?",
        "Are refund and merchant patterns consistent with the observed coordination?",
    )

    return InvestigationResponse(
        summary=summary,
        observed_evidence=observed,
        benign_alternatives=benign_alternatives,
        uncertainty=uncertainty,
        review_questions=review_questions,
        recommendation=recommendation,
        cited_evidence_ids=cited_ids,
    )