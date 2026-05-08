from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from .engine_backend import account_type, gnc_numeric_to_decimal, seconds_to_date
from .ledger_reader import export_ledger


ASSET_TYPES = {"ASSET", "BANK", "CASH", "RECEIVABLE", "STOCK", "MUTUAL"}
LIABILITY_TYPES = {"LIABILITY", "CREDIT", "PAYABLE"}
INCOME_TYPES = {"INCOME"}
EXPENSE_TYPES = {"EXPENSE"}
EQUITY_TYPES = {"EQUITY"}
COGS_HINTS = ("cogs", "cost of goods", "cost of sales")
CURRENT_ASSET_HINTS = ("cash", "bank", "receivable", "inventory", "stock")
CURRENT_LIABILITY_HINTS = ("payable", "credit", "tax", "wages", "short")


def build_statements(book_uri: str, *, period: str = "month") -> dict:
    ledger = export_ledger(book_uri)
    return build_statements_from_ledger(ledger, period=period)


def build_statements_from_ledger(ledger: dict[str, Any], *, period: str = "month") -> dict:
    account_map = {acc["guid"]: acc for acc in ledger["accounts"]}
    transactions = sorted(ledger["transactions"], key=lambda txn: txn["date"])
    keys = sorted({period_key(txn["date"], period) for txn in transactions}) or ["all"]
    rows = {key: empty_row(key) for key in keys}
    cumulative = {key: defaultdict(float) for key in keys}
    previous_working_capital = 0.0

    for key in keys:
        for txn in transactions:
            txn_key = period_key(txn["date"], period)
            include_activity = period == "all" or txn_key == key
            include_balance = period == "all" or txn_key <= key
            for split in txn["splits"]:
                account = account_map.get(split["account_guid"], {})
                acc_type = split.get("account_type") or account.get("type", "")
                fullname = split.get("account") or account.get("fullname", "")
                value = float(split["value"])
                if include_activity:
                    apply_activity(rows[key], acc_type, fullname, value)
                if include_balance:
                    cumulative[key][acc_type] += value
                    if is_current_asset(acc_type, fullname):
                        cumulative[key]["current_assets"] += value
                    if is_current_liability(acc_type, fullname):
                        cumulative[key]["current_liabilities"] += value
                    if acc_type in ASSET_TYPES and "cash" in fullname.lower():
                        cumulative[key]["cash"] += value
        apply_balance(rows[key], cumulative[key])
        working_capital = rows[key]["current_assets"] - rows[key]["current_liabilities"]
        rows[key]["operating_cash_flow"] = round(rows[key]["net_income"] - (working_capital - previous_working_capital), 2)
        rows[key]["ending_cash"] = rows[key]["cash"]
        previous_working_capital = working_capital

    period_rows = [rows[key] for key in keys]
    return {
        "period_type": period,
        "periods": period_rows,
        "latest": period_rows[-1] if period_rows else empty_row("all"),
        "notes": [
            "Generated from official GnuCash engine objects.",
            "Cash flow is a simplified indirect approximation for agent analysis.",
        ],
    }


def period_key(value: str, period: str) -> str:
    if period == "all":
        return "all"
    parsed = datetime.fromisoformat(value).date()
    if period == "year":
        return str(parsed.year)
    if period == "quarter":
        return f"{parsed.year}-Q{((parsed.month - 1) // 3) + 1}"
    if period == "month":
        return f"{parsed.year}-{parsed.month:02d}"
    raise ValueError("period must be one of: month, quarter, year, all")


def empty_row(period: str) -> dict:
    return {
        "period": period,
        "revenue": 0.0,
        "cogs": 0.0,
        "gross_profit": 0.0,
        "operating_expenses": 0.0,
        "operating_income": 0.0,
        "net_income": 0.0,
        "cash": 0.0,
        "current_assets": 0.0,
        "total_assets": 0.0,
        "current_liabilities": 0.0,
        "total_liabilities": 0.0,
        "equity": 0.0,
        "operating_cash_flow": 0.0,
        "ending_cash": 0.0,
    }


def apply_activity(row: dict, acc_type: str, fullname: str, value: float) -> None:
    if acc_type in INCOME_TYPES:
        row["revenue"] += -value
    elif acc_type in EXPENSE_TYPES:
        if any(hint in fullname.lower() for hint in COGS_HINTS):
            row["cogs"] += value
        else:
            row["operating_expenses"] += value
    row["gross_profit"] = round(row["revenue"] - row["cogs"], 2)
    row["operating_income"] = round(row["gross_profit"] - row["operating_expenses"], 2)
    row["net_income"] = row["operating_income"]


def apply_balance(row: dict, balances: dict[str, float]) -> None:
    total_assets = sum(balances.get(kind, 0.0) for kind in ASSET_TYPES)
    total_liabilities = abs(sum(balances.get(kind, 0.0) for kind in LIABILITY_TYPES))
    total_equity = abs(sum(balances.get(kind, 0.0) for kind in EQUITY_TYPES))
    row["cash"] = round(balances.get("cash", 0.0), 2)
    row["current_assets"] = round(balances.get("current_assets", total_assets), 2)
    row["total_assets"] = round(total_assets, 2)
    row["current_liabilities"] = round(abs(balances.get("current_liabilities", total_liabilities)), 2)
    row["total_liabilities"] = round(total_liabilities, 2)
    row["equity"] = round(total_equity, 2)


def is_current_asset(acc_type: str, fullname: str) -> bool:
    return acc_type in ASSET_TYPES and any(hint in fullname.lower() for hint in CURRENT_ASSET_HINTS)


def is_current_liability(acc_type: str, fullname: str) -> bool:
    return acc_type in LIABILITY_TYPES and any(hint in fullname.lower() for hint in CURRENT_LIABILITY_HINTS)
