"""Unit tests for valuation.py — market cap/P/E/52-week-range/beta/
dividend-yield fetch for the founder-led site cards. External HTTP calls
are mocked."""

from unittest.mock import patch

import requests

from signal_screener import valuation


class _FakeResponse:
    def __init__(self, json_data=None, text="", status_code=200):
        self._json_data = json_data
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._json_data


def _quote_summary_response(*, trailing_pe=53.41, dividend_yield=None, market_cap=99317571584):
    dividend_field = {"raw": dividend_yield, "fmt": f"{dividend_yield:.2%}"} if dividend_yield else {}
    return _FakeResponse(
        json_data={
            "quoteSummary": {
                "result": [
                    {
                        "summaryDetail": {
                            "marketCap": {"raw": market_cap, "fmt": "99.32B"},
                            "trailingPE": {"raw": trailing_pe, "fmt": f"{trailing_pe:.2f}"},
                            "forwardPE": {"raw": 34.47, "fmt": "34.47"},
                            "fiftyTwoWeekLow": {"raw": 1495.0, "fmt": "1,495.00"},
                            "fiftyTwoWeekHigh": {"raw": 2548.5, "fmt": "2,548.50"},
                            "beta": {"raw": 1.312, "fmt": "1.31"},
                            "dividendYield": dividend_field,
                        },
                        "price": {"marketCap": {"raw": market_cap}, "currency": "USD"},
                    }
                ],
                "error": None,
            }
        }
    )


def _empty_quote_summary_response():
    return _FakeResponse(json_data={"quoteSummary": {"result": [], "error": {"code": "Not Found"}}})


def test_get_session_and_crumb_success():
    responses = [_FakeResponse(text=""), _FakeResponse(text="realCrumb123")]

    def get(url, timeout=None, **kwargs):
        return responses.pop(0)

    with patch.object(valuation.requests.Session, "get", side_effect=get):
        result = valuation.get_session_and_crumb()

    assert result is not None
    session, crumb = result
    assert crumb == "realCrumb123"


def test_get_session_and_crumb_returns_none_on_invalid_crumb():
    responses = [_FakeResponse(text=""), _FakeResponse(text="Invalid Crumb")]

    def get(url, timeout=None, **kwargs):
        return responses.pop(0)

    with patch.object(valuation.requests.Session, "get", side_effect=get):
        result = valuation.get_session_and_crumb()

    assert result is None


def test_get_session_and_crumb_returns_none_after_retries_exhausted():
    with patch.object(
        valuation.requests.Session, "get", side_effect=requests.ConnectionError("boom")
    ), patch.object(valuation.time, "sleep"):
        result = valuation.get_session_and_crumb()

    assert result is None


def test_fetch_valuation_metrics_success():
    session = requests.Session()
    with patch.object(session, "get", return_value=_quote_summary_response(dividend_yield=0.0118)):
        metrics = valuation.fetch_valuation_metrics(session, "crumb123", "0700.HK")

    assert metrics is not None
    assert metrics.market_cap == 99317571584
    assert metrics.currency == "USD"
    assert metrics.trailing_pe == 53.41
    assert metrics.forward_pe == 34.47
    assert metrics.fifty_two_week_low == 1495.0
    assert metrics.fifty_two_week_high == 2548.5
    assert metrics.beta == 1.312
    # Converted to a percentage (1.18), not Yahoo's raw fraction (0.0118).
    assert round(metrics.dividend_yield_pct, 2) == 1.18
    assert metrics.source == "yahoo_finance_quotesummary"


def test_fetch_valuation_metrics_none_dividend_yield_is_not_zero():
    """A company that's never paid a dividend gets an empty {} from Yahoo
    for dividendYield, not a real 0.0 — this must come through as None
    (not disclosed / not applicable), never a fabricated 0."""
    session = requests.Session()
    with patch.object(session, "get", return_value=_quote_summary_response(dividend_yield=None)):
        metrics = valuation.fetch_valuation_metrics(session, "crumb123", "ADYEN.AS")

    assert metrics.dividend_yield_pct is None


def test_fetch_valuation_metrics_returns_none_for_unresolvable_ticker():
    session = requests.Session()
    with patch.object(session, "get", return_value=_empty_quote_summary_response()):
        metrics = valuation.fetch_valuation_metrics(session, "crumb123", "NOTATICKER")

    assert metrics is None


def test_fetch_valuation_metrics_returns_none_after_retries_exhausted():
    session = requests.Session()
    with patch.object(
        session, "get", side_effect=requests.ConnectionError("boom")
    ), patch.object(valuation.time, "sleep"):
        metrics = valuation.fetch_valuation_metrics(session, "crumb123", "MELI")

    assert metrics is None
