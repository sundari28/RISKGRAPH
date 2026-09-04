"""Build a deterministic evidence packet for AI investigation."""

from __future__ import annotations

from typing import Iterable

from .schemas import EvidenceItem, InvestigationRequest


def build_evidence_packet(
    case_id: str,
    analysis_run_id: str,
    risk_score: float,
    risk_band: str,
    policy_result: str,
    evidence: Iterable[EvidenceItem],
) -> InvestigationRequest:
    """Create a stable, structured evidence packet.

    The investigator receives only observable evidence supplied here.
    """

    ordered_evidence = tuple(
        sorted(
            evidence,
            key=lambda item: item.evidence_id,
        )
    )

    return InvestigationRequest(
        case_id=case_id,
        analysis_run_id=analysis_run_id,
        risk_score=float(risk_score),
        risk_band=risk_band,
        policy_result=policy_result,
        evidence=ordered_evidence,
    )


def validate_evidence_citations(
    response_citations: Iterable[str],
    evidence: Iterable[EvidenceItem],
) -> bool:
    """Return True only when every cited ID exists in the evidence packet."""

    valid_ids = {item.evidence_id for item in evidence}
    return all(citation in valid_ids for citation in response_citations)