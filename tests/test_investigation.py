"""Tests for the M6 grounded investigator."""

import unittest

from app.investigation.evidence import (
    build_evidence_packet,
    validate_evidence_citations,
)
from app.investigation.investigator import investigate
from app.investigation.schemas import EvidenceItem


class InvestigationTests(unittest.TestCase):

    def setUp(self):
        self.evidence = (
            EvidenceItem(
                evidence_id="EV-001",
                category="shared_identifier",
                description="Two customers share the same device.",
                entity_ids=("C001", "C002"),
            ),
            EvidenceItem(
                evidence_id="EV-002",
                category="temporal_burst",
                description="Multiple customers transact within a short window.",
                entity_ids=("C001", "C002"),
                transaction_ids=("T001", "T002"),
            ),
        )

    def test_evidence_packet_is_deterministic(self):
        packet = build_evidence_packet(
            case_id="CASE-001",
            analysis_run_id="RUN-001",
            risk_score=82,
            risk_band="priority_review",
            policy_result="priority_review",
            evidence=reversed(self.evidence),
        )

        self.assertEqual(
            tuple(item.evidence_id for item in packet.evidence),
            ("EV-001", "EV-002"),
        )

    def test_valid_evidence_citations_are_accepted(self):
        self.assertTrue(
            validate_evidence_citations(
                ("EV-001", "EV-002"),
                self.evidence,
            )
        )

    def test_invented_evidence_citation_is_rejected(self):
        self.assertFalse(
            validate_evidence_citations(
                ("EV-001", "EV-999"),
                self.evidence,
            )
        )

    def test_investigator_uses_only_supplied_evidence(self):
        request = build_evidence_packet(
            case_id="CASE-001",
            analysis_run_id="RUN-001",
            risk_score=82,
            risk_band="priority_review",
            policy_result="priority_review",
            evidence=self.evidence,
        )

        result = investigate(request)

        self.assertEqual(
            result.cited_evidence_ids,
            ("EV-001", "EV-002"),
        )

    def test_coordination_evidence_requires_human_review(self):
        request = build_evidence_packet(
            case_id="CASE-002",
            analysis_run_id="RUN-001",
            risk_score=75,
            risk_band="priority_review",
            policy_result="priority_review",
            evidence=self.evidence,
        )

        result = investigate(request)

        self.assertEqual(result.recommendation, "human_review")
        self.assertIn(
            "not a fraud finding",
            " ".join(result.uncertainty),
        )

    def test_empty_evidence_falls_back_to_monitor_only(self):
        request = build_evidence_packet(
            case_id="CASE-003",
            analysis_run_id="RUN-001",
            risk_score=10,
            risk_band="monitor",
            policy_result="monitor_only",
            evidence=(),
        )

        result = investigate(request)

        self.assertEqual(result.recommendation, "monitor_only")
        self.assertEqual(result.cited_evidence_ids, ())


if __name__ == "__main__":
    unittest.main()