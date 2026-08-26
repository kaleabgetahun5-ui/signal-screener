"""Tier 2 (project brief, section 3): founder-led/network-effect companies
listed only on their home exchange — not cross-listed as US ADRs the way
every Tier 1 candidate is. listing_type is "primary" here, not "ADR" (brief
section 2's schema names both as valid values) — that's a real distinction,
not a formality: these trade on their home market as their actual primary
listing.

Two corrections to the brief's stated sources, found while building this:
  - Germany: the brief names "Bundesanzeiger" — that's Germany's financial-
    statement filing register (a Companies House equivalent), and doesn't
    carry ownership/leadership disclosures at all. The real mechanism is
    BaFin's WpHG-mandated voting-rights notification database
    (portal.mvp.bafin.de/database/AnteileInfo/) — confirmed live, real,
    searchable — see filings/germany.py for what it actually covers (less
    than you'd hope: only holders at or above a 3% threshold).
  - Netherlands: the brief lists Adyen under "Companies House + LSE (UK)".
    Adyen is Dutch, listed on Euronext Amsterdam, not UK-listed at all —
    corrected here to the AFM's substantial-holdings register.

Candidates are added one country at a time as each source is actually
built and verified live, not all at once from the brief's list — the same
"expect manual curation early on, verify as you go" approach Tier 1's
company_name-as-search-string pattern already established.

South Korea (Naver): DART's structured data is keyed by name in Korean
script (e.g. "이해진", not "Lee Hae-jin") — founder_name_local carries that
for filings/korea.py's lookups, while founder_name stays the English
rendering used for display everywhere else (site, digest). None of the
other countries need this split (Germany's sources are already in Latin
script), so it defaults to None and filings/germany.py never looks at it.
"""

from dataclasses import dataclass


@dataclass
class Tier2Candidate:
    company_name: str
    founder_name: str
    country: str
    exchange: str
    source_country_code: str  # dispatches to the matching filings/<country>.py module
    founder_name_local: str | None = None  # see module docstring


TIER2_CANDIDATES = [
    Tier2Candidate("Zalando", "Robert Gentz", "Germany", "XETRA", "DE"),
    Tier2Candidate(
        "Naver", "Lee Hae-jin", "South Korea", "KOSPI", "KR", founder_name_local="이해진"
    ),
]
