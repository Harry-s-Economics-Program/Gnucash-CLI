from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from fractions import Fraction
from types import SimpleNamespace
from uuid import uuid4


ACCT_TYPE_ASSET = "ASSET"
ACCT_TYPE_BANK = "BANK"
ACCT_TYPE_CASH = "CASH"
ACCT_TYPE_RECEIVABLE = "RECEIVABLE"
ACCT_TYPE_LIABILITY = "LIABILITY"
ACCT_TYPE_PAYABLE = "PAYABLE"
ACCT_TYPE_INCOME = "INCOME"
ACCT_TYPE_EXPENSE = "EXPENSE"
ACCT_TYPE_EQUITY = "EQUITY"


class SessionOpenMode:
    SESSION_NORMAL_OPEN = 0
    SESSION_NEW_STORE = 2
    SESSION_READ_ONLY = 4
    SESSION_BREAK_LOCK = 5


BOOKS = {}
SESSION_EVENTS = []


class GncNumeric:
    def __init__(self, numerator=0, denominator=1):
        self.numerator = int(numerator)
        self.denominator = int(denominator)

    def to_fraction(self):
        return Fraction(self.numerator, self.denominator)

    def __str__(self):
        return str(Decimal(self.numerator) / Decimal(self.denominator))


class FakeGUID:
    def __init__(self):
        self.value = uuid4().hex

    def to_string(self):
        return self.value

    def __str__(self):
        return self.value


class FakeCommodity:
    def __init__(self, mnemonic="USD"):
        self.mnemonic = mnemonic

    def get_mnemonic(self):
        return self.mnemonic


class FakeCommodityTable:
    def __init__(self, currency):
        self.currency = currency

    def lookup(self, namespace, mnemonic):
        if namespace == "CURRENCY" and mnemonic == self.currency.mnemonic:
            return self.currency
        return None


class Account:
    def __init__(self, book=None, name="", type="ROOT", parent=None, commodity=None):
        self.book = book
        self.guid = FakeGUID()
        self._name = name
        self._type = type
        self.parent = parent
        self.children = []
        self.splits = []
        self.commodity = commodity or (book.currency if book else FakeCommodity())

    def BeginEdit(self):
        return None

    def CommitEdit(self):
        return None

    def SetName(self, name):
        self._name = name

    def GetName(self):
        return self._name

    def SetType(self, type):
        self._type = type

    def GetType(self):
        return self._type

    def SetCommodity(self, commodity):
        self.commodity = commodity

    def GetCommodity(self):
        return self.commodity

    def AppendChild(self, account):
        account.parent = self
        self.children.append(account)

    append_child = AppendChild

    def get_children(self):
        return self.children

    def get_parent(self):
        return self.parent

    def get_full_name(self):
        names = []
        current = self
        while current is not None:
            if current._name and current._name != "Root Account":
                names.append(current._name)
            current = current.parent
        return ":".join(reversed(names))

    def GetGUID(self):
        return self.guid

    def GetSplitList(self):
        return self.splits


class Split:
    def __init__(self, book=None):
        self.book = book
        self.guid = FakeGUID()
        self.account = None
        self.parent = None
        self.value = GncNumeric()
        self.amount = GncNumeric()
        self.memo = ""

    def SetAccount(self, account):
        self.account = account
        if self not in account.splits:
            account.splits.append(self)

    def GetAccount(self):
        return self.account

    def SetParent(self, parent):
        self.parent = parent

    def GetParent(self):
        return self.parent

    def SetValue(self, value):
        self.value = value

    def GetValue(self):
        return self.value

    def SetAmount(self, amount):
        self.amount = amount

    def GetAmount(self):
        return self.amount

    def SetMemo(self, memo):
        self.memo = memo

    def GetMemo(self):
        return self.memo

    def GetGUID(self):
        return self.guid


class Transaction:
    def __init__(self, book=None):
        self.book = book
        self.guid = FakeGUID()
        self.splits = []
        self.description = ""
        self.num = ""
        self.currency = book.currency if book else FakeCommodity()
        self.date_seconds = int(datetime.combine(date.today(), time()).timestamp())

    def BeginEdit(self):
        return None

    def CommitEdit(self):
        if self.book and self not in self.book.transactions:
            self.book.transactions.append(self)

    def SetCurrency(self, currency):
        self.currency = currency

    def GetCurrency(self):
        return self.currency

    def SetDescription(self, description):
        self.description = description

    def GetDescription(self):
        return self.description

    def SetNum(self, num):
        self.num = num

    def GetNum(self):
        return self.num

    def SetDatePostedSecs(self, seconds):
        self.date_seconds = int(seconds)

    def GetDate(self):
        return self.date_seconds

    def AppendSplit(self, split):
        split.parent = self
        self.splits.append(split)

    def GetSplitList(self):
        return self.splits

    def GetGUID(self):
        return self.guid

    def GetImbalance(self):
        total = sum((split.value.to_fraction() for split in self.splits), Fraction(0))
        return [] if total == 0 else [total]


