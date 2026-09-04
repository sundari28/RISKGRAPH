"""Generate deterministic, synthetic payment-risk datasets for RISKGRAPH.

Model-input CSVs deliberately contain no scenario, cluster, or abuse labels.
Those labels exist only in the accompanying ground-truth CSV.
"""

from __future__ import annotations

import csv
import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .scenarios import SCENARIO_PLANS, Scenario
from .schemas import (
    CUSTOMER_COLUMNS,
    GROUND_TRUTH_COLUMNS,
    MERCHANT_COLUMNS,
    REFUND_COLUMNS,
    TRANSACTION_COLUMNS,
    DatasetResult,
)


UTC = timezone.utc
REFERENCE_TIME = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
PAYMENT_METHODS = ("card", "upi", "net_banking", "wallet")
MERCHANT_CATEGORIES = ("retail", "travel", "electronics", "marketplace", "food", "digital")

# 198.18.0.0/15 is reserved for benchmarking. Each split receives a /16 and
# each scenario receives a distinct third-octet range within it. This gives IP
# address nodes stable, valid synthetic values with no cross-split overlap.
SPLIT_IP_PREFIX = {"dev": "198.18", "test": "198.19"}
SCENARIO_IP_BLOCK = {
    Scenario.NORMAL_CUSTOMER: 0,
    Scenario.LEGITIMATE_HIGH_VALUE: 10,
    Scenario.SUSPICIOUS_INDIVIDUAL: 20,
    Scenario.COORDINATED_ABUSE_RING: 30,
    Scenario.BENIGN_SHARED_INFRASTRUCTURE: 40,
}


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _money(value: float) -> str:
    return f"{max(0.0, value):.2f}"


def _allocate(total: int, recipients: List[str]) -> Dict[str, int]:
    """Allocate a total across recipients with deterministic base/remainder split."""
    base, remainder = divmod(total, len(recipients))
    return {recipient: base + (1 if index < remainder else 0) for index, recipient in enumerate(recipients)}


