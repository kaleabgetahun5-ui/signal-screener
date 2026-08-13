"""Step 3 of the MVP roadmap: founder-led/network-effect Tier 1 (ADR)
companies, using the same SEC EDGAR connection already built for the
biotech screener's ticker matching.

Runs the founder-led subset of the project brief's pipeline (section 4):
  2. Match company name to a ticker (fuzzy) — same matching/ticker_match.py
  3. Verify every matched ticker against a second, independent source —
     same matching/ticker_verify.py, mandatory, never silently trusted
  4. Classify founder status into exactly one tier (Founder-CEO /
     Founder-Chair / Founder-departed), pulled from a real SEC filing,
     never inferred or guessed. Re-run every pipeline run, since both the
     title and the ownership stake can change over time.
  5. Pull ownership detail from the filing (Form 20-F / DEF 14A)
  6. Generate the founder-led/network-effect extraction via Claude
     (section 5's prompt)
  7. Store everything, with source + as-of date on every record
"""

import logging
from datetime import date, datetime

from signal_screener import db
from signal_screener.filings.sec_edgar import (
    extract_leadership_excerpt,
    fetch_filing_text,
    get_latest_annual_filing,
)
from signal_screener.matching.ticker_match import match_company_to_ticker, placeholder_ticker
from signal_screener.matching.ticker_verify import verify_ticker
from signal_screener.models import Company, Ownership
from signal_screener.sources.founder_led_tier1 import TIER1_CANDIDATES
from signal_screener.summarize.founder_extraction import extract_founder_status

logger = logging.getLogger(__name__)

# Project brief, section 4: a "Founder-Chair" whose CEO transition happened
# more than this many months ago is reclassified "Founder-departed" — the
# tier is meant to capture a recent handoff, not an indefinite arrangement.
FOUNDER_CHAIR_RECENCY_MONTHS = 24


def _months_since(iso_date: str) -> float | None:
    try:
        then = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    today = date.today()
    return (today.year - then.year) * 12 + (today.month - then.month)


def _apply_recency_rule(founder_tier: str, transition_date: str | None) -> tuple[str, str | None]:
    """Returns (final_tier, override_reason)."""
    if founder_tier != "Founder-Chair" or not transition_date:
        return founder_tier, None

    months = _months_since(transition_date)
    if months is not None and months > FOUNDER_CHAIR_RECENCY_MONTHS:
        return "Founder-departed", (
            f"downgraded from Founder-Chair: transition on {transition_date} "
            f"was {months:.0f} months ago, over the {FOUNDER_CHAIR_RECENCY_MONTHS}-month limit"
        )
    return founder_tier, None


def run() -> list[str]:
    """Runs the founder-led pipeline once. Returns tickers processed."""
    db.init_db()
    processed = []

    with db.connect() as conn:
        for candidate in TIER1_CANDIDATES:
            match = match_company_to_ticker(candidate.company_name)
            if match is None:
                logger.warning("No ticker match for company_name=%r", candidate.company_name)
                ticker = placeholder_ticker(candidate.company_name)
                db.upsert_company(
                    conn,
                    Company(
                        ticker=ticker,
                        company_name=candidate.company_name,
                        country=candidate.country,
                        founder_tier="N/A",
                        listing_type="ADR",
                        ticker_verified=False,
                        ticker_verification_source="none",
                        ticker_verification_date=date.today().isoformat(),
                        founder_name=candidate.founder_name,
                    ),
                )
                processed.append(ticker)
                continue

            verification = verify_ticker(match.ticker, candidate.company_name)
            if not verification.verified:
                logger.warning(
                    "Ticker verification failed for %s (%s): %s",
                    match.ticker,
                    candidate.company_name,
                    verification.reason,
                )

            filing = get_latest_annual_filing(match.ticker)
            if filing is None:
                logger.warning("No annual filing found for %s", match.ticker)
                company = Company(
                    ticker=match.ticker,
                    company_name=match.matched_company_name,
                    country=candidate.country,
                    founder_tier="N/A",
                    listing_type="ADR",
                    ticker_verified=verification.verified,
                    ticker_verification_source=verification.source,
                    ticker_verification_date=verification.checked_date,
                    ticker_match_confidence=match.confidence,
                    founder_name=candidate.founder_name,
                )
                db.upsert_company(conn, company)
                processed.append(match.ticker)
                continue

            text = fetch_filing_text(filing.document_url)
            excerpt = extract_leadership_excerpt(text, candidate.founder_name)

            try:
                extraction = extract_founder_status(
                    company_name=candidate.company_name, report_excerpt=excerpt
                )
            except Exception:
                logger.exception("Founder extraction failed for %s", match.ticker)
                db.upsert_company(
                    conn,
                    Company(
                        ticker=match.ticker,
                        company_name=match.matched_company_name,
                        country=candidate.country,
                        founder_tier="N/A",
                        listing_type="ADR",
                        ticker_verified=verification.verified,
                        ticker_verification_source=verification.source,
                        ticker_verification_date=verification.checked_date,
                        ticker_match_confidence=match.confidence,
                        founder_name=candidate.founder_name,
                        founder_tier_source=f"{filing.form}:{filing.document_url}",
                        founder_tier_as_of_date=filing.filing_date,
                        exchange=filing.exchange,
                        sector=filing.sector,
                    ),
                )
                processed.append(match.ticker)
                continue

            final_tier, override_reason = _apply_recency_rule(
                extraction.founder_tier, extraction.transition_date
            )
            if override_reason:
                logger.info("%s: %s", match.ticker, override_reason)

            company = Company(
                ticker=match.ticker,
                company_name=match.matched_company_name,
                country=candidate.country,
                founder_tier=final_tier,
                listing_type="ADR",
                ticker_verified=verification.verified,
                ticker_verification_source=verification.source,
                ticker_verification_date=verification.checked_date,
                ticker_match_confidence=match.confidence,
                founder_name=candidate.founder_name,
                network_effect=extraction.network_effect,
                founder_tier_source=f"{filing.form}:{filing.document_url}",
                founder_tier_as_of_date=filing.filing_date,
                exchange=filing.exchange,
                sector=filing.sector,
            )
            db.upsert_company(conn, company)

            db.insert_ownership(
                conn,
                Ownership(
                    ticker=match.ticker,
                    founder_name=candidate.founder_name,
                    role=extraction.leadership_status,
                    ownership_pct=extraction.ownership_pct_numeric,
                    source=f"{filing.form}:{filing.document_url}",
                    as_of_date=filing.filing_date,
                ),
            )

            processed.append(match.ticker)

    return processed
