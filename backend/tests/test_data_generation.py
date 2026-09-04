"""Tests for deterministic, separately labelled synthetic datasets."""

import csv
import sys
import tempfile
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.data_generation.generator import generate_dataset
from app.data_generation.schemas import (
    CUSTOMER_COLUMNS,
    GROUND_TRUTH_COLUMNS,
    MERCHANT_COLUMNS,
    REFUND_COLUMNS,
    TRANSACTION_COLUMNS,
)
from app.data_generation.scenarios import Scenario


class SyntheticDataGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dev = generate_dataset(seed=111, split="dev")
        cls.test = generate_dataset(seed=222, split="test")

    def test_same_seed_is_deterministic(self) -> None:
        again = generate_dataset(seed=111, split="dev")
        self.assertEqual(self.dev.customers, again.customers)
        self.assertEqual(self.dev.merchants, again.merchants)
        self.assertEqual(self.dev.transactions, again.transactions)
        self.assertEqual(self.dev.refunds, again.refunds)
        self.assertEqual(self.dev.ground_truth, again.ground_truth)

    def test_development_and_test_datasets_are_different(self) -> None:
        self.assertNotEqual(self.dev.transactions, self.test.transactions)
        self.assertTrue(self.dev.transactions[0]["transaction_id"].startswith("DEV_111_"))
        self.assertTrue(self.test.transactions[0]["transaction_id"].startswith("TEST_222_"))

    def test_required_columns_exist(self) -> None:
        self.assertEqual(list(self.dev.customers[0]), CUSTOMER_COLUMNS)
        self.assertEqual(list(self.dev.merchants[0]), MERCHANT_COLUMNS)
        self.assertEqual(list(self.dev.transactions[0]), TRANSACTION_COLUMNS)
        self.assertEqual(list(self.dev.refunds[0]), REFUND_COLUMNS)
        self.assertEqual(list(self.dev.ground_truth[0]), GROUND_TRUTH_COLUMNS)

    def test_refund_amounts_are_valid(self) -> None:
        for transaction in self.dev.transactions:
            amount = float(transaction["amount"])
            refund = float(transaction["refund_amount"])
            self.assertGreater(amount, 0)
            self.assertGreaterEqual(refund, 0)
            self.assertLessEqual(refund, amount)
            if transaction["refund_status"] == "NONE":
                self.assertEqual(refund, 0)

    def test_transaction_amounts_are_valid(self) -> None:
        self.assertEqual(len(self.dev.transactions), 10_000)
        self.assertEqual(len(self.test.transactions), 10_000)
        self.assertTrue(all(float(row["amount"]) > 0 for row in self.dev.transactions))

    def test_timestamps_are_valid(self) -> None:
        for transaction in self.dev.transactions:
            parsed = datetime.fromisoformat(transaction["timestamp"].replace("Z", "+00:00"))
            self.assertIsNotNone(parsed.tzinfo)

    def test_coordinated_abuse_has_shared_infrastructure(self) -> None:
        labels = {row["entity_id"]: row for row in self.dev.ground_truth if row["entity_type"] == "transaction"}
        ring_transactions = [
            row for row in self.dev.transactions
            if labels[row["transaction_id"]]["scenario"] == Scenario.COORDINATED_ABUSE_RING.value
        ]
        device_customers = {}
        ip_customers = {}
        address_customers = {}
        for row in ring_transactions:
            device_customers.setdefault(row["device_id"], set()).add(row["customer_id"])
            ip_customers.setdefault(row["ip_address"], set()).add(row["customer_id"])
            address_customers.setdefault(row["billing_address_id"], set()).add(row["customer_id"])
        self.assertTrue(any(len(customers) >= 10 for customers in device_customers.values()))
        self.assertTrue(any(len(customers) >= 10 for customers in ip_customers.values()))
        self.assertTrue(any(len(customers) >= 10 for customers in address_customers.values()))

    def test_ips_have_no_unintended_cross_scenario_overlap(self) -> None:
        labels = {row["entity_id"]: row for row in self.dev.ground_truth if row["entity_type"] == "transaction"}
        scenarios_by_ip = {}
        for row in self.dev.transactions:
            scenarios_by_ip.setdefault(row["ip_address"], set()).add(labels[row["transaction_id"]]["scenario"])
        self.assertTrue(all(len(scenarios) == 1 for scenarios in scenarios_by_ip.values()))

    def test_ips_have_no_cross_split_overlap(self) -> None:
        dev_ips = {row["ip_address"] for row in self.dev.transactions}
        test_ips = {row["ip_address"] for row in self.test.transactions}
        self.assertFalse(dev_ips.intersection(test_ips))

    def test_benign_groups_intentionally_share_ips_and_unique_devices(self) -> None:
        labels = {row["entity_id"]: row for row in self.dev.ground_truth if row["entity_type"] == "transaction"}
        benign = [
            row for row in self.dev.transactions
            if labels[row["transaction_id"]]["scenario"] == Scenario.BENIGN_SHARED_INFRASTRUCTURE.value
        ]
        ip_customers = {}
        device_customers = {}
        for row in benign:
            ip_customers.setdefault(row["ip_address"], set()).add(row["customer_id"])
            device_customers.setdefault(row["device_id"], set()).add(row["customer_id"])
        self.assertEqual(sorted(len(customers) for customers in ip_customers.values()), [10, 10, 10, 10, 10])
        self.assertTrue(all(len(customers) == 1 for customers in device_customers.values()))

    def test_merchant_topology_keeps_non_ring_scenarios_away_from_rings(self) -> None:
        labels = {row["entity_id"]: row for row in self.dev.ground_truth if row["entity_type"] == "transaction"}
        merchants_by_scenario = {}
        ring_merchants_by_cluster = {}
        for row in self.dev.transactions:
            label = labels[row["transaction_id"]]
            merchants_by_scenario.setdefault(label["scenario"], set()).add(row["merchant_id"])
            if label["scenario"] == Scenario.COORDINATED_ABUSE_RING.value:
                ring_merchants_by_cluster.setdefault(label["cluster_id"], set()).add(row["merchant_id"])
        ring_merchants = merchants_by_scenario[Scenario.COORDINATED_ABUSE_RING.value]
        for scenario, merchants in merchants_by_scenario.items():
            if scenario != Scenario.COORDINATED_ABUSE_RING.value:
                self.assertFalse(ring_merchants.intersection(merchants))
        self.assertEqual(len(ring_merchants_by_cluster), 5)
        self.assertTrue(all(len(merchants) >= 4 for merchants in ring_merchants_by_cluster.values()))
        clusters = sorted(ring_merchants_by_cluster)
        for index in range(len(clusters) - 1):
            self.assertEqual(
                len(ring_merchants_by_cluster[clusters[index]].intersection(ring_merchants_by_cluster[clusters[index + 1]])),
                1,
            )
        self.assertFalse(ring_merchants_by_cluster[clusters[0]].intersection(ring_merchants_by_cluster[clusters[-1]]))

    def test_legitimate_high_value_customers_exist(self) -> None:
        customer_labels = {row["entity_id"]: row for row in self.dev.ground_truth if row["entity_type"] == "customer"}
        high_value_customers = [
            row for row in self.dev.customers
            if customer_labels[row["customer_id"]]["scenario"] == Scenario.LEGITIMATE_HIGH_VALUE.value
        ]
        self.assertGreater(len(high_value_customers), 0)
        self.assertTrue(all(int(row["account_age_days"]) >= 800 for row in high_value_customers))
        self.assertTrue(all(float(row["historical_success_rate"]) >= 0.965 for row in high_value_customers))

    def test_benign_shared_infrastructure_exists(self) -> None:
        labels = {row["entity_id"]: row for row in self.dev.ground_truth if row["entity_type"] == "transaction"}
        benign = [
            row for row in self.dev.transactions
            if labels[row["transaction_id"]]["scenario"] == Scenario.BENIGN_SHARED_INFRASTRUCTURE.value
        ]
        ip_counts = Counter(row["ip_address"] for row in benign)
        self.assertTrue(any(count >= 10 for count in ip_counts.values()))

    def test_refunds_are_valid_events_after_successful_transactions(self) -> None:
        transactions = {row["transaction_id"]: row for row in self.dev.transactions}
        refunded_transaction_ids = {row["transaction_id"] for row in self.dev.transactions if row["refund_status"] == "COMPLETED"}
        self.assertGreater(len(self.dev.refunds), 0)
        self.assertEqual({row["original_transaction_id"] for row in self.dev.refunds}, refunded_transaction_ids)
        self.assertEqual(len({row["refund_id"] for row in self.dev.refunds}), len(self.dev.refunds))
        for refund in self.dev.refunds:
            original = transactions[refund["original_transaction_id"]]
            self.assertEqual(refund["refund_status"], "COMPLETED")
            self.assertEqual(original["payment_status"], "SUCCESS")
            self.assertLessEqual(float(refund["refund_amount"]), float(original["amount"]))
            refund_time = datetime.fromisoformat(refund["refund_timestamp"].replace("Z", "+00:00"))
            transaction_time = datetime.fromisoformat(original["timestamp"].replace("Z", "+00:00"))
            self.assertGreater(refund_time, transaction_time)

    def test_customer_references_are_valid(self) -> None:
        customer_ids = {row["customer_id"] for row in self.dev.customers}
        merchant_ids = {row["merchant_id"] for row in self.dev.merchants}
        self.assertTrue(all(row["customer_id"] in customer_ids for row in self.dev.transactions))
        self.assertTrue(all(row["merchant_id"] in merchant_ids for row in self.dev.transactions))

    def test_ground_truth_is_separate_from_model_input(self) -> None:
        forbidden = {"scenario", "cluster_id", "is_coordinated_abuse", "dataset_split", "generator_seed"}
        for model_columns in (CUSTOMER_COLUMNS, MERCHANT_COLUMNS, TRANSACTION_COLUMNS, REFUND_COLUMNS):
            self.assertFalse(forbidden.intersection(model_columns))
        self.assertTrue(forbidden.issubset(GROUND_TRUTH_COLUMNS))
        with tempfile.TemporaryDirectory() as temporary_directory:
            generate_dataset(333, "dev", Path(temporary_directory))
            for filename in ("dev_customers.csv", "dev_merchants.csv", "dev_transactions.csv", "dev_refunds.csv"):
                with (Path(temporary_directory) / filename).open(newline="", encoding="utf-8") as handle:
                    self.assertFalse(forbidden.intersection(csv.DictReader(handle).fieldnames or []))


if __name__ == "__main__":
    unittest.main()