def _write_csv(path: Path, columns: List[str], rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class SyntheticDatasetGenerator:
    """One seeded generator with no external services or hidden global randomness."""

    def __init__(self, seed: int, split: str) -> None:
        if split not in {"dev", "test"}:
            raise ValueError("split must be 'dev' or 'test'")
        self.seed = seed
        self.split = split
        self.random = random.Random(seed)
        self.prefix = f"{split.upper()}_{seed}"
        self.customers: List[Dict[str, str]] = []
        self.merchants: List[Dict[str, str]] = []
        self.transactions: List[Dict[str, str]] = []
        self.refunds: List[Dict[str, str]] = []
        self.ground_truth: List[Dict[str, str]] = []
        self.scenario_counts: Counter[str] = Counter()
        self.merchant_pools = self._build_merchant_topology()

    def _id(self, kind: str, number: int) -> str:
        return f"{self.prefix}_{kind}_{number:05d}"

    def _ip(self, scenario: Scenario, index: int) -> str:
        """Return a deterministic, scenario- and split-isolated benchmark IP."""
        block, host = divmod(index - 1, 250)
        return f"{SPLIT_IP_PREFIX[self.split]}.{SCENARIO_IP_BLOCK[scenario] + block}.{host + 1}"

    def _create_merchant(self, sequence: int) -> str:
        merchant_id = self._id("M", sequence)
        self.merchants.append(
            {
                "merchant_id": merchant_id,
                "merchant_category": MERCHANT_CATEGORIES[(sequence - 1) % len(MERCHANT_CATEGORIES)],
            }
        )
        return merchant_id

    def _build_merchant_topology(self) -> Dict[str, List[str]]:
        """Create controlled pools without exposing scenario metadata in merchant rows.

        Normal, high-value, individual, and benign groups have disjoint pools.
        Rings receive four private merchants plus one or two bridge merchants
        shared only with adjacent rings, preserving limited realistic overlap.
        """
        sequence = 0

        def create_pool(size: int) -> List[str]:
            nonlocal sequence
            pool = []
            for _ in range(size):
                sequence += 1
                pool.append(self._create_merchant(sequence))
            return pool

        topology: Dict[str, List[str]] = {
            "normal": create_pool(12),
            "high_value": create_pool(6),
            "suspicious_individual": create_pool(5),
        }
        for group_index in range(1, 6):
            topology[f"benign_{group_index}"] = create_pool(3)
        bridges = create_pool(4)
        ring_private = [create_pool(4) for _ in range(5)]
        for ring_index in range(5):
            pool = list(ring_private[ring_index])
            if ring_index > 0:
                pool.append(bridges[ring_index - 1])
            if ring_index < 4:
                pool.append(bridges[ring_index])
            topology[f"ring_{ring_index + 1}"] = pool
        return topology

    def _ground_truth(
        self,
        entity_type: str,
        entity_id: str,
        scenario: Scenario,
        cluster_id: str = "",
        is_abuse: bool = False,
    ) -> None:
        self.ground_truth.append(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "scenario": scenario.value,
                "cluster_id": cluster_id,
                "is_coordinated_abuse": str(is_abuse).lower(),
                "dataset_split": self.split,
                "generator_seed": str(self.seed),
            }
        )

    def _new_customer(
        self,
        scenario: Scenario,
        index: int,
        *,
        cluster_id: str = "",
        is_abuse: bool = False,
    ) -> str:
        customer_id = self._id("C", index)
        if scenario is Scenario.LEGITIMATE_HIGH_VALUE:
            age_days = self.random.randint(800, 3_200)
            historical_transactions = self.random.randint(180, 1_500)
            historical_refunds = self.random.randint(0, max(1, historical_transactions // 80))
            success_rate = self.random.uniform(0.965, 0.998)
        elif scenario is Scenario.COORDINATED_ABUSE_RING:
            age_days = self.random.randint(8, 220)
            historical_transactions = self.random.randint(0, 35)
            historical_refunds = self.random.randint(0, 5)
            success_rate = self.random.uniform(0.72, 0.96)
        elif scenario is Scenario.SUSPICIOUS_INDIVIDUAL:
            age_days = self.random.randint(5, 420)
            historical_transactions = self.random.randint(0, 70)
            historical_refunds = self.random.randint(0, 12)
            success_rate = self.random.uniform(0.68, 0.95)
        else:
            age_days = self.random.randint(120, 2_500)
            historical_transactions = self.random.randint(15, 500)
            historical_refunds = self.random.randint(0, max(1, historical_transactions // 30))
            success_rate = self.random.uniform(0.88, 0.997)

        self.customers.append(
            {
                "customer_id": customer_id,
                "account_created_at": _iso(REFERENCE_TIME - timedelta(days=age_days)),
                "account_age_days": str(age_days),
                "historical_transaction_count": str(historical_transactions),
                "historical_refund_count": str(historical_refunds),
                "historical_success_rate": f"{success_rate:.4f}",
            }
        )
        self._ground_truth("customer", customer_id, scenario, cluster_id, is_abuse)
        return customer_id

    def _append_transaction(
        self,
        *,
        transaction_id: str,
        customer_id: str,
        scenario: Scenario,
        transaction_number: int,
        amount: float,
        timestamp: datetime,
        merchant_id: str,
        device_id: str,
        ip_address: str,
        billing_address_id: str,
        shipping_address_id: str,
        refund_probability: float,
        failed_probability: float,
        refund_delay_minutes: tuple[int, int],
        cluster_id: str = "",
        is_abuse: bool = False,
    ) -> None:
        payment_status = "FAILED" if self.random.random() < failed_probability else "SUCCESS"
        can_refund = payment_status == "SUCCESS" and self.random.random() < refund_probability
        refund_status = "COMPLETED" if can_refund else "NONE"
        refund_amount = amount * self.random.uniform(0.5, 1.0) if can_refund else 0.0
        record = {
            "transaction_id": transaction_id,
            "customer_id": customer_id,
            "merchant_id": merchant_id,
            "amount": _money(amount),
            "timestamp": _iso(timestamp),
            "payment_method": self.random.choice(PAYMENT_METHODS),
            "payment_status": payment_status,
            "device_id": device_id,
            "ip_address": ip_address,
            "billing_address_id": billing_address_id,
            "shipping_address_id": shipping_address_id,
            "refund_status": refund_status,
            "refund_amount": _money(refund_amount),
        }
        self.transactions.append(record)
        self._ground_truth("transaction", transaction_id, scenario, cluster_id, is_abuse)
        if can_refund:
            refund_id = self._id("R", len(self.refunds) + 1)
            refund_timestamp = timestamp + timedelta(minutes=self.random.randint(*refund_delay_minutes))
            self.refunds.append(
                {
                    "refund_id": refund_id,
                    "original_transaction_id": transaction_id,
                    "refund_timestamp": _iso(refund_timestamp),
                    "refund_amount": _money(refund_amount),
                    "refund_status": "COMPLETED",
                }
            )
            self._ground_truth("refund", refund_id, scenario, cluster_id, is_abuse)
        self.scenario_counts[scenario.value] += 1

    def _standard_transactions(
        self,
        scenario: Scenario,
        customers: List[str],
        total: int,
        transaction_offset: int,
        *,
        amount_range: tuple[float, float],
        refund_probability: float,
        failed_probability: float,
        refund_delay_minutes: tuple[int, int],
        stable_identity: bool,
        shared_ip: Optional[str] = None,
        shared_address: Optional[str] = None,
        merchant_pool: Optional[List[str]] = None,
    ) -> int:
        counts = _allocate(total, customers)
        number = transaction_offset
        for customer_index, customer_id in enumerate(customers, start=1):
            device_id = self._id("D", 10_000 + transaction_offset + customer_index)
            ip_address = shared_ip or self._ip(scenario, customer_index)
            address_id = shared_address or self._id("A", 10_000 + transaction_offset + customer_index)
            pool = merchant_pool or self.merchant_pools["normal"]
            preferred_merchants = self.random.sample(pool, min(len(pool), 2 if stable_identity else 5))
            for sequence in range(counts[customer_id]):
                number += 1
                if stable_identity or self.random.random() < 0.82:
                    used_device = device_id
                    used_ip = ip_address
                    used_address = address_id
                else:
                    used_device = self._id("D", 30_000 + number)
                    used_ip = self._ip(scenario, 1_000 + number)
                    used_address = self._id("A", 30_000 + number)
                timestamp = REFERENCE_TIME - timedelta(
                    days=self.random.randint(1, 365), minutes=self.random.randint(0, 1_439)
                )
                amount = self.random.uniform(*amount_range)
                merchant_id = self.random.choice(preferred_merchants)
                self._append_transaction(
                    transaction_id=self._id("T", number),
                    customer_id=customer_id,
                    scenario=scenario,
                    transaction_number=number,
                    amount=amount,
                    timestamp=timestamp,
                    merchant_id=merchant_id,
                    device_id=used_device,
                    ip_address=used_ip,
                    billing_address_id=used_address,
                    shipping_address_id=used_address if self.random.random() < 0.9 else self._id("A", 40_000 + number),
                    refund_probability=refund_probability,
                    failed_probability=failed_probability,
                    refund_delay_minutes=refund_delay_minutes,
                )
        return number

    def _coordinated_ring_transactions(self, customers: List[str], total: int, transaction_offset: int) -> int:
        counts = _allocate(total, customers)
        number = transaction_offset
        ring_size = 20
        for ring_index in range(5):
            ring_customers = customers[ring_index * ring_size : (ring_index + 1) * ring_size]
            cluster_id = f"{self.prefix}_RING_{ring_index + 1:02d}"
            shared_devices = [f"{cluster_id}_D_{number}" for number in range(1, 3)]
            shared_ips = [self._ip(Scenario.COORDINATED_ABUSE_RING, ring_index * 10 + number) for number in range(1, 3)]
            shared_addresses = [f"{cluster_id}_A_{number}" for number in range(1, 3)]
            merchant_pool = self.merchant_pools[f"ring_{ring_index + 1}"]
            burst_anchor = REFERENCE_TIME - timedelta(days=ring_index * 9 + self.random.randint(1, 4), hours=11)
            for customer_position, customer_id in enumerate(ring_customers):
                unique_device = self._id("D", 50_000 + ring_index * 100 + customer_position)
                unique_ip = self._ip(Scenario.COORDINATED_ABUSE_RING, 1_000 + ring_index * 100 + customer_position)
                unique_address = self._id("A", 50_000 + ring_index * 100 + customer_position)
                for sequence in range(counts[customer_id]):
                    number += 1
                    # Most but not all ring transactions share infrastructure. This
                    # preserves meaningful graph links without making every event obvious.
                    coordinated_event = self.random.random() < 0.68
                    if coordinated_event:
                        device_id = self.random.choice(shared_devices)
                        ip_address = self.random.choice(shared_ips)
                        address_id = self.random.choice(shared_addresses)
                        timestamp = burst_anchor + timedelta(minutes=self.random.randint(0, 240))
                        merchant_id = self.random.choice(merchant_pool)
                        refund_probability = 0.38
                        refund_delay_minutes = (5, 120)
                        amount = self.random.uniform(850, 7_500)
                    else:
                        device_id = unique_device
                        ip_address = unique_ip
                        address_id = unique_address
                        timestamp = REFERENCE_TIME - timedelta(days=self.random.randint(10, 280), minutes=self.random.randint(0, 1_439))
                        merchant_id = self.random.choice(merchant_pool)
                        refund_probability = 0.09
                        refund_delay_minutes = (24 * 60, 10 * 24 * 60)
                        amount = self.random.uniform(150, 2_400)
                    self._append_transaction(
                        transaction_id=self._id("T", number),
                        customer_id=customer_id,
                        scenario=Scenario.COORDINATED_ABUSE_RING,
                        transaction_number=number,
                        amount=amount,
                        timestamp=timestamp,
                        merchant_id=merchant_id,
                        device_id=device_id,
                        ip_address=ip_address,
                        billing_address_id=address_id,
                        shipping_address_id=address_id if self.random.random() < 0.7 else self._id("A", 60_000 + number),
                        refund_probability=refund_probability,
                        failed_probability=0.12,
                        refund_delay_minutes=refund_delay_minutes,
                        cluster_id=cluster_id,
                        is_abuse=True,
                    )
        return number

    def generate(self) -> DatasetResult:
        customer_number = 0
        transaction_number = 0
        scenario_customers: Dict[Scenario, List[str]] = {}
        for plan in SCENARIO_PLANS:
            customers = []
            for _ in range(plan.customer_count):
                customer_number += 1
                if plan.scenario is Scenario.COORDINATED_ABUSE_RING:
                    cluster_id = f"{self.prefix}_RING_{((len(customers)) // 20) + 1:02d}"
                    customer_id = self._new_customer(plan.scenario, customer_number, cluster_id=cluster_id, is_abuse=True)
                else:
                    customer_id = self._new_customer(plan.scenario, customer_number)
                customers.append(customer_id)
            scenario_customers[plan.scenario] = customers

        transaction_number = self._standard_transactions(
            Scenario.NORMAL_CUSTOMER, scenario_customers[Scenario.NORMAL_CUSTOMER], 5_000, transaction_number,
            amount_range=(90, 3_500), refund_probability=0.055, failed_probability=0.035,
            refund_delay_minutes=(3 * 24 * 60, 21 * 24 * 60), stable_identity=True,
            merchant_pool=self.merchant_pools["normal"],
        )
        transaction_number = self._standard_transactions(
            Scenario.LEGITIMATE_HIGH_VALUE, scenario_customers[Scenario.LEGITIMATE_HIGH_VALUE], 1_200, transaction_number,
            amount_range=(8_000, 85_000), refund_probability=0.025, failed_probability=0.012,
            refund_delay_minutes=(7 * 24 * 60, 45 * 24 * 60), stable_identity=True,
            merchant_pool=self.merchant_pools["high_value"],
        )
        transaction_number = self._standard_transactions(
            Scenario.SUSPICIOUS_INDIVIDUAL, scenario_customers[Scenario.SUSPICIOUS_INDIVIDUAL], 900, transaction_number,
            amount_range=(400, 12_000), refund_probability=0.22, failed_probability=0.18,
            refund_delay_minutes=(30, 3 * 24 * 60), stable_identity=False,
            merchant_pool=self.merchant_pools["suspicious_individual"],
        )
        transaction_number = self._coordinated_ring_transactions(
            scenario_customers[Scenario.COORDINATED_ABUSE_RING], 2_100, transaction_number
        )

        # Shared access is deliberately limited to each benign household/office
        # group and lacks ring-style burst/refund/merchant fan-out evidence.
        benign_customers = scenario_customers[Scenario.BENIGN_SHARED_INFRASTRUCTURE]
        groups = [benign_customers[index : index + 10] for index in range(0, len(benign_customers), 10)]
        benign_counts = _allocate(800, benign_customers)
        for group_index, group in enumerate(groups, start=1):
            group_total = sum(benign_counts[customer] for customer in group)
            transaction_number = self._standard_transactions(
                Scenario.BENIGN_SHARED_INFRASTRUCTURE,
                group,
                group_total,
                transaction_number,
                amount_range=(120, 5_500),
                refund_probability=0.045,
                failed_probability=0.03,
                refund_delay_minutes=(4 * 24 * 60, 30 * 24 * 60),
                stable_identity=True,
                shared_ip=self._ip(Scenario.BENIGN_SHARED_INFRASTRUCTURE, group_index),
                shared_address=f"{self.prefix}_BENIGN_A_{group_index:02d}",
                merchant_pool=self.merchant_pools[f"benign_{group_index}"],
            )

        if len(self.transactions) != 10_000:
            raise RuntimeError(f"expected 10000 transactions, got {len(self.transactions)}")
        return DatasetResult(
            customers=self.customers,
            merchants=self.merchants,
            transactions=self.transactions,
            refunds=self.refunds,
            ground_truth=self.ground_truth,
            scenario_counts=dict(sorted(self.scenario_counts.items())),
        )


def generate_dataset(seed: int, split: str, output_dir: Optional[Path] = None) -> DatasetResult:
    """Generate one split and optionally write its three CSV files."""
    result = SyntheticDatasetGenerator(seed=seed, split=split).generate()
    if output_dir is not None:
        output_dir = Path(output_dir)
        _write_csv(output_dir / f"{split}_customers.csv", CUSTOMER_COLUMNS, result.customers)
        _write_csv(output_dir / f"{split}_merchants.csv", MERCHANT_COLUMNS, result.merchants)
        _write_csv(output_dir / f"{split}_transactions.csv", TRANSACTION_COLUMNS, result.transactions)
        _write_csv(output_dir / f"{split}_refunds.csv", REFUND_COLUMNS, result.refunds)
        _write_csv(output_dir / f"{split}_ground_truth.csv", GROUND_TRUTH_COLUMNS, result.ground_truth)
    return result


def generate_default_datasets(output_dir: Optional[Path] = None, dev_seed: int = 20260830, test_seed: int = 20260831) -> Dict[str, DatasetResult]:
    """Generate independent dev and held-out test datasets with distinct seeds."""
    target = output_dir or Path(__file__).resolve().parents[3] / "data"
    return {
        "dev": generate_dataset(dev_seed, "dev", target),
        "test": generate_dataset(test_seed, "test", target),
    }


def _print_summary(name: str, result: DatasetResult) -> None:
    print(
        f"{name}: customers={len(result.customers)}, merchants={len(result.merchants)}, "
        f"transactions={len(result.transactions)}, refunds={len(result.refunds)}, "
        f"scenarios={len(result.scenario_counts)}"
    )
    print(f"  transaction scenarios: {result.scenario_counts}")


if __name__ == "__main__":
    results = generate_default_datasets()
    for dataset_name, dataset_result in results.items():
        _print_summary(dataset_name, dataset_result)
