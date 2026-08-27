"""Tier 2 (brief section 3), Netherlands. See sources/founder_led_tier2.py's
module docstring for why "Companies House + LSE (UK)" (the brief's stated
source) is wrong for this purpose — Adyen is Dutch, listed on Euronext
Amsterdam, not UK-incorporated or UK-listed at all.

For leadership *title*, Adyen's own investor-relations governance page is
authoritative, same reasoning as Germany/Hong Kong's board pages — but it's
built on Nuxt (a JS framework) and the visible DOM is nearly empty static
markup; the real bio content ships as a JSON hydration payload embedded in
a <script id="__NUXT_DATA__"> tag in the same initial HTML response (no JS
execution needed to see it — confirmed live: plain requests.get() already
returns it). fetch_leadership_excerpt() reads that script's text directly
instead of the usual visible-text extraction germany.py/hongkong.py use.

For ownership, the AFM (Autoriteit Financiële Markten — the Dutch SEC
equivalent) runs a public, unauthenticated substantial-holdings register
(the Wet melding zeggenschap disclosure regime) covering every Dutch
listed issuer, exportable as CSV and filterable server-side by a
"keywords" querystring param (confirmed live: keywords=Adyen cuts a
108MB full-register export down to ~2.5MB of Adyen-only rows). Same
3%-reporting-threshold caveat as Germany's BaFin database, and the same
honesty requirement: only the most recent threshold-crossing notification
on file is reported, explicitly labeled as a snapshot rather than implied
to be current, since a holder has no duty to notify again until another
threshold is crossed.

Only Pieter van der Does (Co-Founder & Co-CEO) is tracked as Adyen's
founder here. Co-founder Arnout Schuijff stepped down from the management
board on 2021-01-01 and left the company entirely (confirmed via public
reporting) — he no longer appears anywhere on the governance page, so
there is nothing to classify a "current role" from, unlike a Founder-Chair
or Founder-departed case with an active board seat.
"""

import csv
import io
import re

import requests
from bs4 import BeautifulSoup

from signal_screener.filings.sec_edgar import extract_leadership_excerpt

# A real browser-style UA, not SEC_USER_AGENT (SEC-specific, wrong for a
# Dutch corporate site / the AFM's portal).
_USER_AGENT = "Mozilla/5.0 (compatible; signal-screener research tool)"

GOVERNANCE_URLS = {
    "Adyen": "https://investors.adyen.com/governance",
}

# AFM's register export endpoint. `type` identifies the "substantial
# holdings and gross short positions" register specifically (confirmed
# live against the register's own "Export as CSV" link) — not a value
# this project chose, just what AFM's site emits.
AFM_EXPORT_URL = "https://www.afm.nl/export.aspx"
AFM_EXPORT_TYPE = "1331d46f-3fb6-4a36-b903-9584972675af"


def _governance_page_text(url: str) -> str:
    """Adyen's governance page is a Nuxt SPA: the rendered DOM is nearly
    empty, and the real bio/role content ships as a JSON string inside
    <script id="__NUXT_DATA__">. That script's own get_text() already
    contains readable prose (names, roles, bios) interleaved with JSON
    punctuation — good enough for extract_leadership_excerpt()'s regex
    windowing without needing to actually parse the JSON structure.
    Falls back to the ordinary visible-text extraction if no such script
    exists (e.g. the site stops being a Nuxt app), so this keeps working
    off the plain visible page for any future Tier 2 country that reuses
    it and doesn't have this quirk.
    """
    resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    nuxt_data = soup.find("script", id="__NUXT_DATA__")
    text = nuxt_data.get_text() if nuxt_data else soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _afm_notifications_for(company_name: str, surname: str) -> str:
    """Most recent AFM substantial-holdings notification on file for a
    holder matching surname, as plain text — "" (not an exception) both
    when nothing matches and when the request itself fails, same
    graceful-degradation contract as germany.py's BaFin lookup."""
    try:
        resp = requests.get(
            AFM_EXPORT_URL,
            params={"type": AFM_EXPORT_TYPE, "format": "csv", "keywords": company_name},
            headers={"User-Agent": _USER_AGENT},
            timeout=60,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return ""

    # AFM serves this export as Windows-1252, not UTF-8 (confirmed live —
    # UTF-8 decoding mangles the accented Dutch text, e.g. "Reëel").
    text = resp.content.decode("cp1252", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    # A handful of rows in this export are ragged (more/fewer fields than
    # the header), which makes csv.DictReader put None in for a missing
    # column instead of "" — confirmed live. `or ""` below treats those
    # the same as a genuinely blank field rather than crashing on them.
    matches = [
        row
        for row in reader
        if surname.lower() in (row.get("Meldingsplichtige") or "").lower()
        # Each notification appears twice, split by this column, into a
        # capital-interest row and a voting-rights row with different
        # percentages further along — Kapitaalbelang is the one this
        # project cares about (ownership stake, not voting rights).
        and row.get("Soort aandeel procentuele verdeling") == "Kapitaalbelang"
    ]
    if not matches:
        return ""

    matches.sort(key=lambda row: row.get("Datum meldingsplicht") or "", reverse=True)
    latest = matches[0]
    holder = (latest.get("Meldingsplichtige") or "").strip()
    pct = (latest.get("Totale deelneming") or "").strip()
    notification_date = (latest.get("Datum meldingsplicht") or "").split(" ")[0]
    manner = re.sub(r"<BR>", " ", latest.get("Wijze van beschikken") or "").strip()

    return (
        f"{holder}: {pct} total capital interest as of {notification_date} "
        f"({manner}) — the most recent AFM threshold-crossing notification "
        f"on file. Only holders at or above the 3% reporting threshold "
        f"appear in this register, and a notification is only filed again "
        f"when a threshold is crossed, so this figure is a snapshot from "
        f"that date and may not reflect current holdings."
    )


def fetch_leadership_excerpt(company_name: str, founder_name: str) -> str:
    """Combines a windowed excerpt of the governance page (same surname +
    role-keyword heuristic Tier 1/Germany/Hong Kong use, see
    filings/sec_edgar.py) with whatever the AFM register has on file, into
    one excerpt for the same Claude extraction prompt every other Tier 2
    country uses (summarize/founder_extraction.py).

    Raises if the governance page itself can't be fetched — it's the only
    source of the title info the Founder-CEO tier needs. The AFM half
    degrades gracefully to "nothing on file" instead.
    """
    governance_url = GOVERNANCE_URLS[company_name]
    board_excerpt = extract_leadership_excerpt(
        _governance_page_text(governance_url), founder_name
    )

    surname = founder_name.split()[-1]
    afm_text = _afm_notifications_for(company_name, surname)
    if afm_text:
        afm_section = "AFM substantial-holdings register notification on file: " + afm_text
    else:
        afm_section = (
            "No AFM substantial-holdings notification on file for any holder "
            "matching this name at or above the 3% reporting threshold."
        )
    return board_excerpt + "\n\n" + afm_section
