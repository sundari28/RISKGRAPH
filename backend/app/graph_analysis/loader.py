"""Load only model-input CSVs; ground-truth files are intentionally excluded."""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List

from .schemas import CustomerRecord, InputDataset, MerchantRecord, RefundRecord, TransactionRecord


REQUIRED_COLUMNS = {
    "customers": {"customer_id", "account_created_at", "account_age_days", "historical_transaction_count", "historical_refund_count", "historical_success_rate"},
    "merchants": {"merchant_id", "merchant_category"},
    "transactions": {"transaction_id", "customer_id", "merchant_id", "amount", "timestamp", "payment_method", "payment_status", "device_id", "ip_address", "billing_address_id", "shipping_address_id", "refund_status", "refund_amount"},
    "refunds": {"refund_id", "original_transaction_id", "refund_timestamp", "refund_amount", "refund_status"},
}


def _parse_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"invalid {field}: {value!r}") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone: {value!r}")
    return parsed


def _parse_decimal(value: str, field: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"invalid {field}: {value!r}") from error
    if parsed < 0:
        raise ValueError(f"{field} cannot be negative: {value!r}")
    return parsed


def _read_rows(path: Path, kind: str) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing {kind} input: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS[kind] - columns
        if missing:
            raise ValueError(f"{path.name} is missing required columns: {sorted(missing)}")
        return list(reader)


def _index_unique(records: Iterable[object], attribute: str, kind: str) -> Dict[str, object]:
    indexed: Dict[str, object] = {}
    for record in records:
        identifier = getattr(record, attribute)
        if identifier in indexed:
            raise ValueError(f"duplicate {kind} ID: {identifier}")
        indexed[identifier] = record
    return indexed


def load_input_dataset(data_dir: Path, split: str) -> InputDataset:
    """Load one split from customers, merchants, transactions, and refunds only."""
    if split not in {"dev", "test"}:
        raise ValueError("split must be 'dev' or 'test'")
    data_dir = Path(data_dir)
    customer_rows = _read_rows(data_dir / f"{split}_customers.csv", "customers")
    merchant_rows = _read_rows(data_dir / f"{split}_merchants.csv", "merchants")
    transaction_rows = _read_rows(data_dir / f"{split}_transactions.csv", "transactions")
    refund_rows = _read_rows(data_dir / f"{split}_refunds.csv", "refunds")

    customers = _index_unique(
        [CustomerRecord(row["customer_id"], _parse_timestamp(row["account_created_at"], "account_created_at"), int(row["account_age_days"]), int(row["historical_transaction_count"]), int(row["historical_refund_count"]), float(row["historical_success_rate"])) for row in customer_rows],
        "customer_id", "customer",
    )
    merchants = _index_unique(
        [MerchantRecord(row["merchant_id"], row["merchant_category"]) for row in merchant_rows], "merchant_id", "merchant"
    )
    transactions = _index_unique(
        [TransactionRecord(row["transaction_id"], row["customer_id"], row["merchant_id"], _parse_decimal(row["amount"], "amount"), _parse_timestamp(row["timestamp"], "timestamp"), row["payment_method"], row["payment_status"], row["device_id"], row["ip_address"], row["billing_address_id"], row["shipping_address_id"], row["refund_status"], _parse_decimal(row["refund_amount"], "refund_amount")) for row in transaction_rows],
        "transaction_id", "transaction",
    )
    refunds = _index_unique(
        [RefundRecord(row["refund_id"], row["original_transaction_id"], _parse_timestamp(row["refund_timestamp"], "refund_timestamp"), _parse_decimal(row["refund_amount"], "refund_amount"), row["refund_status"]) for row in refund_rows],
        "refund_id", "refund",
    )

    for transaction in transactions.values():
        if transaction.customer_id not in customers:
            raise ValueError(f"transaction {transaction.transaction_id} references unknown customer")
        if transaction.merchant_id not in merchants:
            raise ValueError(f"transaction {transaction.transaction_id} references unknown merchant")
        if transaction.amount <= 0 or transaction.refund_amount > transaction.amount:
            raise ValueError(f"transaction {transaction.transaction_id} has invalid amounts")
    for refund in refunds.values():
        original = transactions.get(refund.original_transaction_id)
        if original is None:
            raise ValueError(f"refund {refund.refund_id} references unknown transaction")
        if original.payment_status != "SUCCESS" or refund.refund_timestamp <= original.timestamp:
            raise ValueError(f"refund {refund.refund_id} has invalid source transaction or timing")
        if refund.refund_amount > original.amount:
            raise ValueError(f"refund {refund.refund_id} exceeds original transaction amount")
    return InputDataset(split, customers, merchants, transactions, refunds)
