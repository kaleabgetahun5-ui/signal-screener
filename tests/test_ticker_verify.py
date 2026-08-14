"""Golden-set regression tests for matching/ticker_verify.py: known
ticker/company-name pairs that must verify (or must not), covering the
retry-with-backoff + SEC EDGAR full-text fallback added after Yahoo's
unofficial search endpoint was observed failing on real, unambiguous
tickers (PDD Holdings/PDD).

All external HTTP calls are mocked and time.sleep is patched out so the
retry logic runs at full speed in CI.
"""

from unittest.mock import patch

import pytest

from signal_screener.matching import ticker_verify
from signal_screener.matching.ticker_verify import check_delisted_or_acquired, verify_ticker


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ticker_verify.requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._json_data


def _yahoo_quotes(*pairs):
    return _FakeResponse({"quotes": [{"symbol": s, "shortname": n} for s, n in pairs]})


def _sec_fulltext_hit(display_name):
    return _FakeResponse({"hits": {"hits": [{"_source": {"display_names": [display_name]}}]}})


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch.object(ticker_verify.time, "sleep"):
        yield


def test_pdd_verifies_via_yahoo_when_yahoo_succeeds():
    with patch.object(
        ticker_verify.requests, "get", return_value=_yahoo_quotes(("PDD", "PDD Holdings Inc."))
    ):
        result = verify_ticker("PDD", "PDD Holdings")
    assert result.verified is True
    assert result.source == "yahoo_finance_search"


def test_pdd_verifies_via_sec_edgar_when_yahoo_is_flaky():
    """The reported bug: Yahoo's search endpoint returns no listing for
    PDD — an unambiguous, correct match — on some requests. After retries
    still come back empty, SEC EDGAR full-text search must catch it rather
    than the ticker being marked unverified."""
    yahoo_empty = _FakeResponse({"quotes": []})
    sec_hit = _sec_fulltext_hit("PDD Holdings Inc.  (PDD)  (CIK 0001737806)")

    def get(url, params=None, headers=None, timeout=None):
        if url == ticker_verify.YAHOO_SEARCH_URL:
            return yahoo_empty
        assert url == ticker_verify.SEC_FULLTEXT_SEARCH_URL
        return sec_hit

    with patch.object(ticker_verify.requests, "get", side_effect=get) as mock_get:
        result = verify_ticker("PDD", "PDD Holdings")

    assert result.verified is True
    assert result.source == "sec_edgar_fulltext_search"
    # Retried Yahoo (unreliable endpoint) before falling back, not just once.
    yahoo_calls = [c for c in mock_get.call_args_list if c.args[0] == ticker_verify.YAHOO_SEARCH_URL]
    assert len(yahoo_calls) == ticker_verify.RETRY_ATTEMPTS


def test_yahoo_transient_failure_retries_then_succeeds():
    call_count = {"n": 0}

    def get(url, params=None, headers=None, timeout=None):
        call_count["n"] += 1
        if call_count["n"] < ticker_verify.RETRY_ATTEMPTS:
            raise ticker_verify.requests.ConnectionError("transient network error")
        return _yahoo_quotes(("PDD", "PDD Holdings Inc."))

    with patch.object(ticker_verify.requests, "get", side_effect=get):
        result = verify_ticker("PDD", "PDD Holdings")

    assert result.verified is True
    assert call_count["n"] == ticker_verify.RETRY_ATTEMPTS


def test_meli_does_not_verify_against_coupang():
    with patch.object(
        ticker_verify.requests, "get", return_value=_yahoo_quotes(("CPNG", "Coupang, Inc."))
    ):
        result = verify_ticker("CPNG", "MercadoLibre")
    assert result.verified is False


def test_wrong_ticker_stays_unverified_after_both_sources_fail():
    def get(url, params=None, headers=None, timeout=None):
        if url == ticker_verify.YAHOO_SEARCH_URL:
            return _yahoo_quotes(("HSAI", "Hesai Group"))
        return _FakeResponse({"hits": {"hits": []}})

    with patch.object(ticker_verify.requests, "get", side_effect=get):
        result = verify_ticker("HSAI", "Eisai")

    assert result.verified is False
    assert "yahoo" in result.reason and "sec_edgar" in result.reason


def _sec_fulltext_cik_hit(display_name, cik):
    return _FakeResponse(
        {"hits": {"hits": [{"_source": {"ciks": [cik], "display_names": [display_name]}}]}}
    )


def test_check_delisted_or_acquired_detects_real_filer_with_no_active_ticker():
    """The reported case: Day One Biopharmaceuticals was acquired by
    Servier and delisted. SEC full-text search still finds its CIK (filing
    history stays public), but its submissions record has no active
    ticker/exchange — that combination is the confirmed signal."""
    fulltext_hit = _sec_fulltext_cik_hit(
        "Day One Biopharmaceuticals, Inc.  (DAWN)  (CIK 0001845337)", "0001845337"
    )
    submissions = _FakeResponse({"tickers": [], "exchanges": []})

    def get(url, params=None, headers=None, timeout=None):
        if url == ticker_verify.SEC_FULLTEXT_SEARCH_URL:
            return fulltext_hit
        assert url == ticker_verify.SEC_SUBMISSIONS_URL.format(cik="0001845337")
        return submissions

    with patch.object(ticker_verify.requests, "get", side_effect=get):
        result = check_delisted_or_acquired("Day One Biopharmaceuticals")

    assert result is not None
    assert result.delisted_or_acquired is True
    assert result.verified is False
    assert "1845337" in result.reason


def test_check_delisted_or_acquired_returns_none_for_still_active_company():
    fulltext_hit = _sec_fulltext_cik_hit(
        "VERTEX PHARMACEUTICALS INC / MA  (VRTX)  (CIK 0000875320)", "0000875320"
    )
    submissions = _FakeResponse({"tickers": ["VRTX"], "exchanges": ["Nasdaq"]})

    def get(url, params=None, headers=None, timeout=None):
        if url == ticker_verify.SEC_FULLTEXT_SEARCH_URL:
            return fulltext_hit
        return submissions

    with patch.object(ticker_verify.requests, "get", side_effect=get):
        result = check_delisted_or_acquired("Vertex Pharmaceuticals")

    assert result is None


def test_check_delisted_or_acquired_returns_none_when_no_confident_cik_match():
    """Eisai isn't an SEC filer — full-text search only turns up filings
    from unrelated companies that merely mention "Eisai" in passing (a
    competitor, a licensing partner), which must not be mistaken for a
    filing by Eisai itself."""
    unrelated_hits = _FakeResponse(
        {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "ciks": ["0001506251"],
                            "display_names": ["Citius Pharmaceuticals, Inc.  (CTXR)  (CIK 0001506251)"],
                        }
                    }
                ]
            }
        }
    )
    with patch.object(ticker_verify.requests, "get", return_value=unrelated_hits):
        result = check_delisted_or_acquired("Eisai")
    assert result is None
