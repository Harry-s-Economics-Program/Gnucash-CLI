from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from fractions import Fraction
from importlib import import_module
from typing import Any, Iterator


_MISSING = object()


class EngineUnavailable(RuntimeError):
    pass


def load_engine():
    try:
        gnucash = import_module("gnucash")
    except ModuleNotFoundError as exc:
        raise EngineUnavailable(
            "Official GnuCash Python bindings are not importable. "
            "Install python3-gnucash or build GnuCash with -DWITH_PYTHON=ON."
        ) from exc
    return gnucash


def call_any(obj: Any, names: list[str], *args, default: Any = _MISSING) -> Any:
    for name in names:
        fn = getattr(obj, name, None)
        if callable(fn):
            return fn(*args)
    if default is not _MISSING:
        return default
    raise AttributeError(f"{obj!r} has none of methods: {', '.join(names)}")


def attr_or_call(obj: Any, names: list[str], default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            return value() if callable(value) else value
    return default


@dataclass
class EngineModules:
    gnucash: Any
    core: Any

    @classmethod
    def load(cls) -> "EngineModules":
        gnucash = load_engine()
        core = getattr(gnucash, "gnucash_core", None)
        if core is None:
            core = import_module("gnucash.gnucash_core")
        return cls(gnucash=gnucash, core=core)


@contextmanager
def open_session(book_uri: str, *, readonly: bool = False, break_lock: bool = False) -> Iterator[Any]:
    modules = EngineModules.load()
    mode = _session_mode(modules, readonly=readonly, break_lock=break_lock)
    session = modules.gnucash.Session(book_uri, mode)
    try:
        yield session
        if not readonly:
            call_any(session, ["save"], default=None)
    finally:
        call_any(session, ["end"], default=None)
        call_any(session, ["destroy"], default=None)


def _session_mode(modules: EngineModules, *, readonly: bool, break_lock: bool) -> Any:
    open_mode = modules.gnucash.SessionOpenMode
    if readonly:
        return open_mode.SESSION_READ_ONLY
    if break_lock:
        return open_mode.SESSION_BREAK_LOCK
    return open_mode.SESSION_NORMAL_OPEN


def get_book(session: Any) -> Any:
    return attr_or_call(session, ["book", "get_book"])


def get_root_account(book: Any) -> Any:
    return call_any(book, ["get_root_account", "GetRootAccount"])


def account_children(account: Any) -> list[Any]:
    return list(call_any(account, ["get_children", "get_children_sorted", "GetChildren"], default=[]))


def account_descendants(root: Any) -> list[Any]:
    accounts = []

    def walk(account: Any) -> None:
        for child in account_children(account):
            accounts.append(child)
            walk(child)

    walk(root)
    return accounts


def account_name(account: Any) -> str:
    return str(attr_or_call(account, ["name", "GetName", "get_name"], ""))


def account_fullname(account: Any) -> str:
    value = attr_or_call(account, ["get_full_name", "GetFullName"], None)
    if value:
        return str(value)
    parts = []
    current = account
    while current is not None:
        name = account_name(current)
        if name and name != "Root Account":
            parts.append(name)
        current = attr_or_call(current, ["get_parent", "GetParent"], None)
    return ":".join(reversed(parts))


def account_type(account: Any) -> str:
    raw = attr_or_call(account, ["GetType", "get_type"], "")
    if isinstance(raw, str):
        return raw.upper()
    return ACCOUNT_TYPE_NAMES.get(raw, str(raw))


def account_guid(account: Any) -> str:
    guid = call_any(account, ["GetGUID", "get_guid"], default="")
    return guid_to_string(guid)


def guid_to_string(guid: Any) -> str:
    if guid is None:
        return ""
    if hasattr(guid, "to_string"):
        return str(guid.to_string())
    return str(guid)


def commodity_mnemonic(commodity: Any) -> str | None:
    if commodity is None:
        return None
    return attr_or_call(commodity, ["get_mnemonic", "GetMnemonic"], None)


def account_commodity(account: Any) -> Any:
    return attr_or_call(account, ["GetCommodity", "get_currency_or_parent"], None)


def find_account(book: Any, fullname: str) -> Any:
    root = get_root_account(book)
    if account_fullname(root) == fullname or account_name(root) == fullname:
        return root
    for account in account_descendants(root):
        if account_fullname(account) == fullname or account_name(account) == fullname:
            return account
    raise ValueError(f"Account not found: {fullname}")


def lookup_currency(book: Any, mnemonic: str | None, fallback_account: Any | None = None) -> Any:
    if not mnemonic and fallback_account is not None:
        return account_commodity(fallback_account)
    table = call_any(book, ["get_table"], default=None)
    if table is not None and mnemonic:
        currency = call_any(table, ["lookup", "lookup_unique"], "CURRENCY", mnemonic, default=None)
        if currency is not None:
            return currency
    if fallback_account is not None:
        return account_commodity(fallback_account)
    raise ValueError(f"Currency not found: {mnemonic}")


def decimal_to_gnc_numeric(value: Decimal) -> Any:
    modules = EngineModules.load()
    frac = Fraction(value)
    return modules.gnucash.GncNumeric(frac.numerator, frac.denominator)


def gnc_numeric_to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if hasattr(value, "to_fraction"):
        frac = value.to_fraction()
        return Decimal(frac.numerator) / Decimal(frac.denominator)
    if hasattr(value, "to_decimal"):
        result = value.to_decimal(None)
        if result is not None:
            return Decimal(str(result))
    if hasattr(value, "to_double"):
        return Decimal(str(value.to_double()))
    return Decimal(str(value))


def date_to_seconds(value: date) -> int:
    return int(datetime.combine(value, time()).timestamp())


def seconds_to_date(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    try:
        return datetime.fromtimestamp(int(value)).date().isoformat()
    except Exception:
        return str(value)


ACCOUNT_TYPE_NAMES = {
    0: "BANK",
    1: "CASH",
    2: "ASSET",
    3: "CREDIT",
    4: "LIABILITY",
    5: "STOCK",
    6: "MUTUAL",
    8: "INCOME",
    9: "EXPENSE",
    10: "EQUITY",
    11: "RECEIVABLE",
    12: "PAYABLE",
    13: "ROOT",
    14: "TRADING",
}
