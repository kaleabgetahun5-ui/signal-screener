"""Real SEC EDGAR connector for founder-led screener support: locates a
company's most recent leadership/ownership-bearing filing and pulls a
best-effort excerpt from it for Claude to classify (section 5's founder-led
extraction prompt).

Reuses the same SEC EDGAR access already built for ticker matching
(matching/ticker_match.py's CIK lookup, same SEC_USER_AGENT requirement).

Which filing type to use is NOT uniform across "ADR" Tier 1 companies, and
that's a real finding from testing against the five companies in this step:
MercadoLibre and Coupang are Delaware-incorporated and file as US domestic
filers (10-K + DEF 14A proxy statements), while Sea Limited, PDD Holdings,
and Grab are foreign private issuers (20-F + 6-K) — the brief's assumption
that Tier 1 companies uniformly file "Form 20-F, 6-K" doesn't hold for all
five. A DEF 14A is preferred when available: it has a dedicated, fairly
consistent "beneficial ownership" table and director bios, which annual
reports usually just incorporate by reference rather than including
directly. 20-F is the fallback for foreign private issuers, which don't
file DEF 14A at all.

Excerpt extraction is a best-effort keyword-window heuristic (search for
the founder's name near role words, and for ownership-table headings near
a "%" sign and the founder's surname), not a real structural parse of the
filing — these documents run 100-300+ pages with no consistent format
across filers. It works well enough to hand Claude a relevant excerpt in
testing (see MercadoLibre's 2026 proxy, where it correctly isolates both
the CEO-transition letter and the beneficial-ownership table row), but a
miss here just means a thinner excerpt, not a silently wrong one — the
extraction prompt already requires Claude to say "not stated" rather than
guess when something isn't in the excerpt it's given.
"""

import re
import warnings
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from signal_screener.config import SEC_USER_AGENT
from signal_screener.matching.ticker_match import get_cik_for_ticker

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# Preference order: a proxy statement's ownership table + director bios beat
# an annual report's incorporate-by-reference pointer to that same proxy.
PREFERRED_FORMS = ["DEF 14A", "20-F"]

OWNERSHIP_HEADINGS = [
    "beneficial ownership",
    "security ownership",
    "major shareholders",
    "principal shareholders",
]
# Weighted, not just present/absent: generic words like "president" or
# "founder" alone caused a false-positive match in testing (Sea Limited's
# filing mentions its CEO being "elected as President of" an unrelated
# trade association, in a related-party-transactions footnote far from his
# actual bio). Title phrases that are unambiguous about a *corporate* role
# score higher than generic words that need the corporate context.
ROLE_KEYWORDS = {
    "chief executive officer": 3,
    "executive chairman": 3,
    "chairman of the board": 3,
    "chairman": 2,
    "director since": 1,
    "founder": 1,
    "president": 1,
}


@dataclass
class FilingRef:
    company_name: str
    form: str
    filing_date: str
    accession_number: str
    document_url: str
    exchange: str | None
    sector: str | None


def get_latest_annual_filing(ticker: str) -> FilingRef | None:
    cik = get_cik_for_ticker(ticker)
    if cik is None:
        return None

    resp = requests.get(
        SUBMISSIONS_URL.format(cik=cik),
        headers={"User-Agent": SEC_USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    recent = data["filings"]["recent"]
    exchanges = data.get("exchanges") or []

    for form_type in PREFERRED_FORMS:
        for i, form in enumerate(recent["form"]):
            if form != form_type:
                continue
            accession = recent["accessionNumber"][i]
            accession_nodash = accession.replace("-", "")
            cik_nolead = str(int(cik))
            doc = recent["primaryDocument"][i]
            return FilingRef(
                company_name=data["name"],
                form=form_type,
                filing_date=recent["filingDate"][i],
                accession_number=accession,
                document_url=(
                    f"https://www.sec.gov/Archives/edgar/data/"
                    f"{cik_nolead}/{accession_nodash}/{doc}"
                ),
                exchange=exchanges[0] if exchanges else None,
                sector=data.get("sicDescription"),
            )
    return None


def fetch_filing_text(document_url: str) -> str:
    resp = requests.get(document_url, headers={"User-Agent": SEC_USER_AGENT}, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def extract_leadership_excerpt(text: str, founder_name: str, max_chars: int = 6000) -> str:
    """Best-effort excerpt around the founder's role and ownership stake.
    See module docstring for the heuristic's known limitations."""
    sections = []
    surname = founder_name.split()[-1].lower()

    # Search by surname, not the full name: filings are inconsistent about
    # middle names ("Forrest Li" in a footnote vs. "Forrest Xiaodong Li" in
    # the actual director table), and an exact full-name match silently
    # misses the real bio entirely in that case — confirmed against Sea
    # Limited's 20-F during testing. Surname + a word boundary, scored by
    # nearby role keywords, is more robust across that inconsistency.
    best_leadership_idx, best_score = None, 0
    for m in re.finditer(rf"\b{re.escape(surname)}\b", text, re.IGNORECASE):
        window = text[max(0, m.start() - 150) : m.start() + 150].lower()
        score = sum(weight for kw, weight in ROLE_KEYWORDS.items() if kw in window)
        if score > best_score:
            best_score, best_leadership_idx = score, m.start()
    if best_leadership_idx is not None:
        sections.append(text[max(0, best_leadership_idx - 400) : best_leadership_idx + 900])

    for heading in OWNERSHIP_HEADINGS:
        found = False
        for m in re.finditer(re.escape(heading), text, re.IGNORECASE):
            window = text[m.start() : m.start() + 1500]
            if "%" in window and surname in window.lower():
                sections.append(text[m.start() : m.start() + 2500])
                found = True
                break
        if found:
            break

    combined = "\n...\n".join(sections) if sections else text[:max_chars]
    return combined[:max_chars]
