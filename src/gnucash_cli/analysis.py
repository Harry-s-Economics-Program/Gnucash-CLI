from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import BenchmarkFile
from .statements import build_statements


def analyze_book(book_uri: str, *, benchmark_file: str | None = None, period: str = "month") -> dict:
    statements = build_statements(book_uri, period=period)
    latest = statements["latest"]
    ratios = calculate_ratios(latest)
    benchmark = compare_benchmark(ratios, benchmark_file) if benchmark_file else None
    return {
        "statements": statements,
        "ratios": {k: v for k, v in ratios.items() if v is not None},
        "benchmark": benchmark,
        "anomalies": detect_anomalies(ratios, benchmark),
        "data_quality": {
            "warnings": data_quality_warnings(latest, ratios),
            "ratio_count": len([v for v in ratios.values() if v is not None]),
        },
    }


def calculate_ratios(row: dict[str, Any]) -> dict[str, float | None]:
    def safe(num: float, den: float) -> float | None:
        return None if den == 0 else round(num / den, 4)

    revenue = float(row.get("revenue") or 0.0)
    return {
        "gross_margin": safe(float(row.get("gross_profit") or 0.0), revenue),
        "net_margin": safe(float(row.get("net_income") or 0.0), revenue),
        "current_ratio": safe(float(row.get("current_assets") or 0.0), float(row.get("current_liabilities") or 0.0)),
        "debt_to_equity": safe(float(row.get("total_liabilities") or 0.0), float(row.get("equity") or 0.0)),
        "opex_to_revenue": safe(float(row.get("operating_expenses") or 0.0), revenue),
    }


def load_benchmark(path: str | Path) -> BenchmarkFile:
    try:
        return BenchmarkFile.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Benchmark file not found: {path}") from exc
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Invalid benchmark file: {exc}") from exc


def compare_benchmark(ratios: dict[str, float | None], benchmark_file: str) -> dict:
    benchmark = load_benchmark(benchmark_file)
    comparisons = []
    missing = []
    for metric, band in benchmark.metrics.items():
        value = ratios.get(metric)
        if value is None:
            missing.append(metric)
            continue
        position = "near_median"
        if band.low is not None and value < band.low:
            position = "below_low"
        elif band.high is not None and value > band.high:
            position = "above_high"
        elif value < band.median:
            position = "below_median"
        elif value > band.median:
            position = "above_median"
        comparisons.append(
            {
                "metric": metric,
                "value": value,
                "median": band.median,
                "low": band.low,
                "high": band.high,
                "position": position,
                "delta_to_median": round(value - band.median, 4),
            }
        )
    return {
        "industry": benchmark.industry,
        "currency": benchmark.currency,
        "comparisons": comparisons,
        "missing_metrics": missing,
    }


def data_quality_warnings(row: dict[str, Any], ratios: dict[str, float | None]) -> list[str]:
    warnings = []
    if not row.get("revenue"):
        warnings.append("No revenue found in latest period.")
    if ratios.get("current_ratio") is None:
        warnings.append("Current ratio could not be computed.")
    if ratios.get("debt_to_equity") is None:
        warnings.append("Debt-to-equity could not be computed.")
    return warnings


def detect_anomalies(ratios: dict[str, float | None], benchmark: dict | None) -> list[dict]:
    anomalies = []
    if ratios.get("net_margin") is not None and ratios["net_margin"] < 0:
        anomalies.append({"severity": "high", "metric": "net_margin", "message": "Business is loss-making."})
    if ratios.get("current_ratio") is not None and ratios["current_ratio"] < 1:
        anomalies.append({"severity": "high", "metric": "current_ratio", "message": "Current assets do not cover current liabilities."})
    if benchmark:
        for comparison in benchmark.get("comparisons", []):
            if comparison["position"] in {"below_low", "above_high"}:
                anomalies.append({"severity": "medium", "metric": comparison["metric"], "message": "Metric is outside benchmark band."})
    return anomalies
