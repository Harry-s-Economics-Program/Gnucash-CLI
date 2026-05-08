from __future__ import annotations

import json

from gnucash_cli.analysis import analyze_book
from gnucash_cli.cli import main
from gnucash_cli.forecast import forecast_book
from gnucash_cli.ledger_ops import create_account, create_transaction
from gnucash_cli.ledger_reader import export_ledger, inspect_book
from gnucash_cli.models import AccountCreateRequest, TransactionCreateRequest
from gnucash_cli.statements import build_statements


BOOK_URI = "postgres://user:pass@example.com:5432/gnucash"


def test_inspect_and_export_use_engine_objects():
    inspected = inspect_book(BOOK_URI)
    exported = export_ledger(BOOK_URI)
    assert inspected["metadata"]["account_count"] > 0
    assert exported["transactions"]


def test_statements_and_analysis_run_without_llm(tmp_path):
    statements = build_statements(BOOK_URI, period="month")
    assert statements["latest"]["revenue"] == 56000
    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text(
        json.dumps({"industry": "retail", "metrics": {"gross_margin": {"median": 0.36}}}),
        encoding="utf-8",
    )
    result = analyze_book(BOOK_URI, benchmark_file=str(benchmark), period="month")
    assert "gross_margin" in result["ratios"]
    assert result["benchmark"]["comparisons"]


def test_forecast_links_statements(tmp_path):
    assumptions = tmp_path / "assumptions.json"
    assumptions.write_text(json.dumps({"periods": 2, "revenue_growth": 0.05, "gross_margin": 0.45}), encoding="utf-8")
    result = forecast_book(BOOK_URI, assumptions_file=str(assumptions))
    assert result["checks"]["linked"] is True
    assert len(result["forecast"]) == 2


def test_account_create_uses_official_engine_lifecycle():
    result = create_account(BOOK_URI, AccountCreateRequest(name="Platform Fees", type="EXPENSE", parent="Expenses"))
    assert result["created"]["fullname"] == "Expenses:Platform Fees"
    assert result["mutation_log"]["direct_engine_write"] is True


def test_transaction_create_rejects_unbalanced():
    request = TransactionCreateRequest(
        date="2026-03-01",
        description="Bad",
        splits=[
            {"account": "Assets:Cash", "value": 10},
            {"account": "Income:Sales", "value": -9},
        ],
    )
    try:
        create_transaction(BOOK_URI, request)
    except ValueError as exc:
        assert "not balanced" in str(exc)
    else:
        raise AssertionError("expected unbalanced transaction to fail")


def test_cli_returns_json(capsys):
    exit_code = main(["inspect", "--book-uri", BOOK_URI, "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["book_uri"] == BOOK_URI
