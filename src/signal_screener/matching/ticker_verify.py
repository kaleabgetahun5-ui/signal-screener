"""Cross-check a ticker match against a second, independent source before
it's ever used downstream.

Project brief, pipeline step 3: this check is mandatory for every matched
ticker, every run — not just when a match looks uncertain. If verification
fails or is ambiguous, the caller must record the entry as "unverified" and
keep it visible rather than dropping it or trusting it silently. This
module only answers the yes/no verification question; the pipeline decides
what to do with the answer.
"""

from dataclasses import dataclass
from datetime import date

import requests
from rapidfuzz import fuzz, utils

YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"

# Raised from 60: at 60, shared generic words (e.g. "Pharmaceuticals") were
# enough to falsely confirm a wrong company. This is the safety-net check,
# so it should be stricter than the primary match, not looser.
MIN_VERIFY_SCORE = 70


@dataclass
class VerificationResult:
    verified: bool
    source: str
    checked_date: str
    reason: str


def verify_ticker(ticker: str, expected_company_name: str) -> VerificationResult:
    checked_date = date.today().isoformat()
    source = "yahoo_finance_search"

    try:
        resp = requests.get(
            YAHOO_SEARCH_URL,
            params={"q": ticker},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        resp.raise_for_status()
        quotes = resp.json().get("quotes", [])
    except requests.RequestException as exc:
        return VerificationResult(
            verified=False,
            source=source,
            checked_date=checked_date,
            reason=f"verification request failed: {exc}",
        )

    exact_symbol_matches = [q for q in quotes if q.get("symbol", "").upper() == ticker.upper()]
    if not exact_symbol_matches:
        return VerificationResult(
            verified=False,
            source=source,
            checked_date=checked_date,
            reason=f"no listing found for symbol {ticker!r}",
        )

    best_name_score = max(
        fuzz.token_sort_ratio(
            expected_company_name,
            q.get("shortname") or q.get("longname") or "",
            processor=utils.default_process,
        )
        for q in exact_symbol_matches
    )
    if best_name_score < MIN_VERIFY_SCORE:
        return VerificationResult(
            verified=False,
            source=source,
            checked_date=checked_date,
            reason=(
                f"symbol {ticker!r} exists but listed name doesn't match "
                f"{expected_company_name!r} closely enough (score={best_name_score:.0f})"
            ),
        )

    return VerificationResult(
        verified=True,
        source=source,
        checked_date=checked_date,
        reason=f"symbol and company name confirmed (score={best_name_score:.0f})",
    )
