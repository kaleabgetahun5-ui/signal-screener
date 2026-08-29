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
    # Citation for date_granted specifically (a URL/filing, not just "manual
    # seed") — sources/ema_prime.py requires and validates this per row;
    # None for sources (e.g. FDA) that don't yet enforce it.
    date_granted_source: str | None = None


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
    ticker_verification_reason: str | None = None
    ticker_match_confidence: float | None = None
    # Brief section 4's "listing status changed" case, distinct from a
    # plain unverified match — see matching/ticker_verify.py's
    # check_delisted_or_acquired(). True means this company was very likely
    # matched correctly but is no longer an active, tradable listing
    # (acquired, delisted, gone private) — surfaced distinctly on the site
    # and in the digest rather than lumped in with "couldn't verify this."
    delisted_or_acquired: bool = False
    founder_name: str | None = None
    network_effect: str | None = None
    # "Established" | "Emerging" | "None identified" — see
    # summarize/founder_extraction.py's ALLOWED_NETWORK_EFFECT_STRENGTHS.
    # Drives the track-record trigger rule (tracked_outcomes.py) alongside
    # founder_tier: Founder-CEO+Established -> High signal, Founder-CEO+
    # Emerging -> capped at Moderate, Founder-Chair -> Moderate regardless.
    network_effect_strength: str | None = None
    founder_tier_source: str | None = None  # e.g. SEC filing URL/accession used
    founder_tier_as_of_date: str | None = None
    # Valuation snapshot (valuation.py) — market_cap/currency above are
    # reused for this rather than duplicated; the rest are new. All None
    # for a company valuation.fetch_valuation_metrics() couldn't reach
    # (never fabricated), and re-fetched fresh on every pipeline run, same
    # "can go stale, never cached indefinitely" principle as price/
    # ownership.
    trailing_pe: float | None = None
    forward_pe: float | None = None
    fifty_two_week_low: float | None = None
    fifty_two_week_high: float | None = None
    beta: float | None = None
    dividend_yield_pct: float | None = None
    valuation_as_of_date: str | None = None
    valuation_source: str | None = None
    # IPO backtest (backtest.py) — "$100 at IPO vs. S&P 500," site.py's own
    # module docstring's long-deferred feature. currency above is reused
    # for ipo_price/backtest_current_price (a stock only ever trades in
    # one currency). Never fabricated (None if backtest.compute_backtest()
    # couldn't derive every input) and re-fetched fresh every run, same
    # rationale as the valuation fields above.
    ipo_date: str | None = None
    ipo_price: float | None = None
    backtest_current_price: float | None = None
    sp500_price_at_ipo: float | None = None
    sp500_current_price: float | None = None
    backtest_as_of_date: str | None = None
    backtest_source: str | None = None


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
    date_granted_source: str | None = None  # see RawDesignation


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
