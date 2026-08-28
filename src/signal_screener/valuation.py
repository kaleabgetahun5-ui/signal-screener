"""Market valuation snapshot (market cap, P/E, 52-week range, beta,
dividend yield) for each founder-led company's site card.

Yahoo's chart endpoint (track_record.py, already used for price) and
search endpoint (matching/ticker_verify.py, already used for ticker
verification) don't carry any of these fields at all — confirmed live by
checking their actual response keys before building this. The fields
live in Yahoo's quoteSummary endpoint instead, which — unlike those two —
now requires a session cookie + crumb token even for an unauthenticated
caller (confirmed live: a bare request 401s with "Invalid Crumb"). The
cookie+crumb dance below is the same unofficial workaround every
yfinance-style library uses: GET fc.yahoo.com for a session cookie, then
GET v1/test/getcrumb with that cookie for a crumb, then pass both on the
real request.

get_session_and_crumb() is meant to be called once per pipeline run and
its result reused across every candidate — not once per ticker, which
would be 9x the round trips for a token that doesn't expire mid-run.

Same never-block philosophy as track_record.fetch_price(): a failed
cookie/crumb dance or a failed per-ticker quoteSummary call degrades to
"no valuation data" for that company rather than failing the whole
pipeline run — market cap/P/E are a card enrichment, not a fact this
project's core screening logic (founder tier, network effect) depends on.
"""

import logging
import time
from dataclasses import dataclass
from datetime import date

import requests

logger = logging.getLogger(__name__)

CRUMB_COOKIE_URL = "https://fc.yahoo.com"
CRUMB_URL = "https://query2.finance.yahoo.com/v1/test/getcrumb"
QUOTE_SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
QUOTE_SUMMARY_MODULES = "summaryDetail,price"

VALUATION_SOURCE_NAME = "yahoo_finance_quotesummary"

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 1.0


@dataclass
class ValuationMetrics:
    market_cap: float | None
    currency: str | None
    trailing_pe: float | None
    forward_pe: float | None
    fifty_two_week_low: float | None
    fifty_two_week_high: float | None
    beta: float | None
    # A percentage (1.18 meaning 1.18%), not Yahoo's raw fraction (0.0118)
    # — converted here to match this project's existing convention for a
    # stored percentage (see Ownership.ownership_pct).
    dividend_yield_pct: float | None
    as_of_date: str
    source: str = VALUATION_SOURCE_NAME


def get_session_and_crumb() -> tuple[requests.Session, str] | None:
    """Once-per-run setup — see module docstring. Returns None (not an
    exception) on failure, so a caller can degrade the whole run to "no
    valuation data" rather than crash the pipeline over an enrichment."""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    last_exc: requests.RequestException | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            session.get(CRUMB_COOKIE_URL, timeout=15)
            resp = session.get(CRUMB_URL, timeout=15)
            resp.raise_for_status()
            crumb = resp.text.strip()
            if crumb and "Invalid" not in crumb:
                return session, crumb
            return None  # request succeeded but no usable crumb — not worth retrying
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))
    logger.warning("Yahoo cookie/crumb setup failed after %d attempts: %s", RETRY_ATTEMPTS, last_exc)
    return None


def _raw(field: dict | None) -> float | None:
    """Yahoo wraps every numeric value as {"raw": ..., "fmt": "..."} — and
    as an empty {} when the company doesn't have that metric at all (e.g.
    dividendYield for a company that's never paid one, confirmed live
    against MercadoLibre/Adyen). Both "field missing entirely" and "field
    present but empty" collapse to None here — this project never
    fabricates a 0 for "no dividend" vs. "unknown dividend," so
    downstream code must treat None as "not disclosed," not "zero.\""""
    if not field:
        return None
    return field.get("raw")


def fetch_valuation_metrics(
    session: requests.Session, crumb: str, ticker: str
) -> ValuationMetrics | None:
    last_exc: requests.RequestException | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            resp = session.get(
                QUOTE_SUMMARY_URL.format(ticker=ticker),
                params={"modules": QUOTE_SUMMARY_MODULES, "crumb": crumb},
                timeout=15,
            )
            resp.raise_for_status()
            results = (resp.json().get("quoteSummary") or {}).get("result") or []
            if not results:
                return None  # ticker not found on this endpoint — not worth retrying
            data = results[0]
            summary = data.get("summaryDetail") or {}
            price = data.get("price") or {}

            dividend_yield_fraction = _raw(summary.get("dividendYield"))
            return ValuationMetrics(
                market_cap=_raw(summary.get("marketCap")) or _raw(price.get("marketCap")),
                currency=price.get("currency"),
                trailing_pe=_raw(summary.get("trailingPE")),
                forward_pe=_raw(summary.get("forwardPE")),
                fifty_two_week_low=_raw(summary.get("fiftyTwoWeekLow")),
                fifty_two_week_high=_raw(summary.get("fiftyTwoWeekHigh")),
                beta=_raw(summary.get("beta")),
                dividend_yield_pct=(
                    dividend_yield_fraction * 100 if dividend_yield_fraction is not None else None
                ),
                as_of_date=date.today().isoformat(),
            )
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))
    logger.warning(
        "Valuation fetch failed for %s after %d attempts: %s", ticker, RETRY_ATTEMPTS, last_exc
    )
    return None
