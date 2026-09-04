"""Create the customer-only association projection used for candidate discovery."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import DefaultDict, Dict, List, Tuple

import networkx as nx

from .schemas import InputDataset, SharedResource


RESOURCE_FIELDS = (
    ("device", "device_id"),
    ("ip_address", "ip_address"),
    ("billing_address", "billing_address_id"),
    ("shipping_address", "shipping_address_id"),
)


def build_customer_projection(dataset: InputDataset) -> tuple[nx.Graph, Dict[tuple[str, str], SharedResource]]:
    """Project only shared identity infrastructure; merchants never form edges here."""
    resource_events: DefaultDict[tuple[str, str], List[tuple[str, str]]] = defaultdict(list)
    for transaction in dataset.transactions.values():
        for resource_type, field in RESOURCE_FIELDS:
            resource_events[(resource_type, getattr(transaction, field))].append((transaction.customer_id, transaction.transaction_id))

    projection = nx.Graph(split=dataset.split, projection="shared_identity_infrastructure")
    shared_resources: Dict[tuple[str, str], SharedResource] = {}
    for resource_key in sorted(resource_events):
        events = resource_events[resource_key]
        customer_ids = tuple(sorted({customer_id for customer_id, _ in events}))
        if len(customer_ids) < 2:
            continue
        transaction_ids = tuple(sorted(transaction_id for _, transaction_id in events))
        resource = SharedResource(resource_key[0], resource_key[1], customer_ids, transaction_ids)
        shared_resources[resource_key] = resource
        for customer_id in customer_ids:
            projection.add_node(customer_id)
        for left, right in combinations(customer_ids, 2):
            if not projection.has_edge(left, right):
                projection.add_edge(left, right, shared_resources=[])
            projection.edges[left, right]["shared_resources"].append(resource_key)
    return projection, shared_resources
