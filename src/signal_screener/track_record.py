"""Roadmap step 6 / brief section 8's `tracked_outcomes` table — automatic
track record. Brief: "every time something gets flagged 'High signal,' the
pipeline checks back automatically at 3/6/12 months and records what
actually happened to the price... the only thing that tells you, honestly,
whether the screening logic is any good."

Built ahead of schedule (roadmap step 6 says "once you have your first
batch of flagged entries to actually track") on the reasoning that this is
gated on elapsed time, not effort: a 3-month check-back on something
flagged today can't produce a result before 3 months pass no matter when
the code gets written, so starting the clock now is strictly better than
waiting.

Trigger logic (defined this session, not yet written into the brief):
  - Biotech: an existing "High signal" or "Moderate signal" confidence
    flag from claude_summary.py. "Early stage" is deliberately excluded —
    too early to be worth a track record entry.
  - Founder-led: Founder-CEO + "Established" network effect -> High signal.
    Founder-CEO + "Emerging" -> capped at Moderate signal. Founder-Chair
    -> Moderate signal regardless of network-effect strength.
    Founder-departed, and Founder-CEO + "None identified", trigger
    nothing — neither satisfies both halves of this screener's thesis
    (founder-led *and* network effects).

One row per entry_id, created once at first qualifying flag, and never
overwritten thereafter — even if the flag itself changes on a later run.
A flag flipping after the fact is itself worth a human noticing, not
something to silently paper over by rewriting the original record.
"""

import logging
import time
from calendar import monthrange
from dataclasses import dataclass
from datetime import date

import requests

from signal_screener import db

logger = logging.getLogger(__name__)

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 1.0

# Brief section 3 names EOD Historical Data / Alpha Vantage (paid, keyed)
# as the intended market-data source. This uses Yahoo's unofficial chart
# endpoint instead — free, no key, same family of source
# matching/ticker_verify.py's Yahoo search already relies on elsewhere in
# this codebase, with the same retry-with-backoff lesson learned there
# (PDD Holdings/PDD came back empty on some requests that succeeded moments
# later). Swap this for a keyed provider later if Yahoo proves unreliable
# here too — nothing else in this module depends on which source it is.
PRICE_SOURCE_NAME = "yahoo_finance_chart"

CHECKPOINTS = ("3mo", "6mo", "12mo")

# "Early stage" deliberately excluded — too early in the designation's life
# to be worth a track record entry yet (see module docstring).
TRACKABLE_BIOTECH_FLAGS = ("High signal", "Moderate signal")


@dataclass
class PriceQuote:
    price: float
    currency: str
    fetched_at: str  # ISO date this price is as-of


def fetch_price(ticker: str) -> PriceQuote | None:
    last_exc: requests.RequestException | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            resp = requests.get(
                YAHOO_CHART_URL.format(ticker=ticker),
                params={"interval": "1d", "range": "1d"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            resp.raise_for_status()
            result = (resp.json().get("chart") or {}).get("result") or []
            if result:
                meta = result[0].get("meta") or {}
                price = meta.get("regularMarketPrice")
                if price is not None:
                    return PriceQuote(
                        price=price,
                        currency=meta.get("currency", "USD"),
                        fetched_at=date.today().isoformat(),
                    )
            return None  # request succeeded but no usable price — not worth retrying
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))
    logger.warning("Price fetch failed for %s after %d attempts: %s", ticker, RETRY_ATTEMPTS, last_exc)
    return None


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, monthrange(year, month)[1])  # clamp e.g. Jan 31 + 1mo -> Feb 28
    return date(year, month, day)


def derive_founder_flag(founder_tier: str, network_effect_strength: str | None) -> str | None:
    """See module docstring's trigger logic. Returns None for anything
    that shouldn't get a tracked_outcomes entry."""
    if founder_tier == "Founder-CEO":
        if network_effect_strength == "Established":
            return "High signal"
        if network_effect_strength == "Emerging":
            return "Moderate signal"
        return None
    if founder_tier == "Founder-Chair":
        return "Moderate signal"
    return None


def flag_entry(
    conn,
    *,
    entry_id: str,
    entry_type: str,
    ticker: str,
    flag_given: str,
    date_flagged: str | None = None,
) -> None:
    """Creates a tracked_outcomes row for entry_id if one doesn't already
    exist. Captures price_at_flag now (best-effort — a failed fetch still
    creates the row, per the project's "never silently drop" rule, just
    with price_at_flag left null and the failure noted); the 3/6/12-month
    prices are filled in later by check_due_outcomes()."""
    if db.tracked_outcome_exists(conn, entry_id):
        return

    flagged_date = date.fromisoformat(date_flagged) if date_flagged else date.today()
    quote = fetch_price(ticker)

    db.insert_tracked_outcome(
        conn,
        entry_id=entry_id,
        entry_type=entry_type,
        ticker=ticker,
        date_flagged=flagged_date.isoformat(),
        flag_given=flag_given,
        price_source=PRICE_SOURCE_NAME if quote else None,
        price_at_flag=quote.price if quote else None,
        price_at_flag_date=quote.fetched_at if quote else None,
        check_3mo_due=_add_months(flagged_date, 3).isoformat(),
        check_6mo_due=_add_months(flagged_date, 6).isoformat(),
        check_12mo_due=_add_months(flagged_date, 12).isoformat(),
        notes_on_outcome=None if quote else "Price at flag unavailable — fetch failed when this entry was flagged.",
    )
    logger.info("Tracking outcome for %s (%s, ticker=%s, flag=%s)", entry_id, entry_type, ticker, flag_given)


def check_due_outcomes(conn, *, as_of: str | None = None) -> dict[str, int]:
    """Fills in whichever of price_at_3mo/6mo/12mo are now due and not yet
    recorded. Returns a count of checkpoints filled per period, for the
    CLI to report."""
    as_of_date = as_of or date.today().isoformat()
    filled = {cp: 0 for cp in CHECKPOINTS}
    for checkpoint in CHECKPOINTS:
        due = db.get_due_outcome_checkpoints(conn, checkpoint, as_of_date)
        for row in due:
            quote = fetch_price(row["ticker"])
            if quote is None:
                logger.warning(
                    "Checkpoint %s price fetch failed for outcome_id=%s (%s) — will retry next run",
                    checkpoint,
                    row["outcome_id"],
                    row["ticker"],
                )
                continue
            db.record_outcome_checkpoint(conn, row["outcome_id"], checkpoint, quote.price, quote.fetched_at)
            filled[checkpoint] += 1
    return filled
