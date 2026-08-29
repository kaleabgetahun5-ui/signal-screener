"""Unit tests for backtest.py — "$100 at IPO vs. S&P 500" for the
founder-led site cards. External HTTP calls are mocked."""

from unittest.mock import patch

import requests

from signal_screener import backtest


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._json_data


def _meta_response(*, first_trade_ts=1186704600, current_price=1966.25, currency="USD"):
    return _FakeResponse(
        {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "firstTradeDate": first_trade_ts,
                            "regularMarketPrice": current_price,
                            "currency": currency,
                        }
                    }
                ],
                "error": None,
            }
        }
    )


def _empty_meta_response():
    return _FakeResponse({"chart": {"result": None, "error": {"code": "Not Found"}}})


def _historical_response(closes):
    return _FakeResponse(
        {
            "chart": {
                "result": [
                    {
                        "timestamp": list(range(len(closes))),
                        "indicators": {"quote": [{"close": closes}]},
                    }
                ],
                "error": None,
            }
        }
    )


def test_get_current_price_success():
    with patch.object(backtest.requests, "get", return_value=_meta_response(current_price=100.0)):
        price = backtest.get_current_price("MELI")
    assert price == 100.0


def test_get_current_price_returns_none_on_missing_result():
    with patch.object(backtest.requests, "get", return_value=_empty_meta_response()):
        price = backtest.get_current_price("NOTATICKER")
    assert price is None


def test_get_price_near_date_returns_first_non_null_close():
    with patch.object(
        backtest.requests, "get", return_value=_historical_response([None, 28.5, 31.65])
    ):
        price = backtest.get_price_near_date("MELI", "2007-08-10")
    assert price == 28.5


def test_get_price_near_date_returns_none_when_no_trading_data():
    with patch.object(backtest.requests, "get", return_value=_historical_response([])):
        price = backtest.get_price_near_date("MELI", "2007-08-10")
    assert price is None


def test_compute_backtest_success():
    responses = {
        "meta": _meta_response(first_trade_ts=1186704600, current_price=1966.25, currency="USD"),
        "company_hist": _historical_response([28.5, 31.65]),
        "sp500_hist": _historical_response([1453.64, 1452.92]),
    }
    call_order = []

    def get(url, params=None, **kwargs):
        if "period1" in (params or {}):
            if "%5EGSPC" in url or "^GSPC" in url:
                call_order.append("sp500_hist")
                return responses["sp500_hist"]
            call_order.append("company_hist")
            return responses["company_hist"]
        call_order.append("meta")
        return responses["meta"]

    with patch.object(backtest.requests, "get", side_effect=get):
        result = backtest.compute_backtest("MELI", sp500_current_price=7711.76)

    assert result is not None
    assert result.ipo_date == "2007-08-10"
    assert result.company_ipo_price == 28.5
    assert result.company_current_price == 1966.25
    assert result.company_currency == "USD"
    assert round(result.company_growth_multiple, 2) == round(1966.25 / 28.5, 2)
    assert result.sp500_price_at_ipo == 1453.64
    assert result.sp500_current_price == 7711.76
    assert round(result.sp500_growth_multiple, 2) == round(7711.76 / 1453.64, 2)
    assert result.source == "yahoo_finance_chart"


def test_compute_backtest_returns_none_when_sp500_price_missing():
    assert backtest.compute_backtest("MELI", sp500_current_price=None) is None


def test_compute_backtest_returns_none_when_ipo_date_unknown():
    with patch.object(backtest.requests, "get", return_value=_empty_meta_response()):
        result = backtest.compute_backtest("MELI", sp500_current_price=7711.76)
    assert result is None


def test_compute_backtest_returns_none_when_historical_window_empty():
    def get(url, params=None, **kwargs):
        if "period1" in (params or {}):
            return _historical_response([])
        return _meta_response()

    with patch.object(backtest.requests, "get", side_effect=get):
        result = backtest.compute_backtest("MELI", sp500_current_price=7711.76)
    assert result is None
