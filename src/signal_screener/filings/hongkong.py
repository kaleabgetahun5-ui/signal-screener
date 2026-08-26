"""Tier 2 (brief section 3), Hong Kong. See sources/founder_led_tier2.py's
module docstring for why HKEX's own Disclosure of Interests system
(di.hkex.com.hk, the brief's stated source) isn't usable here: confirmed
live, it sits behind an Akamai bot-detection JS challenge that returns an
endless "temporarily unavailable, redirecting..." loop to a plain HTTP
client — there's no scraping workaround for that within this project's
"free, simple, no headless browser" approach.

For leadership *title* — all section 4's Founder-CEO tier needs, no
ownership % required — the listed company's own investor-relations board
page is authoritative and current regardless of ownership thresholds,
same reasoning and same reuse of filings/sec_edgar.py's surname-windowing
heuristic as filings/germany.py. Confirmed live and static for Tencent.

Ownership percentage has no accessible source here at all — not a
threshold-register gap like Zalando/Naver (where the mechanism is
reachable but the founder's stake happens to fall under the reporting
floor), but a genuine access barrier: the one place this project has
found Hong Kong substantial-shareholder disclosures is the blocked DI
system. fetch_leadership_excerpt() says so explicitly in the excerpt
rather than silently omitting the topic, so Claude's extraction reports
"not disclosed in this excerpt" for the right reason and this project's
never-guess guardrail holds regardless of why the data isn't there.
"""

import re

import requests
from bs4 import BeautifulSoup

from signal_screener.filings.sec_edgar import extract_leadership_excerpt

# A real browser-style UA, not SEC_USER_AGENT (SEC-specific, wrong for a
# Hong Kong-listed company's own corporate site).
_USER_AGENT = "Mozilla/5.0 (compatible; signal-screener research tool)"

BOARD_MEMBERS_URLS = {
    "Tencent Holdings": "https://www.tencent.com/en-us/investors/board-members.html",
}


def _page_text(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def fetch_leadership_excerpt(company_name: str, founder_name: str) -> str:
    """Windowed excerpt of the board-members page (same surname + role-
    keyword heuristic Tier 1/Germany use — the full page is mostly nav-menu
    boilerplate) plus an explicit note about the blocked ownership source,
    for the same Claude extraction prompt Tier 1/Germany/Korea use
    (summarize/founder_extraction.py). Raises if the board page itself
    can't be fetched — it's the only source of the title info the
    Founder-CEO/Founder-Chair tiers need.
    """
    board_url = BOARD_MEMBERS_URLS[company_name]
    board_excerpt = extract_leadership_excerpt(_page_text(board_url), founder_name)

    ownership_note = (
        "No ownership percentage source is accessible for this company: HKEX's "
        "Disclosure of Interests system (the substantial-shareholder register) is "
        "behind bot-detection that blocks automated access, and the company's own "
        "investor-relations pages don't publish shareholding percentages as text."
    )
    return board_excerpt + "\n\n" + ownership_note
