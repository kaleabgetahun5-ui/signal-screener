"""Fuzzy-match a company name (as it appears in an FDA designation record)
to a public ticker, using SEC EDGAR's public company/ticker list.

Brief note (project brief, pipeline step 2): "fuzzy matching — expect manual
curation early on." This module returns its best guess plus a confidence
score; it never claims certainty. ticker_verify.py is the mandatory
second-source check that runs on every match before it's trusted.
"""

import re
from dataclasses import dataclass

import requests
from rapidfuzz import fuzz, process, utils

from signal_screener.config import SEC_USER_AGENT

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def placeholder_ticker(company_name: str) -> str:
    """Stand-in ticker for a company with no verified match, so it stays
    visible in the companies table instead of being silently dropped."""
    slug = re.sub(r"[^A-Z0-9]+", "-", company_name.upper()).strip("-")
    return f"UNVERIFIED::{slug}"

# Below this fuzzy-match score (0-100), don't even offer a guess.
MIN_MATCH_SCORE = 75

# Legal suffixes and generic industry words. Left in, they dominate the
# match score for any two companies that happen to share them (e.g. two
# unrelated "___ Pharmaceuticals Inc" get scored mostly on "Pharmaceuticals
# Inc") which surfaced as a real false match during testing: "Vertex
# Pharmaceuticals" outscored against "Telix Pharmaceuticals Ltd" ahead of
# the actual match. Stripping them re-weights the score toward the part of
# the name that actually distinguishes the company. ticker_verify.py
# deliberately does NOT strip these — it compares full names as an
# independent, stricter check on whatever this module guesses.
_DROP_WORDS = {
    "inc", "incorporated", "ltd", "limited", "llc", "corp", "corporation",
    "co", "company", "holdings", "holding", "group", "plc", "the", "ma",
    "pharmaceuticals", "pharmaceutical", "biopharmaceuticals", "biopharmaceutical",
    "therapeutics", "therapeutic", "biosciences", "bioscience", "pharma", "bio",
    "sciences", "science",
}


def _normalize_for_matching(name: str) -> str:
    processed = utils.default_process(name)
    tokens = [t for t in processed.split() if t not in _DROP_WORDS]
    return " ".join(tokens) if tokens else processed


@dataclass
class TickerMatch:
    ticker: str
    matched_company_name: str
    confidence: float  # 0-100 fuzzy match score


_raw_sec_entries: list[dict] | None = None
_ticker_cache: dict[str, tuple[str, str]] | None = None  # name -> (ticker, canonical_name)
_cik_cache: dict[str, str] | None = None  # ticker -> zero-padded 10-digit CIK


def _load_raw_sec_entries() -> list[dict]:
    global _raw_sec_entries
    if _raw_sec_entries is not None:
        return _raw_sec_entries

    resp = requests.get(
        SEC_TICKERS_URL,
        headers={"User-Agent": SEC_USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    _raw_sec_entries = list(resp.json().values())
    return _raw_sec_entries


def _load_sec_company_list() -> dict[str, tuple[str, str]]:
    global _ticker_cache
    if _ticker_cache is not None:
        return _ticker_cache

    # A single company can appear multiple times under the identical title
    # for different listed securities (e.g. "Grab Holdings Ltd" lists both
    # GRAB common stock and GRABW warrants under that exact title) — a
    # plain dict comprehension silently keeps whichever happens to come
    # last in SEC's JSON, which returned warrants instead of common stock
    # for Grab during testing. Keep the shortest ticker for a given title
    # instead: derivative securities (warrants/units/rights) consistently
    # append characters to the base ticker, so shortest is the common stock.
    _ticker_cache = {}
    for entry in _load_raw_sec_entries():
        title, ticker = entry["title"], entry["ticker"]
        existing = _ticker_cache.get(title)
        if existing is None or len(ticker) < len(existing[0]):
            _ticker_cache[title] = (ticker, title)
    return _ticker_cache


def get_cik_for_ticker(ticker: str) -> str | None:
    """Zero-padded 10-digit CIK for a ticker, per SEC EDGAR's own list —
    used to look up a company's actual filings (see filings/sec_edgar.py)."""
    global _cik_cache
    if _cik_cache is None:
        _cik_cache = {
            entry["ticker"].upper(): f"{entry['cik_str']:010d}"
            for entry in _load_raw_sec_entries()
        }
    return _cik_cache.get(ticker.upper())


def match_company_to_ticker(company_name: str) -> TickerMatch | None:
    """Best-effort fuzzy match. Returns None if nothing clears MIN_MATCH_SCORE."""
    company_list = _load_sec_company_list()

    result = process.extractOne(
        company_name,
        company_list.keys(),
        scorer=fuzz.token_sort_ratio,
        processor=_normalize_for_matching,
    )
    if result is None:
        return None

    matched_name, score, _ = result
    if score < MIN_MATCH_SCORE:
        return None

    ticker, canonical_name = company_list[matched_name]
    return TickerMatch(ticker=ticker, matched_company_name=canonical_name, confidence=score)
