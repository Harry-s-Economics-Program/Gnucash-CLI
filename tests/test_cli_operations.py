from __future__ import annotations

import json

from gnucash_cli.cli import main
from gnucash_cli.ledger_reader import export_ledger
from tests import fake_gnucash


BOOK_URI = "postgres://user:pass@example.com:5432/gnucash"


def run_cli(capsys, args: list[str]) -> tuple[int, dict, str]:
    exit_code = main(args)
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out), captured.err


def test_inspect_returns_stable_json_contract(capsys):
    exit_code, payload, stderr = run_cli(capsys, ["inspect", "--book-uri", BOOK_URI, "--json"])

    assert exit_code == 0
    assert stderr == ""
    assert payload["ok"] is True
    assert payload["command"] == "inspect"
    assert payload["book_uri"] == BOOK_URI
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["evidence"], list)
    assert payload["error"] is None
    assert payload["result"]["metadata"]["account_count"] > 0


def test_account_create_persists_and_can_be_read_back(capsys):
    exit_code, payload, stderr = run_cli(
        capsys,
        [
            "account",
            "create",
            "--book-uri",
            BOOK_URI,
            "--json",
            "--name",
            "Platform Fees",
            "--type",
            "EXPENSE",
            "--parent",
            "Expenses",
        ],
    )

    assert exit_code == 0
    assert stderr == ""
    assert payload["ok"] is True
    assert payload["command"] == "account create"
    assert payload["result"]["created"]["fullname"] == "Expenses:Platform Fees"
    assert payload["result"]["mutation_log"]["operation"] == "account.create"
    assert any(event["event"] == "save" and event["uri"] == BOOK_URI for event in fake_gnucash.SESSION_EVENTS)

    ledger = export_ledger(BOOK_URI)
    assert any(account["fullname"] == "Expenses:Platform Fees" for account in ledger["accounts"])


def test_transaction_create_persists_and_can_be_read_back(capsys):
    exit_code, payload, stderr = run_cli(
        capsys,
        [
            "transaction",
            "create",
            "--book-uri",
            BOOK_URI,
            "--json",
            "--date",
            "2026-03-01",
            "--description",
            "March cash sale",
            "--splits",
            '[{"account":"Assets:Cash","value":1200},{"account":"Income:Sales","value":-1200}]',
        ],
    )

    assert exit_code == 0
    assert stderr == ""
    assert payload["ok"] is True
    assert payload["command"] == "transaction create"
    assert payload["result"]["created"]["description"] == "March cash sale"
    assert payload["result"]["mutation_log"]["split_total"] == "0"
    assert len(payload["result"]["created"]["splits"]) == 2
    assert any(event["event"] == "save" and event["uri"] == BOOK_URI for event in fake_gnucash.SESSION_EVENTS)

    ledger = export_ledger(BOOK_URI)
    assert any(transaction["description"] == "March cash sale" for transaction in ledger["transactions"])


def test_transaction_create_rejects_unbalanced_splits(capsys):
    exit_code, payload, stderr = run_cli(
        capsys,
        [
            "transaction",
            "create",
            "--book-uri",
            BOOK_URI,
            "--json",
            "--date",
            "2026-03-01",
            "--description",
            "Bad sale",
            "--splits",
            '[{"account":"Assets:Cash","value":10},{"account":"Income:Sales","value":-9}]',
        ],
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["command"] == "transaction create"
    assert "not balanced" in payload["error"]
    assert "not balanced" in stderr
    assert not any(transaction["description"] == "Bad sale" for transaction in export_ledger(BOOK_URI)["transactions"])


def test_account_create_reports_missing_parent_as_structured_error(capsys):
    exit_code, payload, stderr = run_cli(
        capsys,
        [
            "account",
            "create",
            "--book-uri",
            BOOK_URI,
            "--json",
            "--name",
            "Impossible",
            "--type",
            "EXPENSE",
            "--parent",
            "No Such Parent",
        ],
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["command"] == "account create"
    assert "Account not found" in payload["error"]
    assert "Account not found" in stderr


def test_transaction_create_reports_invalid_json_splits(capsys):
    exit_code, payload, stderr = run_cli(
        capsys,
        [
            "transaction",
            "create",
            "--book-uri",
            BOOK_URI,
            "--json",
            "--date",
            "2026-03-01",
            "--description",
            "Malformed",
            "--splits",
            "not-json",
        ],
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert "--splits must be valid JSON" in payload["error"]
    assert "--splits must be valid JSON" in stderr


def test_break_lock_flag_uses_break_lock_session_mode(capsys):
    exit_code, payload, stderr = run_cli(
        capsys,
        [
            "account",
            "create",
            "--book-uri",
            BOOK_URI,
            "--json",
            "--break-lock",
            "--name",
            "Break Lock Expense",
            "--type",
            "EXPENSE",
            "--parent",
            "Expenses",
        ],
    )

    assert exit_code == 0
    assert stderr == ""
    assert payload["ok"] is True
    assert any(
        event["event"] == "open" and event["mode"] == fake_gnucash.SessionOpenMode.SESSION_BREAK_LOCK
        for event in fake_gnucash.SESSION_EVENTS
    )
