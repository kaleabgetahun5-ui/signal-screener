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

Hong Kong (Tencent): the brief's stated source, HKEX's Disclosure of
Interests system (di.hkex.com.hk), is real but sits behind active bot
protection (an Akamai JS challenge, confirmed live — a plain HTTP client
gets an infinite redirect loop, never the actual search results). No
scraping workaround for that here; filings/hongkong.py falls back to
Tencent's own investor-relations board page for leadership (reliably
static — real content confirmed live) and documents the ownership-%
gap explicitly rather than silently guessing (same "not disclosed in
this excerpt" honesty as Zalando/Naver's threshold-register gaps, just
with a different cause: blocked access, not a genuine absence of
disclosure).

known_ticker: an optional pre-verified ticker hint, tried before the
general fuzzy-match dance (resolve_ticker) — still run through the same
mandatory verify_ticker() check, never trusted blindly. Added for
Tencent specifically: OpenFIGI's own ranking put a thinly-traded US OTC
ticker (TCTZF) ahead of the real, liquid HKEX primary listing (0700.HK)
because both verify and the tie-break has no way to know HKEX is the
"real" one — a bigger accuracy issue than it sounds, since
track_record.py prices off of whatever ticker ends up here, and OTC
pink-sheet pricing for a name like this can be stale/illiquid next to
its actual home-exchange price. Left unset for Zalando/Naver, which
already resolve correctly without it. The same OTC-ticker trap hit
Adyen too (resolves to ADYYF over the real Euronext Amsterdam listing,
ADYEN.AS) — confirmed live, same fix.

Netherlands (Adyen): only Pieter van der Does (Co-Founder & Co-CEO) is
tracked. Co-founder Arnout Schuijff stepped down from the management
board on 2021-01-01 and left the company entirely — see
filings/netherlands.py for the source confirming that and why there's
no "current role" left for him to classify.
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
    known_ticker: str | None = None  # see module docstring


TIER2_CANDIDATES = [
    Tier2Candidate("Zalando", "Robert Gentz", "Germany", "XETRA", "DE"),
    Tier2Candidate(
        "Naver", "Lee Hae-jin", "South Korea", "KOSPI", "KR", founder_name_local="이해진"
    ),
    Tier2Candidate(
        "Tencent Holdings", "Ma Huateng (Pony Ma)", "Hong Kong", "HKEX", "HK", known_ticker="0700.HK"
    ),
    Tier2Candidate(
        "Adyen", "Pieter van der Does", "Netherlands", "Euronext Amsterdam", "NL",
        known_ticker="ADYEN.AS",
    ),
]
