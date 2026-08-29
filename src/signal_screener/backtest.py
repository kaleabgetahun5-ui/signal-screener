"""IPO backtest ("$100 at IPO vs. S&P 500") for each founder-led
company's site card — the exact feature site.py's own module docstring
names as deliberately deferred until "the `price_history` table" (or
equivalent data source) exists.

Reuses the same Yahoo chart endpoint track_record.py already relies on
for current price (v8/finance/chart), extended with period1/period2 to
pull historical daily closes around two dates: each company's own IPO
(from the chart meta's firstTradeDate — Yahoo's own record of the first
trading day, the standard free-source proxy for "IPO date," confirmed
live and historically accurate against real IPO dates for MercadoLibre,
Zalando, Tencent, and Adyen) and the S&P 500 (^GSPC) on that same
calendar date, so both legs of the comparison start on the same day.
Prices are Yahoo's regular (split-adjusted) closes, not raw ticks —
confirmed live against Tencent's 2004 IPO, whose real ~HK$3.70 IPO price
comes back adjusted for two decades of stock splits since, which is the
correct input for a total-return comparison like this one.

Presented as a growth-multiple / hypothetical-$100 illustration in each
security's own currency, not an FX-adjusted USD comparison — the
multiple itself (final price / IPO price) is currency-invariant, but
literally holding two "$100 grew to $X" lines side by side for a
non-USD company next to the (USD) S&P 500 line could read as a like-for-
like dollar comparison it isn't. site.py labels this explicitly rather
than silently implying FX-adjustment this project doesn't do.

compute_backtest() is deliberately all-or-nothing: any missing input
(IPO date unknown, no trading data in the historical window, a current-
price fetch failure) returns None rather than a partially-filled result
— unlike valuation.py's per-field degrade, a growth multiple with a
missing numerator or denominator isn't a smaller fact, it's a wrong one.

Re-fetched fresh on every pipeline run rather than cached — the IPO-
date/IPO-price/S&P-price-at-IPO half is a historical fact that never
changes, but re-deriving it every run is a small, bounded cost (three
chart calls per company) against a separate "fetch once, backfill if
still unknown" caching mechanism this project doesn't otherwise use, and
it's the only way the "current price" half of the multiple stays
current — same trade-off valuation.py already made for the same reason.
"""

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone

import requests

logger = logging.getLogger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
SP500_TICKER = "^GSPC"
BACKTEST_SOURCE_NAME = "yahoo_finance_chart"

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 1.0

# Calendar days of daily bars to pull starting at a target date, to find
# the first real trading day's close at/after it — covers a weekend or
# holiday landing exactly on the target without pulling in a whole extra
# week of unrelated data.
WINDOW_DAYS = 7


@dataclass
class BacktestResult:
    ipo_date: str
    company_ipo_price: float
    company_current_price: float
    company_currency: str
    company_growth_multiple: float
    sp500_price_at_ipo: float
    sp500_current_price: float
    sp500_growth_multiple: float
    as_of_date: str
    source: str = BACKTEST_SOURCE_NAME


def _fetch_chart(ticker: str, *, period1: int | None = None, period2: int | None = None) -> dict | None:
    params = {"interval": "1d"}
    if period1 is not None and period2 is not None:
        params["period1"] = period1
        params["period2"] = period2
    else:
        params["range"] = "1d"

    last_exc: requests.RequestException | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            resp = requests.get(
                CHART_URL.format(ticker=ticker),
                params=params,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            resp.raise_for_status()
            result = (resp.json().get("chart") or {}).get("result") or []
            return result[0] if result else None
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))
    logger.warning("Chart fetch failed for %s after %d attempts: %s", ticker, RETRY_ATTEMPTS, last_exc)
    return None


def get_current_price(ticker: str) -> float | None:
    result = _fetch_chart(ticker)
    if result is None:
        return None
    return (result.get("meta") or {}).get("regularMarketPrice")


def get_price_near_date(ticker: str, target_date: str) -> float | None:
    """First real trading day's close at/after target_date (an ISO
    date) — see WINDOW_DAYS. None if the ticker has no trading data in
    that window (shouldn't happen for a real listed ticker on/after its
    own first trade date, but a request failure degrades to this too)."""
    target = datetime.fromisoformat(target_date).replace(tzinfo=timezone.utc)
    period1 = int(target.timestamp())
    period2 = period1 + WINDOW_DAYS * 86400
    result = _fetch_chart(ticker, period1=period1, period2=period2)
    if result is None:
        return None
    closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    for close in closes:
        if close is not None:
            return close
    return None


def compute_backtest(ticker: str, sp500_current_price: float | None) -> BacktestResult | None:
    """sp500_current_price is fetched once per pipeline run by the caller
    (get_current_price(SP500_TICKER)) and passed in here rather than
    re-fetched per company — it's the same value for all 9 candidates in
    a given run, same "fetch once, reuse" pattern as valuation.py's
    session+crumb."""
    if sp500_current_price is None:
        return None

    meta_result = _fetch_chart(ticker)
    if meta_result is None:
        return None
    meta = meta_result.get("meta") or {}
    ipo_timestamp = meta.get("firstTradeDate")
    company_current_price = meta.get("regularMarketPrice")
    currency = meta.get("currency") or "USD"
    if ipo_timestamp is None or company_current_price is None:
        return None
    ipo_date = datetime.fromtimestamp(ipo_timestamp, tz=timezone.utc).date().isoformat()

    company_ipo_price = get_price_near_date(ticker, ipo_date)
    sp500_price_at_ipo = get_price_near_date(SP500_TICKER, ipo_date)
    if company_ipo_price is None or sp500_price_at_ipo is None:
        return None
    if company_ipo_price == 0 or sp500_price_at_ipo == 0:
        return None

    return BacktestResult(
        ipo_date=ipo_date,
        company_ipo_price=company_ipo_price,
        company_current_price=company_current_price,
        company_currency=currency,
        company_growth_multiple=company_current_price / company_ipo_price,
        sp500_price_at_ipo=sp500_price_at_ipo,
        sp500_current_price=sp500_current_price,
        sp500_growth_multiple=sp500_current_price / sp500_price_at_ipo,
        as_of_date=date.today().isoformat(),
    )
