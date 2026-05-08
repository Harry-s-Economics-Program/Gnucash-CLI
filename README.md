# Gnucash-CLI

[![CI](https://github.com/Harry-s-Economics-Program/Gnucash-CLI/actions/workflows/ci.yml/badge.svg)](https://github.com/Harry-s-Economics-Program/Gnucash-CLI/actions/workflows/ci.yml)
[![Release](https://github.com/Harry-s-Economics-Program/Gnucash-CLI/actions/workflows/release.yml/badge.svg)](https://github.com/Harry-s-Economics-Program/Gnucash-CLI/actions/workflows/release.yml)
[![PyPI](https://img.shields.io/pypi/v/hep-gnucash-cli.svg)](https://pypi.org/project/hep-gnucash-cli/)
[![Python](https://img.shields.io/pypi/pyversions/hep-gnucash-cli.svg)](https://pypi.org/project/hep-gnucash-cli/)

`Gnucash-CLI` is the HEP command-line runtime for operating GnuCash books through the **official GnuCash engine**, not by directly editing SQL tables.

The intended production path is:

```text
AI Agent
  -> JSON CLI
  -> GnuCash official Python bindings
  -> libgnucash engine / QOF Session
  -> GnuCash PostgreSQL backend
```

No `piecash` and no SQLAlchemy are used.

## Requirements

You need a Python environment where GnuCash official Python bindings are importable:

```python
import gnucash
from gnucash import Session, SessionOpenMode
```

On Linux this is commonly provided by a package like `python3-gnucash`, or by building GnuCash with:

```bash
cmake -DWITH_PYTHON=ON ...
```

GnuCash's own docs warn that GnuCash is effectively single-writer; do not run this CLI while the GUI is editing the same book.

## Install

From PyPI:

```bash
pipx install hep-gnucash-cli
```

For development:

```bash
python -m pip install -e ".[dev]"
```

## Usage

Use a GnuCash URI. For PostgreSQL, pass the URI that your GnuCash build accepts for its SQL backend:

```bash
hep-gnucash inspect --book-uri "$GNUCASH_BOOK_URI" --json
hep-gnucash export-ledger --book-uri "$GNUCASH_BOOK_URI" --json
hep-gnucash statements --book-uri "$GNUCASH_BOOK_URI" --json --period month
hep-gnucash analyze --book-uri "$GNUCASH_BOOK_URI" --json --benchmark-file benchmarks/retail.json
hep-gnucash forecast --book-uri "$GNUCASH_BOOK_URI" --json --assumptions-file examples/forecast_assumptions.json
```

Write commands use official engine object creation/edit/commit:

```bash
hep-gnucash account create --book-uri "$GNUCASH_BOOK_URI" --json \
  --name "Platform Fees" --type EXPENSE --parent "Expenses"

hep-gnucash transaction create --book-uri "$GNUCASH_BOOK_URI" --json \
  --date 2026-05-08 --description "Cash sale" \
  --splits '[{"account":"Assets:Cash","value":100},{"account":"Income:Sales","value":-100}]'
```

## JSON Contract

Every command emits JSON to stdout:

```json
{
  "ok": true,
  "command": "inspect",
  "book_uri": "postgres://...",
  "result": {},
  "warnings": [],
  "evidence": []
}
```

Errors are also structured JSON and return a non-zero exit code.

## Safety

For PostgreSQL books there is no file copy backup. Instead, write commands return a mutation log with created GUIDs, affected accounts, and split totals. Use PostgreSQL snapshots/PITR or run against a staging book for recovery-grade workflows.
