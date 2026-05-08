from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .analysis import calculate_ratios
from .models import ForecastAssumptions
from .statements import build_statements


def forecast_book(book_uri: str, *, assumptions_file: str | None = None, period: str = "month") -> dict:
    base_statements = build_statements(book_uri, period=period)
    assumptions = load_assumptions(assumptions_file)
    rows = project_three_statements(base_statements["latest"], assumptions)
    return {
        "base_period": base_statements["latest"]["period"],
        "assumptions": assumptions.model_dump(),
        "forecast": rows,
        "checks": validate_forecast(rows),
        "notes": ["Forecast is deterministic and runs without an LLM."],
    }


def load_assumptions(path: str | None) -> ForecastAssumptions:
    if not path:
        return ForecastAssumptions()
    try:
        return ForecastAssumptions.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Assumptions file not found: {path}") from exc
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Invalid assumptions file: {exc}") from exc


def project_three_statements(base: dict, assumptions: ForecastAssumptions) -> list[dict]:
    ratios = calculate_ratios(base)
    gross_margin = assumptions.gross_margin
    if gross_margin is None:
        gross_margin = ratios.get("gross_margin") if ratios.get("gross_margin") is not None else 0.4

    revenue = float(base.get("revenue") or 0.0)
    opex = float(base.get("operating_expenses") or 0.0)
    cash = float(base.get("ending_cash") or base.get("cash") or 0.0)
    total_liabilities = float(base.get("total_liabilities") or 0.0)
    equity = float(base.get("equity") or 0.0)
    previous_working_capital = float(base.get("current_assets") or 0.0) - float(base.get("current_liabilities") or 0.0)

    rows = []
    for index in range(1, assumptions.periods + 1):
        revenue *= 1 + assumptions.revenue_growth
        cogs = revenue * (1 - gross_margin)
        gross_profit = revenue - cogs
        opex *= 1 + assumptions.opex_growth
        operating_income = gross_profit - opex
        taxes = max(operating_income, 0.0) * assumptions.tax_rate
        net_income = operating_income - taxes
        working_capital = revenue * assumptions.working_capital_percent_revenue
        operating_cash_flow = net_income - (working_capital - previous_working_capital)
        financing_cash_flow = assumptions.debt_change + assumptions.owner_injections
        cash = cash + operating_cash_flow - assumptions.capex + financing_cash_flow
        total_liabilities = max(total_liabilities + assumptions.debt_change, 0.0)
        equity = max(equity + net_income + assumptions.owner_injections, 0.0)
        total_assets = total_liabilities + equity
        row = {
            "period": f"forecast_{index}",
            "revenue": round(revenue, 2),
            "cogs": round(cogs, 2),
            "gross_profit": round(gross_profit, 2),
            "operating_expenses": round(opex, 2),
            "operating_income": round(operating_income, 2),
            "taxes": round(taxes, 2),
            "net_income": round(net_income, 2),
            "working_capital": round(working_capital, 2),
            "operating_cash_flow": round(operating_cash_flow, 2),
            "capex": round(assumptions.capex, 2),
            "financing_cash_flow": round(financing_cash_flow, 2),
            "ending_cash": round(cash, 2),
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2),
            "equity": round(equity, 2),
        }
        row["balance_gap"] = round(row["total_assets"] - row["total_liabilities"] - row["equity"], 2)
        rows.append(row)
        previous_working_capital = working_capital
    return rows


def validate_forecast(rows: list[dict]) -> dict:
    max_gap = max((abs(row["balance_gap"]) for row in rows), default=0.0)
    return {
        "period_count": len(rows),
        "max_balance_gap": round(max_gap, 2),
        "linked": max_gap < 0.01,
    }
