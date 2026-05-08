from __future__ import annotations

import sys

import pytest

from tests import fake_gnucash


@pytest.fixture(autouse=True)
def install_fake_gnucash(monkeypatch):
    fake_gnucash.BOOKS.clear()
    monkeypatch.setitem(sys.modules, "gnucash", fake_gnucash)
    monkeypatch.setitem(sys.modules, "gnucash.gnucash_core", fake_gnucash.gnucash_core)
    yield
