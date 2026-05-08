from __future__ import annotations

from typing import Any

from .engine_backend import account_descendants, account_guid, call_any, get_book, get_root_account, open_session
from .serialization import serialize_account, serialize_transaction


def inspect_book(book_uri: str) -> dict:
    with open_session(book_uri, readonly=True) as session:
        book = get_book(session)
        root = get_root_account(book)
        accounts = [serialize_account(account) for account in account_descendants(root)]
        transactions = list(iter_transactions(root))
        return {
            "metadata": {
                "account_count": len(accounts),
                "transaction_count": len(transactions),
            },
            "accounts": accounts,
            "currencies": sorted({acc["currency"] for acc in accounts if acc.get("currency")}),
            "data_quality": {
                "has_income_accounts": any(acc["type"] == "INCOME" for acc in accounts),
                "has_expense_accounts": any(acc["type"] == "EXPENSE" for acc in accounts),
                "has_asset_accounts": any(acc["type"] in {"ASSET", "BANK", "CASH", "RECEIVABLE"} for acc in accounts),
            },
        }


def export_ledger(book_uri: str) -> dict:
    with open_session(book_uri, readonly=True) as session:
        book = get_book(session)
        root = get_root_account(book)
        return {
            "accounts": [serialize_account(account) for account in account_descendants(root)],
            "transactions": [serialize_transaction(txn) for txn in iter_transactions(root)],
        }


def iter_transactions(root: Any):
    seen = set()
    for account in account_descendants(root):
        for split in list(call_any(account, ["GetSplitList", "get_split_list"], default=[])):
            transaction = call_any(split, ["GetParent", "get_parent"])
            guid = str(call_any(transaction, ["GetGUID", "get_guid"], default=id(transaction)))
            if guid in seen:
                continue
            seen.add(guid)
            yield transaction


def account_index(book_uri: str) -> dict[str, str]:
    with open_session(book_uri, readonly=True) as session:
        root = get_root_account(get_book(session))
        return {account_guid(account): serialize_account(account)["fullname"] for account in account_descendants(root)}
