"""Fuzzy-match a company name (as it appears in an FDA designation record)
to a public ticker, using SEC EDGAR's public company/ticker list.

Brief note (project brief, pipeline step 2): "fuzzy matching — expect manual
curation early on." This module returns its best guess plus a confidence
score; it never claims certainty. ticker_verify.py is the mandatory
second-source check that runs on every match before it's trusted.

SEC's company_tickers.json only covers US-registered filers, which misses
two real categories found in production: non-US companies with no US-
registered ticker (e.g. Eisai — its real ADR ESAIY trades OTC and isn't in
this file at all, so the fuzzy matcher was scoring against unrelated SEC
names and landed on "Hesai Group"/HSAI, a coincidental near-anagram), and
companies recently delisted/acquired (e.g. Day One Biopharmaceuticals/DAWN,
acquired by Servier in 2026 — SEC drops a filer from this file once it's no
longer an active registrant, even though the designation being processed
predates the acquisition). match_company_to_ticker_openfigi() below is the
fallback for both cases; matching/resolve.py decides when to use it.
"""

import re
from dataclasses import dataclass

import requests
from rapidfuzz import fuzz, process, utils

from signal_screener.config import OPENFIGI_API_KEY, SEC_USER_AGENT

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
OPENFIGI_SEARCH_URL = "https://api.openfigi.com/v3/search"

# Security types OpenFIGI's search returns that actually represent "a
# company's stock" rather than a derivative referencing one — options,
# warrants, and crypto all show up in results for a plain name search and
# would otherwise dominate/pollute the candidate list.
_OPENFIGI_EQUITY_SECURITY_TYPES = {"Common Stock", "REIT", "ADR", "Depositary Receipt"}


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


def match_company_to_ticker_openfigi(company_name: str) -> TickerMatch | None:
    """Fallback matcher for companies match_company_to_ticker() can't place
    (not in SEC's US-filer list at all) or placed wrong (matched but failed
    ticker_verify.py's check) — see module docstring. Uses OpenFIGI's search
    API, which indexes global listings including OTC ADRs and delisted/
    acquired securities that SEC's file omits. Best-effort like its SEC
    counterpart: returns its best guess plus a confidence score, never a
    claim of certainty — matching/resolve.py still runs this through
    ticker_verify.py before trusting it.
    """
    headers = {"Content-Type": "application/json"}
    if OPENFIGI_API_KEY:
        headers["X-OPENFIGI-APIKEY"] = OPENFIGI_API_KEY

    try:
        resp = requests.post(
            OPENFIGI_SEARCH_URL,
            json={"query": company_name},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        candidates = resp.json().get("data", [])
    except requests.RequestException:
        return None

    equity_candidates = [
        c
        for c in candidates
        if c.get("marketSector") == "Equity"
        and c.get("securityType") in _OPENFIGI_EQUITY_SECURITY_TYPES
        and c.get("ticker")
        and c.get("name")
    ]
    if not equity_candidates:
        return None

    scored = [
        (c, fuzz.token_sort_ratio(company_name, c["name"], processor=_normalize_for_matching))
        for c in equity_candidates
    ]
    scored = [(c, score) for c, score in scored if score >= MIN_MATCH_SCORE]
    if not scored:
        return None

    # Tie-break toward the primary US listing when the top score is shared —
    # a foreign issuer's GDR/secondary listing scores identically to its US
    # ADR on name alone (confirmed against real data: "Eisai" search returns
    # 70+ equally-scored "EISAI CO LTD" listings across a dozen exchanges).
    # Shortest-ticker alone isn't a safe tie-break here — unlike the SEC
    # warrant-vs-common-stock case this comment used to reference, OpenFIGI's
    # results span many exchanges, and a short non-US listing code (e.g.
    # "EII" on exchCode "LU") can be shorter than the real US ADR ticker
    # ("ESAIY") it should lose to. Prefer exchCode "US" and the primary/
    # composite record (compositeFIGI == figi) first — the two downstream
    # verification sources (Yahoo, SEC EDGAR) are both US-centric, so a
    # non-US listing can never actually get verified even when it's the
    # right company.
    best_score = max(score for _, score in scored)
    best_candidates = [c for c, score in scored if score == best_score]

    def _listing_priority(c: dict) -> tuple[int, int]:
        is_us = c.get("exchCode") == "US"
        is_composite = c.get("compositeFIGI") == c.get("figi")
        rank = 0 if (is_us and is_composite) else 1 if is_us else 2 if is_composite else 3
        return (rank, len(c["ticker"]))

    best = min(best_candidates, key=_listing_priority)

    return TickerMatch(ticker=best["ticker"], matched_company_name=best["name"], confidence=best_score)
