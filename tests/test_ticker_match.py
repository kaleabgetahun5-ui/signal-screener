"""Golden-set regression tests for matching/ticker_match.py and the
SEC + OpenFIGI fallback orchestration in matching/resolve.py.

All external HTTP calls are mocked — these are known name -> ticker pairs
that must resolve correctly, not a live check of SEC/OpenFIGI/Yahoo, which
would make the suite flaky and rate-limit-prone in CI.
"""

from unittest.mock import Mock, patch

import pytest

from signal_screener.matching import ticker_match
from signal_screener.matching.resolve import resolve_ticker
from signal_screener.matching.ticker_match import (
    match_company_to_ticker,
    match_company_to_ticker_openfigi,
)

# A small slice of SEC's real company_tickers.json, exact titles as SEC
# publishes them — enough to exercise real fuzzy-match behavior without
# hitting the network.
SEC_FIXTURE = {
    "0": {"cik_str": 1861737, "ticker": "HSAI", "title": "Hesai Group"},
    "1": {"cik_str": 1099590, "ticker": "MELI", "title": "MERCADOLIBRE INC"},
    "2": {"cik_str": 1834584, "ticker": "CPNG", "title": "Coupang, Inc."},
    "3": {"cik_str": 1737806, "ticker": "PDD", "title": "PDD Holdings Inc."},
}


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ticker_match.requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._json_data


@pytest.fixture(autouse=True)
def _reset_sec_cache():
    """The module caches SEC's list at import scope — clear it around every
    test so mocked responses don't leak between tests."""
    ticker_match._raw_sec_entries = None
    ticker_match._ticker_cache = None
    ticker_match._cik_cache = None
    yield
    ticker_match._raw_sec_entries = None
    ticker_match._ticker_cache = None
    ticker_match._cik_cache = None


@pytest.fixture
def mock_sec_list():
    with patch.object(ticker_match.requests, "get", return_value=_FakeResponse(SEC_FIXTURE)) as m:
        yield m


def test_match_company_to_ticker_finds_close_matches(mock_sec_list):
    assert match_company_to_ticker("MercadoLibre").ticker == "MELI"
    assert match_company_to_ticker("Coupang").ticker == "CPNG"
    assert match_company_to_ticker("PDD Holdings").ticker == "PDD"


def test_match_company_to_ticker_does_not_confuse_mercadolibre_and_coupang(mock_sec_list):
    meli = match_company_to_ticker("MercadoLibre")
    cpng = match_company_to_ticker("Coupang")
    assert meli.ticker != cpng.ticker
    assert meli.ticker == "MELI"
    assert cpng.ticker == "CPNG"


def test_match_company_to_ticker_sec_only_reproduces_the_eisai_trap(mock_sec_list):
    """Documents the actual bug: SEC's list has no Eisai entry at all, and
    "Eisai" fuzzy-matches "Hesai Group" (a coincidental near-anagram) well
    above MIN_MATCH_SCORE on the SEC-only path. This is exactly why
    resolve_ticker() exists — see test below for the corrected behavior."""
    match = match_company_to_ticker("Eisai")
    assert match is not None
    assert match.ticker == "HSAI"


def test_match_company_to_ticker_openfigi_filters_out_derivatives():
    candidates = {
        "data": [
            {
                "figi": "OPT1",
                "name": "April 22 Puts on DAWN US",
                "ticker": "DAWN 04/14/22 P17.5",
                "exchCode": "UP",
                "securityType": "Equity Option",
                "marketSector": "Equity",
            },
            {
                "figi": "EQ1",
                "name": "Day One Biopharmaceuticals, Inc.",
                "ticker": "DAWN",
                "exchCode": "US",
                "securityType": "Common Stock",
                "marketSector": "Equity",
            },
            {
                "figi": "CRYPTO1",
                "name": "Dawn Protocol",
                "ticker": "DAWN",
                "exchCode": None,
                "securityType": "Crypto",
                "marketSector": "Curncy",
            },
        ]
    }
    with patch.object(ticker_match.requests, "post", return_value=_FakeResponse(candidates)):
        match = match_company_to_ticker_openfigi("Day One Biopharmaceuticals")
    assert match is not None
    assert match.ticker == "DAWN"
    assert match.matched_company_name == "Day One Biopharmaceuticals, Inc."


