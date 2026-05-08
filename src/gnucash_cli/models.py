from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


AccountType = Literal[
    "ASSET",
    "BANK",
    "CASH",
    "RECEIVABLE",
    "STOCK",
    "MUTUAL",
    "LIABILITY",
    "CREDIT",
    "PAYABLE",
    "INCOME",
    "EXPENSE",
    "EQUITY",
    "TRADING",
]


class EvidenceItem(BaseModel):
    source: str
    detail: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class CommandResponse(BaseModel):
    ok: bool
    command: str
    book_uri: str | None
    result: dict[str, Any] | list[Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    error: str | None = None


class AccountCreateRequest(BaseModel):
    name: str
    type: AccountType
    parent: str
    currency: str | None = None

    @field_validator("name", "parent")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class SplitInput(BaseModel):
    account: str
    value: Decimal
    memo: str = ""
    quantity: Decimal | None = None

    @field_validator("account")
    @classmethod
    def account_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("account must not be blank")
        return value.strip()


class TransactionCreateRequest(BaseModel):
    date: date
    description: str
    splits: list[SplitInput]
    num: str = ""
    currency: str | None = None

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("description must not be blank")
        return value.strip()

    @field_validator("splits")
    @classmethod
    def at_least_two_splits(cls, value: list[SplitInput]) -> list[SplitInput]:
        if len(value) < 2:
            raise ValueError("transaction requires at least two splits")
        return value


class ForecastAssumptions(BaseModel):
    periods: int = Field(default=3, ge=1, le=60)
    revenue_growth: float = 0.0
    gross_margin: float | None = Field(default=None, ge=-1.0, le=1.0)
    opex_growth: float = 0.0
    capex: float = 0.0
    working_capital_percent_revenue: float = 0.0
    debt_change: float = 0.0
    tax_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    owner_injections: float = 0.0


class BenchmarkBand(BaseModel):
    low: float | None = None
    median: float
    high: float | None = None


class BenchmarkFile(BaseModel):
    industry: str
    currency: str | None = None
    metrics: dict[str, BenchmarkBand]
