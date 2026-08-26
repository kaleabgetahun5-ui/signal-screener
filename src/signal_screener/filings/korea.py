"""Tier 2 (brief section 3), South Korea. Source: DART (Data Analysis,
Retrieval and Transfer System), the Financial Supervisory Service's public
disclosure API — https://opendart.fss.or.kr. Free key required (no
unauthenticated fallback, unlike OpenFIGI); see config.py.

Two DART endpoints, both structured JSON (no HTML scraping/windowing
needed here, unlike filings/germany.py):
  - exctvSttus: executive roster per periodic report (name, title,
    responsibilities, registered/unregistered status) — the leadership
    title source.
  - majorstock: 5%+ substantial-holding disclosures, same shape as
    Germany's BaFin AnteileInfo — a threshold-based register, not a full
    ownership snapshot.

DART requires an internal 8-digit corp_code per company, obtained from a
one-time bulk corpCode.xml download (~120k companies) rather than a
name-search endpoint — looked up once and hardcoded below, same pattern as
germany.py's MANAGEMENT_BOARD_URLS.

Real finding building this (Naver): DART's executive-status data already
shows founder Lee Hae-jin (이해진) holding "이사회의장" (Chairman of the
Board) as far back as fiscal year 2015 — the earliest year DART's
structured data covers — the exact same role he holds today. That's not a
recent handoff; brief section 4's Founder-Chair tier is explicitly for a
transition "within the last 24 months," and section 4 already implements
the reverse case as a downgrade to Founder-departed for anything older.
Claude's extraction can't know this from a single current-period excerpt
(there's no "stepped back on X" sentence to find — DART's periodic
executive-status filings just show current officers, not transition
history), so check_role_predates_recency_window() below establishes it
directly from DART's own historical filings instead of leaving it to
inference — the same "verify with real data, don't infer" approach
check_delisted_or_acquired() (matching/ticker_verify.py) already uses.

Also real: neither DART endpoint discloses Lee Hae-jin's ownership
percentage at all (absent from majorstock's 5%+ register, and from
elestock's ownership-*change* reports — no evidence either way beyond "not
above 5%, and no reported change to infer a number from"). Same category
of gap as Zalando's founders — not a scraping failure, an honest
disclosure-threshold gap.
"""

import logging
from datetime import date

import requests

from signal_screener.config import OPENDART_API_KEY

logger = logging.getLogger(__name__)

CORP_CODES = {
    "Naver": "00266961",
}

EXCTV_STTUS_URL = "https://opendart.fss.or.kr/api/exctvSttus.json"
MAJOR_STOCK_URL = "https://opendart.fss.or.kr/api/majorstock.json"

# Annual report only, no need to also try quarterly for this — a decade+
# stale role only needs one confirmed old snapshot to establish "not
# recent," not the most precise one available.
EARLIEST_AVAILABLE_YEAR = "2015"
EARLIEST_REPRT_CODE = "11011"

# Most-recent-first report periods to try for the *current* excerpt —
# DART requires an explicit (year, quarter) pair per request, there's no
# "give me whatever's latest" mode.
_REPRT_CODES = [("11013", "Q1"), ("11012", "H1"), ("11014", "Q3"), ("11011", "Annual")]