def test_match_company_to_ticker_openfigi_prefers_us_composite_listing():
    """Regression case found against live data: OpenFIGI returns the same
    company under dozens of equally-named listings across exchanges (Eisai
    alone has 70+). Shortest-ticker alone picked a short non-US listing
    ("EII" on a European exchange) over the real US ADR ("ESAIY") — and a
    non-US listing can never verify against Yahoo/SEC EDGAR (both US-
    centric) even when it's the right company."""
    candidates = {
        "data": [
            {
                "figi": "EU1",
                "name": "EISAI CO LTD",
                "ticker": "EII",
                "exchCode": "LU",
                "securityType": "Common Stock",
                "marketSector": "Equity",
                "compositeFIGI": "EU1COMPOSITE",
            },
            {
                "figi": "US1",
                "name": "EISAI CO LTD",
                "ticker": "ESAIY",
                "exchCode": "US",
                "securityType": "ADR",
                "marketSector": "Equity",
                "compositeFIGI": "US1",
            },
        ]
    }
    with patch.object(ticker_match.requests, "post", return_value=_FakeResponse(candidates)):
        match = match_company_to_ticker_openfigi("Eisai")
    assert match.ticker == "ESAIY"


def test_match_company_to_ticker_openfigi_does_not_prefer_composite_for_non_us_listings():
    """Regression case found live against Zalando (Tier 2, Germany): among
    90+ "ZALANDO SE" listings, the clean home-market ticker "ZAL" never
    happens to carry compositeFIGI == figi, but a currency-variant listing
    ("ZAL1GBX") does. Trusting "composite" alone for a non-US company (the
    prior version of this tie-break did) picked the GBX-denominated
    listing over the real one — composite is only a meaningful signal
    paired with exchCode "US" (see test above)."""
    candidates = {
        "data": [
            {
                "figi": "GBX1",
                "name": "ZALANDO SE",
                "ticker": "ZAL1GBX",
                "exchCode": "EO",
                "securityType": "Common Stock",
                "marketSector": "Equity",
                "compositeFIGI": "GBX1",  # composite, but not a US listing
            },
            {
                "figi": "DE1",
                "name": "ZALANDO SE",
                "ticker": "ZAL",
                "exchCode": "GY",
                "securityType": "Common Stock",
                "marketSector": "Equity",
                "compositeFIGI": "DE1COMPOSITE",  # not composite
            },
        ]
    }
    with patch.object(ticker_match.requests, "post", return_value=_FakeResponse(candidates)):
        match = match_company_to_ticker_openfigi("Zalando")
    assert match.ticker == "ZAL"


def test_match_company_to_ticker_openfigi_returns_none_below_threshold():
    candidates = {
        "data": [
            {
                "figi": "EQ1",
                "name": "Completely Unrelated Company Ltd",
                "ticker": "XYZ",
                "exchCode": "US",
                "securityType": "Common Stock",
                "marketSector": "Equity",
            }
        ]
    }
    with patch.object(ticker_match.requests, "post", return_value=_FakeResponse(candidates)):
        match = match_company_to_ticker_openfigi("Day One Biopharmaceuticals")
    assert match is None


def test_match_company_to_ticker_openfigi_returns_none_on_request_failure():
    with patch.object(ticker_match.requests, "post", side_effect=ticker_match.requests.RequestException("boom")):
        match = match_company_to_ticker_openfigi("Day One Biopharmaceuticals")
    assert match is None


def _yahoo_response_for(symbol_to_name: dict) -> _FakeResponse:
    return _FakeResponse(
        {
            "quotes": [
                {"symbol": symbol, "shortname": name}
                for symbol, name in symbol_to_name.items()
            ]
        }
    )


def test_resolve_ticker_corrects_eisai_via_openfigi_fallback():
    """End-to-end golden case: SEC's fuzzy match alone gets this wrong
    (HSAI/Hesai Group). resolve_ticker() must not surface that — it should
    fail verification, fall back to OpenFIGI, and land on Eisai's real ADR.

    ticker_match and ticker_verify both do a bare `import requests`, so
    they share the exact same module object — patching requests.get once
    covers every GET either module makes (SEC's ticker list, Yahoo, and
    the SEC EDGAR full-text fallback) rather than needing separate patches
    that would silently shadow each other.
    """
    from signal_screener.matching import ticker_verify

    openfigi_candidates = {
        "data": [
            {
                "figi": "EISAI1",
                "name": "Eisai Co., Ltd.",
                "ticker": "ESAIY",
                "exchCode": "US",
                "securityType": "ADR",
                "marketSector": "Equity",
            }
        ]
    }

    def fake_get(url, params=None, headers=None, timeout=None):
        if url == ticker_match.SEC_TICKERS_URL:
            return _FakeResponse(SEC_FIXTURE)
        if url == ticker_verify.YAHOO_SEARCH_URL:
            q = params["q"]
            if q == "HSAI":
                return _yahoo_response_for({"HSAI": "Hesai Group"})
            if q == "ESAIY":
                return _yahoo_response_for({"ESAIY": "Eisai Co., Ltd."})
            return _FakeResponse({"quotes": []})
        assert url == ticker_verify.SEC_FULLTEXT_SEARCH_URL
        return _FakeResponse({"hits": {"hits": []}})

    with patch.object(ticker_match.requests, "get", side_effect=fake_get):
        with patch.object(ticker_match.requests, "post", return_value=_FakeResponse(openfigi_candidates)):
            match, verification = resolve_ticker("Eisai")

    assert match.ticker == "ESAIY"
    assert match.ticker != "HSAI"
    assert verification.verified is True


