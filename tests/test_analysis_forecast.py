from __future__ import annotations

import json

from gnucash_cli.analysis import analyze_book
from gnucash_cli.forecast import forecast_book
from gnucash_cli.statements import build_statements


BOOK_URI = "postgres://user:pass@example.com:5432/gnucash"


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
