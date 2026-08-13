from dataclasses import dataclass


@dataclass
class RawDesignation:
    """A designation as pulled from a source, before ticker matching."""

    source: str  # "FDA"
    type: str  # "Breakthrough Therapy"
    date_granted: str  # ISO date
    drug_name: str
    company_name: str
    indication: str
    trial_id: str | None
    data_source: str  # where this record came from, e.g. a URL or "manual_seed"
    data_as_of_date: str  # ISO date this record was pulled/curated


@dataclass
class Company:
    ticker: str
    company_name: str
    exchange: str | None = None
    country: str | None = None
    market_cap: float | None = None
    currency: str | None = None
    sector: str | None = None
    founder_tier: str = "N/A"
    listing_type: str | None = None
    ticker_verified: bool = False
    ticker_verification_source: str | None = None
    ticker_verification_date: str | None = None
    ticker_match_confidence: float | None = None
    founder_name: str | None = None
    network_effect: str | None = None
    founder_tier_source: str | None = None  # e.g. SEC filing URL/accession used
    founder_tier_as_of_date: str | None = None


@dataclass
class Ownership:
    ticker: str  # FK -> companies.ticker
    founder_name: str
    role: str
    ownership_pct: float | None
    source: str
    as_of_date: str


@dataclass
class Designation:
    designation_id: str
    ticker: str  # FK -> companies.ticker ("unverified:<name>" if match failed)
    source: str
    type: str
    date_granted: str
    drug_name: str
    indication: str
    trial_id: str | None
    data_source: str
    data_as_of_date: str
    raw_company_name: str  # as submitted, before ticker matching — see db.py schema note
    summary_text: str | None = None
    summary_confidence_flag: str | None = None
    summary_generated_at: str | None = None


@dataclass
class Trial:
    trial_id: str
    registry: str
    phase: str | None
    status: str | None
    start_date: str | None
    primary_completion_date: str | None
    condition: str | None
    fetched_at: str
