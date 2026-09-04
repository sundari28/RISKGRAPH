import unittest

from app.policy.policy import PolicyInput, evaluate_policy


class PolicyTests(unittest.TestCase):

    def test_high_risk_coordinated_case_goes_to_priority_review(self):
        result = evaluate_policy(
            PolicyInput(
                risk_score=85,
                classification="coordinated_abuse_candidate",
                shared_identifier_types=2,
                temporal_burst_present=True,
                short_refund_count=5,
                behaviour_novelty_present=False,
                established_legitimacy=False,
            )
        )

        self.assertEqual(result.routing, "priority_review")
        self.assertEqual(result.priority, "high")

    def test_shared_ip_alone_does_not_trigger_priority_review(self):
        result = evaluate_policy(
            PolicyInput(
                risk_score=85,
                classification="coordinated_abuse_candidate",
                shared_identifier_types=1,
                temporal_burst_present=False,
                short_refund_count=0,
                behaviour_novelty_present=False,
                established_legitimacy=False,
            )
        )

        self.assertNotEqual(result.routing, "priority_review")

    def test_legitimate_customer_is_monitor_only(self):
        result = evaluate_policy(
            PolicyInput(
                risk_score=80,
                classification="coordinated_abuse_candidate",
                shared_identifier_types=2,
                temporal_burst_present=True,
                short_refund_count=4,
                behaviour_novelty_present=True,
                established_legitimacy=True,
            )
        )

        self.assertEqual(result.routing, "monitor_only")
        self.assertEqual(result.priority, "low")

    def test_benign_shared_infrastructure_is_monitor_only(self):
        result = evaluate_policy(
            PolicyInput(
                risk_score=60,
                classification="benign_shared_infrastructure_candidate",
                shared_identifier_types=1,
                temporal_burst_present=False,
                short_refund_count=0,
                behaviour_novelty_present=False,
                established_legitimacy=False,
            )
        )

        self.assertEqual(result.routing, "monitor_only")
        self.assertEqual(result.priority, "low")

    def test_coordinated_candidate_with_some_evidence_goes_to_investigation(self):
        result = evaluate_policy(
            PolicyInput(
                risk_score=55,
                classification="coordinated_abuse_candidate",
                shared_identifier_types=1,
                temporal_burst_present=True,
                short_refund_count=0,
                behaviour_novelty_present=False,
                established_legitimacy=False,
            )
        )

        self.assertEqual(result.routing, "investigate")
        self.assertEqual(result.priority, "medium")

    def test_unknown_or_insufficient_case_is_monitor_only(self):
        result = evaluate_policy(
            PolicyInput(
                risk_score=20,
                classification="insufficient_evidence",
                shared_identifier_types=0,
                temporal_burst_present=False,
                short_refund_count=0,
                behaviour_novelty_present=False,
                established_legitimacy=False,
            )
        )

        self.assertEqual(result.routing, "monitor_only")
        self.assertEqual(result.priority, "low")

    def test_policy_has_version(self):
        result = evaluate_policy(
            PolicyInput(
                risk_score=50,
                classification="insufficient_evidence",
                shared_identifier_types=0,
                temporal_burst_present=False,
                short_refund_count=0,
                behaviour_novelty_present=False,
                established_legitimacy=False,
            )
        )

        self.assertEqual(result.ruleset_version, "m5-v1")


if __name__ == "__main__":
    unittest.main()