def _get_json(url: str, params: dict) -> dict:
    resp = requests.get(url, params={**params, "crtfc_key": OPENDART_API_KEY}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") not in ("000", "013"):  # 013 = "no data found", not an error
        raise RuntimeError(f"DART API error {data.get('status')}: {data.get('message')}")
    return data


def _recent_report_periods() -> list[tuple[str, str]]:
    """(bsns_year, reprt_code) pairs, most-recent-first, covering roughly
    the last 18 months — enough to find whichever period was most recently
    filed regardless of exactly when in the quarter this runs."""
    today = date.today()
    periods = []
    for year_offset in (0, 1):
        year = str(today.year - year_offset)
        for reprt_code, _ in reversed(_REPRT_CODES):
            periods.append((year, reprt_code))
    return periods


def fetch_current_executives(company_name: str) -> list[dict]:
    """The executive roster from whichever recent periodic report is
    actually available — tries periods most-recent-first and returns the
    first non-empty result, since DART has no "latest" shortcut."""
    corp_code = CORP_CODES[company_name]
    for year, reprt_code in _recent_report_periods():
        data = _get_json(
            EXCTV_STTUS_URL, {"corp_code": corp_code, "bsns_year": year, "reprt_code": reprt_code}
        )
        items = data.get("list") or []
        if items:
            return items
    return []


def check_role_predates_recency_window(company_name: str, founder_name_local: str) -> str | None:
    """Queries DART's earliest available annual report (2015) for this
    founder. If they already held a leadership role back then, returns
    that report's fiscal year-end as a real, filing-confirmed "held this
    role since at least this date" anchor — not the actual transition
    date (unknowable from DART's coverage window, which starts in 2015),
    but a true lower bound, which is exactly what the recency rule needs:
    proof the transition happened more than 24 months ago, not a precise
    date for it. Returns None if the founder doesn't appear in that
    earliest report at all (transition may genuinely be recent, or this
    country/company combination just doesn't have that history — either
    way, "no evidence of an old role" rather than a fabricated date).
    """
    corp_code = CORP_CODES[company_name]
    try:
        data = _get_json(
            EXCTV_STTUS_URL,
            {"corp_code": corp_code, "bsns_year": EARLIEST_AVAILABLE_YEAR, "reprt_code": EARLIEST_REPRT_CODE},
        )
    except (requests.RequestException, RuntimeError):
        logger.warning("DART historical exctvSttus lookup failed for %s", company_name)
        return None

    for item in data.get("list") or []:
        if item.get("nm") == founder_name_local:
            return f"{EARLIEST_AVAILABLE_YEAR}-12-31"
    return None


def fetch_major_shareholding(company_name: str, founder_name_local: str) -> dict | None:
    """The founder's most recent 5%+ holding disclosure, if any — same
    threshold-register nature as Germany's BaFin check (module docstring)."""
    corp_code = CORP_CODES[company_name]
    try:
        data = _get_json(MAJOR_STOCK_URL, {"corp_code": corp_code})
    except (requests.RequestException, RuntimeError):
        logger.warning("DART majorstock lookup failed for %s", company_name)
        return None

    matches = [i for i in (data.get("list") or []) if i.get("repror") == founder_name_local]
    if not matches:
        return None
    return max(matches, key=lambda i: i["rcept_dt"])


def fetch_leadership_excerpt(company_name: str, founder_name_local: str) -> str:
    """Builds a plain-English-labeled excerpt from DART's structured JSON
    fields for the same Claude extraction prompt Tier 1/Germany use
    (summarize/founder_extraction.py) — no HTML/windowing needed, DART's
    data already comes back as clean per-executive records. Raises if the
    executive roster itself can't be fetched (the only source of the
    title info the Founder-CEO/Founder-Chair tiers need); the major-
    shareholding half degrades to "not disclosed" instead, same as
    Germany's BaFin fallback.
    """
    if not OPENDART_API_KEY:
        raise RuntimeError("OPENDART_API_KEY is not set (see .env.example)")

    executives = fetch_current_executives(company_name)
    if not executives:
        raise RuntimeError(f"No executive status report found for {company_name!r} in DART")

    founder_row = next((e for e in executives if e.get("nm") == founder_name_local), None)

    lines = [f"DART executive status report for {company_name} (source_country: South Korea):"]
    for e in executives:
        marker = " <- SUBJECT" if e is founder_row else ""
        lines.append(
            f"- {e.get('nm')}: position={e.get('ofcps')!r}, "
            f"registered={e.get('rgist_exctv_at')!r}, standing={e.get('fte_at')!r}, "
            f"responsibilities={e.get('chrg_job')!r}, "
            f"relationship_to_largest_shareholder={e.get('mxmm_shrholdr_relate')!r}{marker}"
        )
    if founder_row is None:
        lines.append(
            f"\n{founder_name_local} does not appear in this executive roster at all — "
            "no active board/executive role found in the current periodic report."
        )

    holding = fetch_major_shareholding(company_name, founder_name_local)
    if holding:
        lines.append(
            f"\nDART substantial-holding disclosure (5%+ threshold register) for "
            f"{founder_name_local}, filed {holding['rcept_dt']}: {holding.get('stkrt')}% "
            f"of shares (reason: {holding.get('report_resn')})."
        )
    else:
        lines.append(
            f"\nNo DART substantial-holding disclosure on file for {founder_name_local} — "
            "either their stake is below the 5% mandatory reporting threshold, or a "
            "recent change simply hasn't been filed."
        )

    return "\n".join(lines)
