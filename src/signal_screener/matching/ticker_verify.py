"""Cross-check a ticker match against a second, independent source before
it's ever used downstream.

Project brief, pipeline step 3: this check is mandatory for every matched
ticker, every run — not just when a match looks uncertain. If verification
fails or is ambiguous, the caller must record the entry as "unverified" and
keep it visible rather than dropping it or trusting it silently. This
module only answers the yes/no verification question; the pipeline decides
what to do with the answer.

Yahoo's search endpoint is unofficial and unreliable — it's been observed
returning no listing for real, unambiguous tickers (PDD Holdings/PDD) on
requests that succeed moments later. So every external call here retries
with backoff before being treated as a real "not found," and if Yahoo still
comes back empty/failed after retries, SEC EDGAR full-text search is a
second, independent fallback before the ticker is ever marked unverified.

Name comparison uses token_set_ratio, not token_sort_ratio: a short base
name (e.g. "Eisai", as it appears in a designation record) against its own
canonical registered name ("Eisai Co., Ltd.") scores only 59 on
token_sort_ratio — the two extra suffix tokens drag down a whole-string
edit-distance ratio out of proportion to a real short name, which fails
even the *correct* ticker at MIN_VERIFY_SCORE=70. token_set_ratio scores
that same true positive 100 (it credits "Eisai" being a clean subset of the
other name) while still scoring the real false positive this threshold
exists to catch — "Eisai" vs "Hesai Group" — at 50, same as before.
"""

import re
import time
from dataclasses import dataclass
from datetime import date

import requests
from rapidfuzz import fuzz, utils

from signal_screener.config import SEC_USER_AGENT

YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
SEC_FULLTEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# Raised from 60: at 60, shared generic words (e.g. "Pharmaceuticals") were
# enough to falsely confirm a wrong company. This is the safety-net check,
# so it should be stricter than the primary match, not looser.
MIN_VERIFY_SCORE = 70

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 1.0

# SEC EDGAR full-text search result "display_names" look like
# 'Day One Biopharmaceuticals, Inc.  (DAWN)  (CIK 0001845337)' — this pulls
# the parenthesized ticker out of that string.
_DISPLAY_NAME_TICKER_RE = re.compile(r"\(([A-Z][A-Z.\-]{0,9})\)")


@dataclass
class VerificationResult:
    verified: bool
    source: str
    checked_date: str
    reason: str
    # Brief section 4: listing status must be re-checked every run — a
    # company can stop being a live, tradable ticker (acquired, delisted,
    # gone private) after a designation/candidacy was recorded, without the
    # original match ever having been wrong. Distinct from verified=False's
    # usual meaning ("couldn't confirm this match"): this means the match
    # was likely right, and we know *why* it's not currently verifiable as
    # an active listing. See check_delisted_or_acquired().
    delisted_or_acquired: bool = False
    # Set only when Yahoo confirmed the company under an exchange-suffixed
    # symbol the input ticker didn't have (e.g. input "ZAL", Yahoo's real
    # symbol "ZAL.DE") — see _verify_via_yahoo's base-ticker fallback,
    # added for Tier 2 international companies. matching/resolve.py
    # substitutes this back in as the ticker actually used downstream
    # (site links, price fetches) once the plain, unsuffixed guess
    # OpenFIGI/ticker_match.py returns wouldn't otherwise resolve anywhere.
    resolved_ticker: str | None = None


def _get_json_with_retry(url: str, *, params: dict, headers: dict, timeout: int) -> dict:
    """GET url as JSON, retrying transient failures with exponential backoff.
    Re-raises the last exception if every attempt fails."""
    last_exc: requests.RequestException | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))
    raise last_exc


def _fetch_yahoo_quotes(ticker: str) -> list[dict]:
    """Retries on both request failures AND a successful-but-empty result:
    PDD Holdings/PDD — an unambiguous, correct ticker — was observed getting
    an empty quotes list from this endpoint on requests that returned real
    results moments later, so an empty first response isn't trusted as a
    real "not found" until it repeats across every retry."""
    last_exc: requests.RequestException | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            resp = requests.get(
                YAHOO_SEARCH_URL,
                params={"q": ticker},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            resp.raise_for_status()
            quotes = resp.json().get("quotes", [])
            if quotes or attempt == RETRY_ATTEMPTS - 1:
                return quotes
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == RETRY_ATTEMPTS - 1:
                raise
        time.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))
    raise last_exc  # unreachable given the loop above, satisfies type checkers


