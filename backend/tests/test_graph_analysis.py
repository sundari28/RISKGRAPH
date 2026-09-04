"""M3 graph-analysis tests against the frozen M2 development/test datasets."""

import csv
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.graph_analysis.builder import build_full_graph, node_id
from app.graph_analysis.loader import load_input_dataset
from app.graph_analysis.pipeline import analyze_dataset


def load_ground_truth(split: str) -> dict[str, dict[str, str]]:
    """Test-only helper; production analysis never receives this mapping."""
    with (DATA_DIR / f"{split}_ground_truth.csv").open(newline="", encoding="utf-8") as handle:
        return {row["entity_id"]: row for row in csv.DictReader(handle)}


class GraphAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dev = analyze_dataset(DATA_DIR, "dev")
        cls.test = analyze_dataset(DATA_DIR, "test")
        cls.dev_truth = load_ground_truth("dev")

    def test_pipeline_is_deterministic(self) -> None:
        self.assertEqual(self.dev, analyze_dataset(DATA_DIR, "dev"))

    def test_pipeline_runs_without_any_ground_truth_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory)
            for name in ("customers", "merchants", "transactions", "refunds"):
                shutil.copy2(DATA_DIR / f"dev_{name}.csv", target / f"dev_{name}.csv")
            result = analyze_dataset(target, "dev")
        self.assertEqual(result.candidate_cluster_count, 10)

    def test_full_graph_contains_typed_refund_relationships(self) -> None:
        dataset = load_input_dataset(DATA_DIR, "dev")
        graph = build_full_graph(dataset)
        self.assertGreater(graph.number_of_nodes(), len(dataset.transactions))
        for refund in dataset.refunds.values():
            source = node_id("transaction", refund.original_transaction_id)
            target = node_id("refund", refund.refund_id)
            self.assertTrue(graph.has_edge(source, target, key="refunded_by"))
            self.assertEqual(graph.nodes[target]["node_type"], "refund")

    def test_analysis_outputs_do_not_contain_ground_truth_fields(self) -> None:
        dataset = load_input_dataset(DATA_DIR, "dev")
        graph = build_full_graph(dataset)
        forbidden = {"scenario", "cluster_id", "is_coordinated_abuse", "dataset_split", "generator_seed"}
        for _, attributes in graph.nodes(data=True):
            self.assertFalse(forbidden.intersection(attributes))
        for _, _, attributes in graph.edges(data=True):
            self.assertFalse(forbidden.intersection(attributes))
        self.assertTrue(all(not hasattr(cluster.signals, "risk_score") for cluster in self.dev.clusters))

    def test_dev_detects_five_coordinated_rings_without_merging_them(self) -> None:
        coordinated = [cluster for cluster in self.dev.clusters if cluster.classification == "coordinated_abuse_candidate"]
        self.assertEqual(len(coordinated), 5)
        expected_rings = {}
        for entity_id, label in self.dev_truth.items():
            if label["entity_type"] == "customer" and label["scenario"] == "COORDINATED_ABUSE_RING":
                expected_rings.setdefault(label["cluster_id"], set()).add(entity_id)
        self.assertEqual(len(expected_rings), 5)
        self.assertEqual({frozenset(cluster.member_customer_ids) for cluster in coordinated}, {frozenset(members) for members in expected_rings.values()})
        for cluster in coordinated:
            self.assertEqual(cluster.signals.member_count, 20)
            self.assertEqual(cluster.signals.shared_device_count, 2)
            self.assertEqual(cluster.signals.shared_ip_count, 2)
            self.assertEqual(cluster.signals.shared_billing_address_count, 2)
            self.assertTrue(cluster.signals.temporal_burst_present)
            self.assertGreaterEqual(cluster.signals.short_refund_count, 3)
            self.assertGreaterEqual(cluster.signals.merchant_fanout_count, 4)

    def test_benign_shared_infrastructure_is_not_classified_as_coordinated(self) -> None:
        benign = [cluster for cluster in self.dev.clusters if cluster.classification == "benign_shared_infrastructure_candidate"]
        self.assertEqual(len(benign), 5)
        for cluster in benign:
            self.assertEqual(cluster.signals.member_count, 10)
            self.assertEqual(cluster.signals.shared_device_count, 0)
            self.assertFalse(cluster.signals.temporal_burst_present)
            self.assertEqual(cluster.signals.short_refund_count, 0)
            self.assertGreaterEqual(cluster.signals.activity_span_days, 30)

    def test_legitimate_high_value_customers_are_not_candidate_members(self) -> None:
        high_value_ids = {
            entity_id for entity_id, label in self.dev_truth.items()
            if label["entity_type"] == "customer" and label["scenario"] == "LEGITIMATE_HIGH_VALUE"
        }
        analyses = {analysis.customer_id: analysis for analysis in self.dev.customers}
        self.assertTrue(high_value_ids)
        self.assertTrue(all(analyses[customer_id].candidate_cluster_id is None for customer_id in high_value_ids))

    def test_test_split_has_expected_candidate_shape(self) -> None:
        classifications = [cluster.classification for cluster in self.test.clusters]
        self.assertEqual(self.test.candidate_cluster_count, 10)
        self.assertEqual(classifications.count("coordinated_abuse_candidate"), 5)
        self.assertEqual(classifications.count("benign_shared_infrastructure_candidate"), 5)

    def test_transaction_outputs_reference_only_observable_evidence(self) -> None:
        outputs = {analysis.transaction_id: analysis for analysis in self.dev.transactions}
        self.assertEqual(len(outputs), 10_000)
        clustered = [analysis for analysis in outputs.values() if analysis.candidate_cluster_id]
        self.assertTrue(clustered)
        self.assertTrue(all(analysis.shared_resource_ids for analysis in clustered))


if __name__ == "__main__":
    unittest.main()