def test_resolve_ticker_resolves_bare_ticker_to_exchange_suffixed_symbol():
    """End-to-end golden case for Tier 2 international companies: SEC has
    no match at all (foreign company), OpenFIGI returns a bare home-market
    ticker ("ZAL"), and Yahoo only has it under an exchange-suffixed
    symbol ("ZAL.DE") — resolve_ticker() must come back with that
    suffixed symbol as match.ticker, not the bare guess nothing else in
    the pipeline (site links, price fetches) can actually use."""
    from signal_screener.matching import ticker_verify

    openfigi_candidates = {
        "data": [
            {
                "figi": "DE1",
                "name": "ZALANDO SE",
                "ticker": "ZAL",
                "exchCode": "GY",
                "securityType": "Common Stock",
                "marketSector": "Equity",
            }
        ]
    }

    def fake_get(url, params=None, headers=None, timeout=None):
        if url == ticker_match.SEC_TICKERS_URL:
            return _FakeResponse(SEC_FIXTURE)  # no Zalando entry -> SEC match is None
        assert url == ticker_verify.YAHOO_SEARCH_URL
        assert params["q"] == "ZAL"
        return _yahoo_response_for({"ZAL.DE": "Zalando SE"})

    with patch.object(ticker_match.requests, "get", side_effect=fake_get):
        with patch.object(ticker_match.requests, "post", return_value=_FakeResponse(openfigi_candidates)):
            match, verification = resolve_ticker("Zalando")

    assert match.ticker == "ZAL.DE"
    assert verification.verified is True
    assert verification.resolved_ticker == "ZAL.DE"


def test_resolve_ticker_flags_delisted_company_distinctly_not_unverified():
    """The reported case: SEC's list has no entry at all for Day One
    Biopharmaceuticals (delisted after its acquisition by Servier), and
    OpenFIGI's fallback surfaces a stale/derivative identifier (its old
    European GDR ticker) rather than recognizing the company is gone.
    resolve_ticker() must come back with delisted_or_acquired=True, not a
    plain unverified result — the match is still the best guess, just
    tagged with the real reason instead of "couldn't verify.\""""
    from signal_screener.matching import ticker_verify

    openfigi_candidates = {
        "data": [
            {
                "figi": "DAWNGBX1",
                "name": "DAY ONE BIOPHARMACEUTICALS I",
                "ticker": "DAWNGBX",
                "exchCode": "EU",
                "securityType": "Common Stock",
                "marketSector": "Equity",
            }
        ]
    }
    sec_fulltext_hit = _FakeResponse(
        {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "ciks": ["0001845337"],
                            "display_names": [
                                "Day One Biopharmaceuticals, Inc.  (DAWN)  (CIK 0001845337)"
                            ],
                        }
                    }
                ]
            }
        }
    )
    submissions_empty = _FakeResponse({"tickers": [], "exchanges": []})

    def fake_get(url, params=None, headers=None, timeout=None):
        if url == ticker_match.SEC_TICKERS_URL:
            return _FakeResponse(SEC_FIXTURE)  # no Day One entry -> SEC match is None
        if url == ticker_verify.YAHOO_SEARCH_URL:
            return _FakeResponse({"quotes": []})  # DAWNGBX isn't a real listing
        if url == ticker_verify.SEC_FULLTEXT_SEARCH_URL:
            return sec_fulltext_hit
        assert url == ticker_verify.SEC_SUBMISSIONS_URL.format(cik="0001845337")
        return submissions_empty

    with patch.object(ticker_match.requests, "get", side_effect=fake_get):
        with patch.object(ticker_match.requests, "post", return_value=_FakeResponse(openfigi_candidates)):
            match, verification = resolve_ticker("Day One Biopharmaceuticals")

    assert match.ticker == "DAWNGBX"
    assert verification.verified is False
    assert verification.delisted_or_acquired is True
    assert "1845337" in verification.reason
