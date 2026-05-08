from __future__ import annotations

from decimal import Decimal

from .engine_backend import (
    EngineModules,
    call_any,
    date_to_seconds,
    decimal_to_gnc_numeric,
    find_account,
    get_book,
    lookup_currency,
    open_session,
)
from .models import AccountCreateRequest, TransactionCreateRequest
from .serialization import serialize_account, serialize_transaction


def create_account(book_uri: str, request: AccountCreateRequest, *, break_lock: bool = False) -> dict:
    modules = EngineModules.load()
    with open_session(book_uri, readonly=False, break_lock=break_lock) as session:
        book = get_book(session)
        parent = find_account(book, request.parent)
        currency = lookup_currency(book, request.currency, fallback_account=parent)
        account = modules.gnucash.Account(book)
        call_any(account, ["BeginEdit", "begin_edit"], default=None)
        call_any(account, ["SetName", "set_name"], request.name)
        call_any(account, ["SetType", "set_type"], account_type_constant(modules, request.type))
        call_any(account, ["SetCommodity", "set_commodity"], currency)
        call_any(parent, ["append_child", "AppendChild"], account)
        call_any(account, ["CommitEdit", "commit_edit"], default=None)
        return {
            "created": serialize_account(account),
            "mutation_log": {
                "operation": "account.create",
                "parent": request.parent,
                "direct_engine_write": True,
                "backup": "not_applicable_for_postgresql_backend",
            },
        }


def create_transaction(book_uri: str, request: TransactionCreateRequest, *, break_lock: bool = False) -> dict:
    total = sum((split.value for split in request.splits), Decimal("0"))
    if total != Decimal("0"):
        raise ValueError(f"Transaction is not balanced; split total is {total}")

    modules = EngineModules.load()
    with open_session(book_uri, readonly=False, break_lock=break_lock) as session:
        book = get_book(session)
        first_account = find_account(book, request.splits[0].account)
        currency = lookup_currency(book, request.currency, fallback_account=first_account)
        transaction = modules.gnucash.Transaction(book)
        call_any(transaction, ["BeginEdit", "begin_edit"])
        call_any(transaction, ["SetCurrency", "set_currency"], currency)
        call_any(transaction, ["SetDescription", "set_description"], request.description)
        call_any(transaction, ["SetDatePostedSecs", "SetDate", "set_date"], date_to_seconds(request.date))
        if request.num:
            call_any(transaction, ["SetNum", "set_num"], request.num)

        created_splits = []
        for split_request in request.splits:
            account = find_account(book, split_request.account)
            split = modules.gnucash.Split(book)
            numeric_value = decimal_to_gnc_numeric(split_request.value)
            numeric_quantity = decimal_to_gnc_numeric(split_request.quantity or split_request.value)
            call_any(transaction, ["AppendSplit", "append_split"], split)
            call_any(account, ["InsertSplit", "insert_split"], split, default=None)
            call_any(split, ["SetAccount", "set_account"], account)
            call_any(split, ["SetValue", "set_value"], numeric_value)
            call_any(split, ["SetAmount", "set_amount"], numeric_quantity)
            if split_request.memo:
                call_any(split, ["SetMemo", "set_memo"], split_request.memo)
            created_splits.append(split)

        imbalance = call_any(transaction, ["GetImbalance", "get_imbalance"], default=[])
        if imbalance:
            raise ValueError(f"GnuCash engine reports transaction imbalance: {imbalance}")
        call_any(transaction, ["CommitEdit", "commit_edit"])
        return {
            "created": serialize_transaction(transaction),
            "mutation_log": {
                "operation": "transaction.create",
                "direct_engine_write": True,
                "split_count": len(created_splits),
                "split_total": str(total),
                "backup": "not_applicable_for_postgresql_backend",
            },
        }


def account_type_constant(modules: EngineModules, account_type: str):
    name = f"ACCT_TYPE_{account_type}"
    for scope in (modules.gnucash, modules.core):
        if hasattr(scope, name):
            return getattr(scope, name)
    return account_type
