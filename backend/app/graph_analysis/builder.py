"""Build the typed full investigation graph from validated model-input records."""

from __future__ import annotations

import networkx as nx

from .schemas import InputDataset


def node_id(node_type: str, identifier: str) -> str:
    return f"{node_type}:{identifier}"


def build_full_graph(dataset: InputDataset) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph(split=dataset.split)
    for customer in dataset.customers.values():
        graph.add_node(node_id("customer", customer.customer_id), node_type="customer", customer_id=customer.customer_id, account_age_days=customer.account_age_days, historical_transaction_count=customer.historical_transaction_count, historical_refund_count=customer.historical_refund_count, historical_success_rate=customer.historical_success_rate)
    for merchant in dataset.merchants.values():
        graph.add_node(node_id("merchant", merchant.merchant_id), node_type="merchant", merchant_id=merchant.merchant_id, merchant_category=merchant.merchant_category)
    for transaction in dataset.transactions.values():
        transaction_node = node_id("transaction", transaction.transaction_id)
        graph.add_node(transaction_node, node_type="transaction", transaction_id=transaction.transaction_id, amount=float(transaction.amount), timestamp=transaction.timestamp.isoformat(), payment_method=transaction.payment_method, payment_status=transaction.payment_status, refund_status=transaction.refund_status, refund_amount=float(transaction.refund_amount))
        graph.add_edge(node_id("customer", transaction.customer_id), transaction_node, key="made", relationship="made")
        graph.add_edge(transaction_node, node_id("merchant", transaction.merchant_id), key="paid_at", relationship="paid_at")
        for resource_type, resource_id, relationship in (("device", transaction.device_id, "used_device"), ("ip_address", transaction.ip_address, "originated_from"), ("address", transaction.billing_address_id, "billed_to"), ("address", transaction.shipping_address_id, "shipped_to")):
            resource_node = node_id(resource_type, resource_id)
            graph.add_node(resource_node, node_type=resource_type, resource_id=resource_id)
            graph.add_edge(transaction_node, resource_node, key=relationship, relationship=relationship)
    for refund in dataset.refunds.values():
        refund_node = node_id("refund", refund.refund_id)
        graph.add_node(refund_node, node_type="refund", refund_id=refund.refund_id, refund_timestamp=refund.refund_timestamp.isoformat(), refund_amount=float(refund.refund_amount), refund_status=refund.refund_status)
        graph.add_edge(node_id("transaction", refund.original_transaction_id), refund_node, key="refunded_by", relationship="refunded_by")
    return graph
