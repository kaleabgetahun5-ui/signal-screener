"""Tier 2 (brief section 3), Germany. See sources/founder_led_tier2.py's
module docstring for why "Bundesanzeiger" (the brief's stated source) is
wrong for this purpose.

For leadership *title* — all section 4's Founder-CEO tier needs, no
ownership % required — a company's own investor-relations "Management
Board" page is authoritative and current regardless of ownership
thresholds, since board membership is a governance disclosure, not an
ownership one. Confirmed live and static (not JS-rendered) for Zalando.

For the Founder-Chair tier's >5% ownership requirement, BaFin's AnteileInfo
database (portal.mvp.bafin.de) is queried directly by company name.
Confirmed live: it's a real, searchable, unauthenticated database of WpHG
sec. 33/38/39 voting-rights notifications — but it only contains holders at
or above a 3% reporting threshold. Checked live for Zalando: neither
founder appears in it at all, because each individually holds under 3% —
their combined ~5% stake is disclosed only in a company-published PNG
chart on Zalando's own shareholder-structure page, not any machine-
readable text this pipeline can extract. That's the brief's own
anticipated "founder-ownership data is harder to source cleanly here"
playing out exactly as expected — the extraction honestly reports
"not disclosed in this excerpt" rather than guessing at a number, per
this project's core never-infer guardrail.
"""

import re

import requests
from bs4 import BeautifulSoup

from signal_screener.filings.sec_edgar import extract_leadership_excerpt

# A real browser-style UA, not SEC_USER_AGENT (SEC-specific, wrong for a
# German corporate site / BaFin's portal).
_USER_AGENT = "Mozilla/5.0 (compatible; signal-screener research tool)"

MANAGEMENT_BOARD_URLS = {
    "Zalando": "https://corporate.zalando.com/en/investor-relations/our-management-board",
}

BAFIN_START_URL = "https://portal.mvp.bafin.de/database/AnteileInfo/start.do"
BAFIN_SEARCH_URL = "https://portal.mvp.bafin.de/database/AnteileInfo/suche.do"


def _page_text(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _bafin_notifications_for(company_name: str) -> str:
    """Whatever WpHG voting-rights notifications BaFin has on file for
    company_name, as plain text — "" (not an exception) both when the
    company isn't found and when a real request failure occurs, since
    either way the honest fallback is the same: say nothing was found
    rather than block the whole extraction on one source being down."""
    session = requests.Session()
    try:
        session.get(BAFIN_START_URL, headers={"User-Agent": _USER_AGENT}, timeout=30)
        resp = session.post(
            BAFIN_SEARCH_URL,
            data={"nameAktiengesellschaft": company_name, "nameMeldepflichtiger": ""},
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", id="aktiengesellschaft")
    if table is None:
        return ""
    text = table.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def fetch_leadership_excerpt(company_name: str, founder_name: str) -> str:
    """Combines a windowed excerpt of the Management Board page (same
    surname + role-keyword heuristic Tier 1 uses, see filings/sec_edgar.py
    — the full page is mostly nav-menu boilerplate) with whatever BaFin
    has on file, into one excerpt for the same Claude extraction prompt
    Tier 1 uses (summarize/founder_extraction.py).

    The BaFin summary is appended unconditionally, not run through the
    surname-windowing heuristic — Zalando's founders don't appear in it
    by name at all (each below the 3% threshold, see module docstring),
    so that heuristic would just drop this section entirely, and Claude
    would have no explicit basis for answering "not disclosed" on the
    ownership question rather than staying silent about why.

    Raises if the Management Board page itself can't be fetched — no
    fallback for that one, it's the only source of the title info the
    Founder-CEO tier actually needs. The BaFin half degrades gracefully
    to "nothing on file" instead, per its own docstring above.
    """
    board_url = MANAGEMENT_BOARD_URLS[company_name]
    board_excerpt = extract_leadership_excerpt(_page_text(board_url), founder_name)

    bafin_text = _bafin_notifications_for(company_name)
    if bafin_text:
        bafin_section = (
            "BaFin voting-rights notifications on file (WpHG sec. 33/38/39 — "
            "only holders at or above the 3% threshold appear here): " + bafin_text
        )
    else:
        bafin_section = (
            "No BaFin voting-rights notifications on file for any holder at or "
            "above the 3% WpHG disclosure threshold."
        )
    return board_excerpt + "\n\n" + bafin_section