def _verify_via_yahoo(ticker: str, expected_company_name: str, checked_date: str) -> VerificationResult:
    source = "yahoo_finance_search"
    try:
        quotes = _fetch_yahoo_quotes(ticker)
    except requests.RequestException as exc:
        return VerificationResult(
            verified=False,
            source=source,
            checked_date=checked_date,
            reason=f"verification request failed after {RETRY_ATTEMPTS} attempts: {exc}",
        )

    exact_symbol_matches = [q for q in quotes if q.get("symbol", "").upper() == ticker.upper()]
    resolved_ticker = None
    candidates = exact_symbol_matches

    if not candidates:
        # Base-ticker fallback for non-US listings: matching/ticker_match.py's
        # OpenFIGI path (Tier 2 international companies) returns a bare
        # home-market ticker ("ZAL"), but Yahoo's real symbol for a non-US
        # listing is exchange-suffixed ("ZAL.DE") — an exact-match-only
        # check fails every single Tier 2 company for a reason that has
        # nothing to do with whether the match is right. A symbol is
        # accepted here only if its part before the first "." matches the
        # input exactly, so "ZAL.DE"/"ZAL.HM" match ticker "ZAL" but
        # "ZALN.MU" (a different suffix on the base itself) does not.
        base_matches = [
            q for q in quotes if q.get("symbol", "").upper().split(".")[0] == ticker.upper()
        ]
        if base_matches:
            candidates = base_matches

    if not candidates:
        return VerificationResult(
            verified=False,
            source=source,
            checked_date=checked_date,
            reason=f"no listing found for symbol {ticker!r}",
        )

    best = max(
        candidates,
        key=lambda q: fuzz.token_set_ratio(
            expected_company_name,
            q.get("shortname") or q.get("longname") or "",
            processor=utils.default_process,
        ),
    )
    best_name_score = fuzz.token_set_ratio(
        expected_company_name,
        best.get("shortname") or best.get("longname") or "",
        processor=utils.default_process,
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

    if candidates is not exact_symbol_matches:
        resolved_ticker = best.get("symbol")

    return VerificationResult(
        verified=True,
        source=source,
        checked_date=checked_date,
        reason=f"symbol and company name confirmed (score={best_name_score:.0f})"
        + (f" — resolved to {resolved_ticker!r}" if resolved_ticker else ""),
        resolved_ticker=resolved_ticker,
    )


def _verify_via_sec_edgar(ticker: str, expected_company_name: str, checked_date: str) -> VerificationResult:
    source = "sec_edgar_fulltext_search"
    try:
        data = _get_json_with_retry(
            SEC_FULLTEXT_SEARCH_URL,
            params={"q": f'"{expected_company_name}"'},
            headers={"User-Agent": SEC_USER_AGENT},
            timeout=15,
        )
    except requests.RequestException as exc:
        return VerificationResult(
            verified=False,
            source=source,
            checked_date=checked_date,
            reason=f"verification request failed after {RETRY_ATTEMPTS} attempts: {exc}",
        )

    hits = data.get("hits", {}).get("hits", [])
    for hit in hits:
        for display_name in hit.get("_source", {}).get("display_names", []):
            m = _DISPLAY_NAME_TICKER_RE.search(display_name)
            if m is None or m.group(1).upper() != ticker.upper():
                continue
            filer_name = display_name.split("(")[0].strip()
            score = fuzz.token_set_ratio(
                expected_company_name, filer_name, processor=utils.default_process
            )
            if score >= MIN_VERIFY_SCORE:
                return VerificationResult(
                    verified=True,
                    source=source,
                    checked_date=checked_date,
                    reason=(
                        f"ticker {ticker!r} found on SEC filer {filer_name!r} "
                        f"in EDGAR full-text search (score={score:.0f})"
                    ),
                )

    return VerificationResult(
        verified=False,
        source=source,
        checked_date=checked_date,
        reason=f"no SEC EDGAR filing associates {ticker!r} with {expected_company_name!r}",
    )


def _find_cik_by_name(company_name: str, checked_date: str) -> tuple[str, str] | None:
    """Look up a CIK via the same SEC EDGAR full-text search endpoint
    _verify_via_sec_edgar uses, but matched purely on company name rather
    than a ticker — company name is all check_delisted_or_acquired() has to
    go on when the ticker in hand (e.g. an OpenFIGI-derived one like
    DAWNGBX) isn't itself an SEC-registered symbol. Returns (cik, filer's
    real registered name) for the best-scoring hit, or None if nothing
    scores high enough to trust — most searches return hits that merely
    *mention* the company (a competitor, a licensing partner), not filings
    *by* it, so this is deliberately as strict as ticker verification."""
    try:
        data = _get_json_with_retry(
            SEC_FULLTEXT_SEARCH_URL,
            params={"q": f'"{company_name}"'},
            headers={"User-Agent": SEC_USER_AGENT},
            timeout=15,
        )
    except requests.RequestException:
        return None

    hits = data.get("hits", {}).get("hits", [])
    for hit in hits:
        source = hit.get("_source", {})
        ciks = source.get("ciks") or []
        for display_name in source.get("display_names", []):
            if not ciks:
                continue
            filer_name = display_name.split("(")[0].strip()
            score = fuzz.token_set_ratio(company_name, filer_name, processor=utils.default_process)
            if score >= MIN_VERIFY_SCORE:
                return ciks[0], filer_name
    return None


def check_delisted_or_acquired(company_name: str) -> VerificationResult | None:
    """Confirms whether company_name is a real SEC filer that currently has
    no active ticker/exchange on record — SEC drops both from a filer's
    submissions once it deregisters (acquired, gone private, delisted),
    even though its filing history stays public. That's a reliable, checkable
    signal distinct from "couldn't verify this match" (matching/
    ticker_match.py's OpenFIGI fallback can still surface a stale/derivative
    identifier — e.g. Day One Biopharmaceuticals' European GDR ticker
    DAWNGBX, after its $2.5B acquisition by Servier — for a company that's
    genuinely gone).

    Returns None if company_name doesn't resolve to a confident SEC filer
    match at all (this check only applies to past/current SEC filers), so
    callers should treat None as "inconclusive," not "still active."
    """
    checked_date = date.today().isoformat()
    found = _find_cik_by_name(company_name, checked_date)
    if found is None:
        return None
    cik, filer_name = found

    try:
        data = _get_json_with_retry(
            SEC_SUBMISSIONS_URL.format(cik=str(int(cik)).zfill(10)),
            params={},
            headers={"User-Agent": SEC_USER_AGENT},
            timeout=15,
        )
    except requests.RequestException:
        return None

    if data.get("tickers") or data.get("exchanges"):
        return None  # still has an active ticker/exchange on record

    return VerificationResult(
        verified=False,
        source="sec_edgar_submissions",
        checked_date=checked_date,
        reason=(
            f"{filer_name!r} (CIK {cik}) is a real SEC filer with no active "
            f"ticker or exchange currently on record — likely delisted, "
            f"acquired, or taken private since this record was created"
        ),
        delisted_or_acquired=True,
    )


def resolve_arbitrary_ticker(ticker: str) -> tuple[VerificationResult, str | None, str | None]:
    """For the personal watchlist's "add an outside ticker" case: there's
    no expected_company_name to check verify_ticker() against here — the
    company name is exactly the thing this is trying to discover, not
    something already known and being confirmed. So this looks the ticker
    up directly on Yahoo (same source, same exact/base-symbol matching as
    _verify_via_yahoo above, just without the name-comparison step that
    needs a name in hand first) and reports whatever it finds — a real
    typo like "MADEUPTICKER123" fails here for having no listing at all,
    the same never-guess guardrail as everywhere else in this project,
    just checking a different fact (does this symbol exist) than
    verify_ticker checks (does this symbol match this specific company).

    Returns (verification_result, resolved_ticker, resolved_company_name).
    resolved_ticker is always the canonical Yahoo symbol on success (e.g.
    input "meli" -> "MELI", input "rhm" -> "RHM.DE") — the caller should
    store that, not the raw input, so it's guaranteed to be the same
    ticker every downstream link (price, digest, site) actually resolves
    against. Both resolved_* are None when verified is False.
    """
    checked_date = date.today().isoformat()
    source = "yahoo_finance_search"
    try:
        quotes = _fetch_yahoo_quotes(ticker)
    except requests.RequestException as exc:
        return (
            VerificationResult(
                verified=False,
                source=source,
                checked_date=checked_date,
                reason=f"verification request failed after {RETRY_ATTEMPTS} attempts: {exc}",
            ),
            None,
            None,
        )

    candidates = [q for q in quotes if q.get("symbol", "").upper() == ticker.upper()]
    if not candidates:
        # Same non-US base-ticker fallback as _verify_via_yahoo — see its
        # comment for why ("ZAL" -> "ZAL.DE" is a real match, "ZALN.MU" is
        # not).
        candidates = [
            q for q in quotes if q.get("symbol", "").upper().split(".")[0] == ticker.upper()
        ]

    if not candidates:
        return (
            VerificationResult(
                verified=False,
                source=source,
                checked_date=checked_date,
                reason=f"no listing found for symbol {ticker!r}",
            ),
            None,
            None,
        )

    best = candidates[0]
    resolved_symbol = best.get("symbol") or ticker
    resolved_name = best.get("shortname") or best.get("longname") or resolved_symbol

    return (
        VerificationResult(
            verified=True,
            source=source,
            checked_date=checked_date,
            reason=f"resolved {ticker!r} to {resolved_symbol!r} ({resolved_name!r})",
            resolved_ticker=(
                resolved_symbol if resolved_symbol.upper() != ticker.upper() else None
            ),
        ),
        resolved_symbol,
        resolved_name,
    )


def verify_ticker(ticker: str, expected_company_name: str) -> VerificationResult:
    checked_date = date.today().isoformat()

    yahoo_result = _verify_via_yahoo(ticker, expected_company_name, checked_date)
    if yahoo_result.verified:
        return yahoo_result

    sec_result = _verify_via_sec_edgar(ticker, expected_company_name, checked_date)
    if sec_result.verified:
        return sec_result

    return VerificationResult(
        verified=False,
        source=f"{yahoo_result.source}+{sec_result.source}",
        checked_date=checked_date,
        reason=f"yahoo: {yahoo_result.reason}; sec_edgar: {sec_result.reason}",
    )
