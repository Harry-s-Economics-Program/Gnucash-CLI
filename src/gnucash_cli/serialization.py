from __future__ import annotations

from typing import Any

from .engine_backend import (
    account_commodity,
    account_fullname,
    account_guid,
    account_name,
    account_type,
    attr_or_call,
    call_any,
    commodity_mnemonic,
    gnc_numeric_to_decimal,
    guid_to_string,
    seconds_to_date,
)


def serialize_account(account: Any) -> dict:
    parent = attr_or_call(account, ["get_parent", "GetParent"], None)
    return {
        "guid": account_guid(account),
        "name": account_name(account),
        "fullname": account_fullname(account),
        "type": account_type(account),
        "parent": account_fullname(parent) if parent else None,
        "currency": commodity_mnemonic(account_commodity(account)),
        "placeholder": bool(attr_or_call(account, ["GetPlaceholder", "get_placeholder"], False)),
    }


def serialize_split(split: Any) -> dict:
    account = call_any(split, ["GetAccount", "get_account"])
    value = gnc_numeric_to_decimal(call_any(split, ["GetValue", "GetAmount", "get_value"]))
    quantity = gnc_numeric_to_decimal(call_any(split, ["GetAmount", "GetValue", "get_amount"], default=value))
    return {
        "guid": guid_to_string(call_any(split, ["GetGUID", "get_guid"], default="")),
        "account": account_fullname(account),
        "account_guid": account_guid(account),
        "account_type": account_type(account),
        "value": float(value),
        "quantity": float(quantity),
        "memo": attr_or_call(split, ["GetMemo", "get_memo"], ""),
    }


def serialize_transaction(transaction: Any) -> dict:
    currency = attr_or_call(transaction, ["GetCurrency", "get_currency"], None)
    splits = list(call_any(transaction, ["GetSplitList", "get_split_list"], default=[]))
    return {
        "guid": guid_to_string(call_any(transaction, ["GetGUID", "get_guid"], default="")),
        "date": seconds_to_date(call_any(transaction, ["GetDate", "RetDatePosted", "get_date"], default="")),
        "description": attr_or_call(transaction, ["GetDescription", "get_description"], ""),
        "num": attr_or_call(transaction, ["GetNum", "get_num"], ""),
        "currency": commodity_mnemonic(currency),
        "splits": [serialize_split(split) for split in splits],
    }
