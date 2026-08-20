"""Golden-set + unit tests for roadmap step 6's track-record checker."""

import importlib
from datetime import date
from unittest.mock import patch

import pytest
import requests

import signal_screener.config as config


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._json_data


def _chart_response(price, currency="USD"):
    return _FakeResponse(
        {"chart": {"result": [{"meta": {"regularMarketPrice": price, "currency": currency}}], "error": None}}
    )


def _empty_chart_response():
    return _FakeResponse({"chart": {"result": None, "error": {"code": "Not Found"}}})


def _reload(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    importlib.reload(importlib.import_module("signal_screener.db"))
    return importlib.reload(importlib.import_module("signal_screener.track_record"))


def test_add_months_clamps_day_overflow():
    from signal_screener.track_record import _add_months

    assert _add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert _add_months(date(2026, 10, 15), 3) == date(2027, 1, 15)
    assert _add_months(date(2026, 8, 16), 12) == date(2027, 8, 16)


@pytest.mark.parametrize(
    "founder_tier,strength,expected",
    [
        ("Founder-CEO", "Established", "High signal"),
        ("Founder-CEO", "Emerging", "Moderate signal"),
        ("Founder-CEO", "None identified", None),
        ("Founder-Chair", "Established", "Moderate signal"),
        ("Founder-Chair", "None identified", "Moderate signal"),
        ("Founder-departed", "Established", None),
        ("N/A", "Established", None),
    ],
)
def test_derive_founder_flag(founder_tier, strength, expected):
    from signal_screener.track_record import derive_founder_flag

    assert derive_founder_flag(founder_tier, strength) == expected


def test_fetch_price_success(tmp_path, monkeypatch):
    track_record = _reload(tmp_path, monkeypatch)

    with patch.object(track_record.requests, "get", return_value=_chart_response(123.45)):
        quote = track_record.fetch_price("VRTX")

    assert quote is not None
    assert quote.price == 123.45
    assert quote.currency == "USD"


def test_fetch_price_returns_none_for_delisted_ticker(tmp_path, monkeypatch):
    track_record = _reload(tmp_path, monkeypatch)

    with patch.object(track_record.requests, "get", return_value=_empty_chart_response()):
        quote = track_record.fetch_price("DAWNGBX")

    assert quote is None


def test_fetch_price_retries_then_succeeds(tmp_path, monkeypatch):
    track_record = _reload(tmp_path, monkeypatch)

    call_count = {"n": 0}

    def get(url, params=None, headers=None, timeout=None):
        call_count["n"] += 1
        if call_count["n"] < track_record.RETRY_ATTEMPTS:
            raise track_record.requests.ConnectionError("transient")
        return _chart_response(50.0)

    with patch.object(track_record.requests, "get", side_effect=get), patch.object(
        track_record.time, "sleep"
    ):
        quote = track_record.fetch_price("VRTX")

    assert quote is not None
    assert quote.price == 50.0
    assert call_count["n"] == track_record.RETRY_ATTEMPTS


def test_flag_entry_creates_once_and_is_never_overwritten(tmp_path, monkeypatch):
    track_record = _reload(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")

    db.init_db()
    with db.connect() as conn, patch.object(
        track_record.requests, "get", return_value=_chart_response(100.0)
    ):
        track_record.flag_entry(
            conn,
            entry_id="abc123",
            entry_type="designation",
            ticker="VRTX",
            flag_given="High signal",
            date_flagged="2026-08-16",
        )

    with db.connect() as conn:
        row = conn.execute("SELECT * FROM tracked_outcomes WHERE entry_id = 'abc123'").fetchone()
        assert row["flag_given"] == "High signal"
        assert row["price_at_flag"] == 100.0
        assert row["price_source"] == "yahoo_finance_chart"
        assert row["check_3mo_due"] == "2026-11-16"
        assert row["check_6mo_due"] == "2027-02-16"
        assert row["check_12mo_due"] == "2027-08-16"

    # Re-flagging with a different flag/price must not change the original
    # record — "created once, never overwritten" (module docstring).
    with db.connect() as conn, patch.object(
        track_record.requests, "get", return_value=_chart_response(999.0)
    ):
        track_record.flag_entry(
            conn,
            entry_id="abc123",
            entry_type="designation",
            ticker="VRTX",
            flag_given="Moderate signal",
            date_flagged="2026-09-01",
        )

    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM tracked_outcomes WHERE entry_id = 'abc123'").fetchall()
        assert len(rows) == 1
        assert rows[0]["flag_given"] == "High signal"
        assert rows[0]["price_at_flag"] == 100.0


def test_flag_entry_still_creates_row_when_price_fetch_fails(tmp_path, monkeypatch):
    """Never silently drop an entry for lack of a price — same guardrail
    ticker matching/verification already follows elsewhere in this project."""
    track_record = _reload(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")

    db.init_db()
    with db.connect() as conn, patch.object(
        track_record.requests, "get", return_value=_empty_chart_response()
    ):
        track_record.flag_entry(
            conn,
            entry_id="xyz789",
            entry_type="founder_stock",
            ticker="DAWNGBX",
            flag_given="High signal",
        )

    with db.connect() as conn:
        row = conn.execute("SELECT * FROM tracked_outcomes WHERE entry_id = 'xyz789'").fetchone()
        assert row is not None
        assert row["price_at_flag"] is None
        assert row["notes_on_outcome"] is not None


def test_check_due_outcomes_only_fills_checkpoints_that_are_due(tmp_path, monkeypatch):
    track_record = _reload(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")

    db.init_db()
    with db.connect() as conn:
        db.insert_tracked_outcome(
            conn,
            entry_id="abc123",
            entry_type="designation",
            ticker="VRTX",
            date_flagged="2026-01-01",
            flag_given="High signal",
            price_source="yahoo_finance_chart",
            price_at_flag=100.0,
            price_at_flag_date="2026-01-01",
            check_3mo_due="2026-04-01",  # already due
            check_6mo_due="2099-01-01",  # far future — not due
            check_12mo_due="2099-01-01",
            notes_on_outcome=None,
        )

    with db.connect() as conn, patch.object(
        track_record.requests, "get", return_value=_chart_response(150.0)
    ):
        filled = track_record.check_due_outcomes(conn, as_of="2026-08-16")

    assert filled == {"3mo": 1, "6mo": 0, "12mo": 0}

    with db.connect() as conn:
        row = conn.execute("SELECT * FROM tracked_outcomes WHERE entry_id = 'abc123'").fetchone()
        assert row["price_at_3mo"] == 150.0
        assert row["price_at_3mo_date"] == date.today().isoformat()
        assert row["price_at_6mo"] is None

    # Running it again the same day must not re-fill an already-recorded
    # checkpoint (get_due_outcome_checkpoints excludes non-NULL prices).
    with db.connect() as conn, patch.object(
        track_record.requests, "get", return_value=_chart_response(150.0)
    ):
        filled_again = track_record.check_due_outcomes(conn, as_of="2026-08-16")
    assert filled_again == {"3mo": 0, "6mo": 0, "12mo": 0}
