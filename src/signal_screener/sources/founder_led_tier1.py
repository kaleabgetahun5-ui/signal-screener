"""Tier 1 of the founder-led/network-effect screener (project brief, section
3): foreign companies listed directly on NYSE/NASDAQ that file with the SEC
(20-F/6-K or, as testing found, 10-K/DEF 14A for the two of these five that
are Delaware-incorporated), so they plug into the same SEC EDGAR connection
already built for ticker matching and filing lookups.

company_name here is the search string run through the existing fuzzy
ticker matcher (matching/ticker_match.py) — same as every designation
source — not a hardcoded ticker, so this list goes through the same
match-then-verify path as the biotech screener rather than being trusted
by construction. founder_name is who filings/sec_edgar.py's excerpt
extractor searches for by surname.

country is the company's real operating headquarters, set here rather than
pulled from a filing — SEC's own company-metadata (registered agent /
mailing address) reflects where a company is legally domiciled or has a US
agent, not where it's actually headquartered, so it's not a reliable
source for this field.
"""

from dataclasses import dataclass


@dataclass
class FounderLedCandidate:
    company_name: str
    founder_name: str
    country: str


TIER1_CANDIDATES = [
    FounderLedCandidate("MercadoLibre", "Marcos Galperin", "Uruguay"),
    FounderLedCandidate("Sea Limited", "Forrest Li", "Singapore"),
    FounderLedCandidate("PDD Holdings", "Colin Huang", "China"),
    FounderLedCandidate("Coupang", "Bom Kim", "South Korea"),
    FounderLedCandidate("Grab Holdings", "Anthony Tan", "Singapore"),
]
