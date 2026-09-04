"""Typed schemas for the RISKGRAPH AI Investigator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class EvidenceItem:
    """A single factual piece of evidence available to the investigator."""

    evidence_id: str
    category: str
    description: str
    entity_ids: Tuple[str, ...] = ()
    transaction_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class InvestigationRequest:
    """Structured evidence packet supplied to the investigator."""

    case_id: str
    analysis_run_id: str
    risk_score: float
    risk_band: str
    policy_result: str
    evidence: Tuple[EvidenceItem, ...]


@dataclass(frozen=True)
class InvestigationResponse:
    """Grounded explanation returned by the investigator."""

    summary: str
    observed_evidence: Tuple[str, ...]
    benign_alternatives: Tuple[str, ...]
    uncertainty: Tuple[str, ...]
    review_questions: Tuple[str, ...]
    recommendation: str
    cited_evidence_ids: Tuple[str, ...]