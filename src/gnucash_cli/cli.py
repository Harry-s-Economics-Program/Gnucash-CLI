from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from pydantic import ValidationError

from .analysis import analyze_book
from .forecast import forecast_book
from .ledger_ops import create_account, create_transaction
from .ledger_reader import export_ledger, inspect_book
from .models import AccountCreateRequest, CommandResponse, EvidenceItem, TransactionCreateRequest
from .statements import build_statements


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help(sys.stderr)
        return 2

    book_uri = getattr(args, "book_uri", None)
    try:
        payload = args.handler(args)
        response = CommandResponse(
            ok=True,
            command=args.command_path,
            book_uri=book_uri,
            result=payload,
            warnings=payload.get("warnings", []) if isinstance(payload, dict) else [],
            evidence=[
                EvidenceItem(
                    source="gnucash-official-engine",
                    detail=f"Command executed through official GnuCash Python bindings: {args.command_path}",
                    confidence=1.0,
                )
            ],
        )
        emit(response)
        return 0
    except Exception as exc:
        response = CommandResponse(
            ok=False,
            command=getattr(args, "command_path", "unknown"),
            book_uri=book_uri,
            result=None,
            error=str(exc),
        )
        emit(response)
        print(str(exc), file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hep-gnucash")
    subparsers = parser.add_subparsers(dest="command")

    inspect_parser = subparsers.add_parser("inspect")
    add_common(inspect_parser)
    set_handler(inspect_parser, "inspect", lambda args: inspect_book(args.book_uri))

    export_parser = subparsers.add_parser("export-ledger")
    add_common(export_parser)
    set_handler(export_parser, "export-ledger", lambda args: export_ledger(args.book_uri))

    statements_parser = subparsers.add_parser("statements")
    add_common(statements_parser)
    statements_parser.add_argument("--period", default="month", choices=["month", "quarter", "year", "all"])
    set_handler(statements_parser, "statements", lambda args: build_statements(args.book_uri, period=args.period))

    analyze_parser = subparsers.add_parser("analyze")
    add_common(analyze_parser)
    analyze_parser.add_argument("--period", default="month", choices=["month", "quarter", "year", "all"])
    analyze_parser.add_argument("--benchmark-file", default="")
    set_handler(
        analyze_parser,
        "analyze",
        lambda args: analyze_book(args.book_uri, benchmark_file=args.benchmark_file or None, period=args.period),
    )

    forecast_parser = subparsers.add_parser("forecast")
    add_common(forecast_parser)
    forecast_parser.add_argument("--period", default="month", choices=["month", "quarter", "year", "all"])
    forecast_parser.add_argument("--assumptions-file", default="")
    set_handler(
        forecast_parser,
        "forecast",
        lambda args: forecast_book(args.book_uri, assumptions_file=args.assumptions_file or None, period=args.period),
    )

    account_parser = subparsers.add_parser("account")
    account_subparsers = account_parser.add_subparsers(dest="account_command")
    account_create = account_subparsers.add_parser("create")
    add_common(account_create)
    account_create.add_argument("--name", required=True)
    account_create.add_argument("--type", required=True)
    account_create.add_argument("--parent", required=True)
    account_create.add_argument("--currency", default="")
    account_create.add_argument("--break-lock", action="store_true")
    set_handler(account_create, "account create", handle_account_create)

    transaction_parser = subparsers.add_parser("transaction")
    transaction_subparsers = transaction_parser.add_subparsers(dest="transaction_command")
    transaction_create = transaction_subparsers.add_parser("create")
    add_common(transaction_create)
    transaction_create.add_argument("--date", required=True)
    transaction_create.add_argument("--description", required=True)
    transaction_create.add_argument("--splits", required=True)
    transaction_create.add_argument("--num", default="")
    transaction_create.add_argument("--currency", default="")
    transaction_create.add_argument("--break-lock", action="store_true")
    set_handler(transaction_create, "transaction create", handle_transaction_create)

    return parser


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--book-uri", "--book", dest="book_uri", required=True)
    parser.add_argument("--json", action="store_true", help="Accepted for explicit agent usage; output is always JSON.")


def set_handler(parser: argparse.ArgumentParser, command_path: str, handler: Callable[[Any], dict]) -> None:
    parser.set_defaults(handler=handler, command_path=command_path)


def handle_account_create(args) -> dict:
    request = AccountCreateRequest(
        name=args.name,
        type=args.type.upper(),
        parent=args.parent,
        currency=args.currency or None,
    )
    return create_account(args.book_uri, request, break_lock=args.break_lock)


def handle_transaction_create(args) -> dict:
    try:
        split_payload = json.loads(args.splits)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--splits must be valid JSON: {exc}") from exc
    try:
        request = TransactionCreateRequest(
            date=args.date,
            description=args.description,
            splits=split_payload,
            num=args.num,
            currency=args.currency or None,
        )
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    return create_transaction(args.book_uri, request, break_lock=args.break_lock)


def emit(response: CommandResponse) -> None:
    print(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