class FakeBook:
    def __init__(self):
        self.currency = FakeCommodity("USD")
        self.root = Account(self, "Root Account", "ROOT", None, self.currency)
        self.transactions = []
        self.table = FakeCommodityTable(self.currency)

    def get_root_account(self):
        return self.root

    def get_table(self):
        return self.table


class Session:
    def __init__(self, uri, mode=None):
        self.uri = uri
        self.mode = mode
        self.book = BOOKS.setdefault(uri, sample_book())
        self.saved = False
        self.ended = False
        SESSION_EVENTS.append({"event": "open", "uri": uri, "mode": mode})

    def get_book(self):
        return self.book

    def save(self):
        self.saved = True
        SESSION_EVENTS.append({"event": "save", "uri": self.uri, "mode": self.mode})

    def end(self):
        self.ended = True
        SESSION_EVENTS.append({"event": "end", "uri": self.uri, "mode": self.mode})

    def destroy(self):
        SESSION_EVENTS.append({"event": "destroy", "uri": self.uri, "mode": self.mode})
        return None


def sample_book():
    book = FakeBook()
    root = book.root
    assets = Account(book, "Assets", "ASSET", root, book.currency)
    cash = Account(book, "Cash", "BANK", assets, book.currency)
    ar = Account(book, "Accounts Receivable", "RECEIVABLE", assets, book.currency)
    liabilities = Account(book, "Liabilities", "LIABILITY", root, book.currency)
    ap = Account(book, "Accounts Payable", "PAYABLE", liabilities, book.currency)
    equity = Account(book, "Equity", "EQUITY", root, book.currency)
    opening = Account(book, "Opening Balances", "EQUITY", equity, book.currency)
    income = Account(book, "Income", "INCOME", root, book.currency)
    sales = Account(book, "Sales", "INCOME", income, book.currency)
    expenses = Account(book, "Expenses", "EXPENSE", root, book.currency)
    cogs = Account(book, "COGS", "EXPENSE", expenses, book.currency)
    rent = Account(book, "Rent", "EXPENSE", expenses, book.currency)
    for parent, child in [
        (root, assets),
        (assets, cash),
        (assets, ar),
        (root, liabilities),
        (liabilities, ap),
        (root, equity),
        (equity, opening),
        (root, income),
        (income, sales),
        (root, expenses),
        (expenses, cogs),
        (expenses, rent),
    ]:
        parent.AppendChild(child)
    add_txn(book, date(2026, 1, 1), "Opening cash", [(cash, 20000), (opening, -20000)])
    add_txn(book, date(2026, 1, 31), "January sales", [(cash, 50000), (sales, -50000)])
    add_txn(book, date(2026, 1, 31), "January COGS", [(cogs, 28000), (ap, -28000)])
    add_txn(book, date(2026, 2, 28), "February sales", [(ar, 56000), (sales, -56000)])
    add_txn(book, date(2026, 2, 28), "February rent", [(rent, 6000), (cash, -6000)])
    return book


def add_txn(book, txn_date, description, split_rows):
    txn = Transaction(book)
    txn.SetDescription(description)
    txn.SetDatePostedSecs(int(datetime.combine(txn_date, time()).timestamp()))
    for account, value in split_rows:
        split = Split(book)
        numeric = GncNumeric(int(Decimal(str(value)) * 100), 100)
        split.SetValue(numeric)
        split.SetAmount(numeric)
        txn.AppendSplit(split)
        split.SetAccount(account)
    txn.CommitEdit()


gnucash_core = SimpleNamespace(
    ACCT_TYPE_ASSET=ACCT_TYPE_ASSET,
    ACCT_TYPE_BANK=ACCT_TYPE_BANK,
    ACCT_TYPE_CASH=ACCT_TYPE_CASH,
    ACCT_TYPE_RECEIVABLE=ACCT_TYPE_RECEIVABLE,
    ACCT_TYPE_LIABILITY=ACCT_TYPE_LIABILITY,
    ACCT_TYPE_PAYABLE=ACCT_TYPE_PAYABLE,
    ACCT_TYPE_INCOME=ACCT_TYPE_INCOME,
    ACCT_TYPE_EXPENSE=ACCT_TYPE_EXPENSE,
    ACCT_TYPE_EQUITY=ACCT_TYPE_EQUITY,
)
