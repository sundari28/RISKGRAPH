"""Public M3 pipeline for deterministic graph construction and candidate analysis."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

import networkx as nx

from .builder import build_full_graph, node_id
from .detection import classify_candidate
from .loader import load_input_dataset
from .projection import build_customer_projection
from .schemas import ClusterAnalysis, CustomerAnalysis, GraphAnalysisResult, InputDataset, SharedResource, TransactionAnalysis
from .signals import build_cluster_signals


def _cluster_subgraph_nodes(full_graph: nx.MultiDiGraph, members: Set[str], transaction_ids: Set[str], refund_ids: Set[str], resources: Sequence[SharedResource]) -> Tuple[str, ...]:
    nodes = {node_id("customer", customer_id) for customer_id in members}
    nodes.update(node_id("transaction", transaction_id) for transaction_id in transaction_ids)
    nodes.update(node_id("refund", refund_id) for refund_id in refund_ids)
    for resource in resources:
        resource_node_type = "address" if resource.resource_type in {"billing_address", "shipping_address"} else resource.resource_type
        nodes.add(node_id(resource_node_type, resource.resource_id))
    for transaction_id in transaction_ids:
        transaction_node = node_id("transaction", transaction_id)
        for _, target, edge_data in full_graph.out_edges(transaction_node, data=True):
            if edge_data["relationship"] == "paid_at":
                nodes.add(target)
    return tuple(sorted(nodes))


def analyze_dataset(data_dir: Path, split: str) -> GraphAnalysisResult:
    """Analyze a frozen model-input split without loading labels or assigning scores."""
    dataset = load_input_dataset(Path(data_dir), split)
    full_graph = build_full_graph(dataset)
    projection, shared_resource_index = build_customer_projection(dataset)
    components = [tuple(sorted(component)) for component in nx.connected_components(projection) if len(component) >= 2]
    components.sort(key=lambda component: component[0])

    clusters: List[ClusterAnalysis] = []
    customer_cluster: Dict[str, str] = {}
    transaction_cluster: Dict[str, str] = {}
    transaction_resources: Dict[str, Set[str]] = defaultdict(set)
    transaction_peak: Set[str] = set()
    for index, component in enumerate(components, start=1):
        members = set(component)
        resources = tuple(resource for resource in shared_resource_index.values() if set(resource.customer_ids).issubset(members))
        resources = tuple(sorted(resources, key=lambda resource: (resource.resource_type, resource.resource_id)))
        signals, peak_ids = build_cluster_signals(dataset, component, resources)
        classification, reasons = classify_candidate(signals)
        cluster_id = f"{split}_candidate_{index:03d}"
        transaction_ids = tuple(sorted({transaction_id for resource in resources for transaction_id in resource.transaction_ids}))
        refund_ids = tuple(sorted(refund.refund_id for refund in dataset.refunds.values() if refund.original_transaction_id in transaction_ids))
        for customer_id in component:
            customer_cluster[customer_id] = cluster_id
        for resource in resources:
            resource_label = f"{resource.resource_type}:{resource.resource_id}"
            for transaction_id in resource.transaction_ids:
                transaction_cluster[transaction_id] = cluster_id
                transaction_resources[transaction_id].add(resource_label)
        transaction_peak.update(peak_ids)
        clusters.append(ClusterAnalysis(cluster_id, component, transaction_ids, refund_ids, resources, signals, classification, reasons, _cluster_subgraph_nodes(full_graph, members, set(transaction_ids), set(refund_ids), resources)))

    transactions_by_customer: Dict[str, List[object]] = defaultdict(list)
    refund_by_transaction = {refund.original_transaction_id: refund.refund_id for refund in dataset.refunds.values()}
    for transaction in dataset.transactions.values():
        transactions_by_customer[transaction.customer_id].append(transaction)
    customers = []
    for customer_id in sorted(dataset.customers):
        customer = dataset.customers[customer_id]
        events = transactions_by_customer[customer_id]
        customers.append(CustomerAnalysis(customer_id, customer_cluster.get(customer_id), len(events), len({event.device_id for event in events}), len({event.ip_address for event in events}), len({event.billing_address_id for event in events}), len({event.shipping_address_id for event in events}), customer.account_age_days, customer.historical_transaction_count, customer.historical_refund_count, customer.historical_success_rate))
    transactions = tuple(TransactionAnalysis(transaction_id, transaction_cluster.get(transaction_id), tuple(sorted(transaction_resources[transaction_id])), transaction_id in transaction_peak, refund_by_transaction.get(transaction_id)) for transaction_id in sorted(dataset.transactions))
    return GraphAnalysisResult(split, full_graph.number_of_nodes(), full_graph.number_of_edges(), len(clusters), tuple(clusters), tuple(customers), transactions)
