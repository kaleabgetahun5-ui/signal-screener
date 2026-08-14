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
from dataclasses import dataclass
from datetime import date, datetime

from signal_screener import db
from signal_screener.filings.sec_edgar import (
    extract_leadership_excerpt,
    fetch_filing_text,
    get_latest_annual_filing,
)
from signal_screener.matching.resolve import resolve_ticker
from signal_screener.matching.ticker_match import placeholder_ticker
from signal_screener.models import Company, Ownership
from signal_screener.sources.founder_led_tier1 import TIER1_CANDIDATES
from signal_screener.summarize.founder_extraction import extract_founder_status

logger = logging.getLogger(__name__)

# Project brief, section 4: a "Founder-Chair" whose CEO transition happened
# more than this many months ago is reclassified "Founder-departed" — the
# tier is meant to capture a recent handoff, not an indefinite arrangement.
FOUNDER_CHAIR_RECENCY_MONTHS = 24


@dataclass
class RunSummary:
    """Item 6, failure visibility — see pipeline.RunSummary for the twin
    of this on the biotech side."""

    processed_tickers: list[str]
    unverified_tickers: int = 0
    filing_lookup_failures: int = 0
    extraction_failures: int = 0
    # Not a failure — see pipeline.RunSummary.delisted_or_acquired.
    delisted_or_acquired: int = 0

    @property
    def failure_count(self) -> int:
        return self.unverified_tickers + self.filing_lookup_failures + self.extraction_failures

    def one_line(self) -> str:
        return (
            f"{len(self.processed_tickers)} processed, {self.failure_count} failure(s): "
            f"{self.unverified_tickers} unverified ticker(s), "
            f"{self.filing_lookup_failures} filing lookup failure(s), "
            f"{self.extraction_failures} founder extraction failure(s) "
            f"| {self.delisted_or_acquired} delisted/acquired (not a failure)"
        )


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


def run() -> RunSummary:
    """Runs the founder-led pipeline once. Returns a RunSummary (processed
    tickers plus failure counts — see RunSummary.one_line())."""
    db.init_db()
    processed = []
    run_summary = RunSummary(processed_tickers=processed)

    with db.connect() as conn:
        for candidate in TIER1_CANDIDATES:
            match, verification = resolve_ticker(candidate.company_name)
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
                run_summary.unverified_tickers += 1
                continue

            if verification.delisted_or_acquired:
                # Terminal state for this screener's purpose — a delisted/
                # acquired company isn't a founder-led investment candidate
                # anymore, so there's no point spending a filing lookup +
                # Claude extraction call classifying its founder tier. Kept
                # visible (never silently dropped) with founder_tier "N/A"
                # and the delisted/acquired flag, same as pipeline.py.
                logger.warning(
                    "%s (%s) is delisted/acquired: %s",
                    match.ticker,
                    candidate.company_name,
                    verification.reason,
                )
                db.upsert_company(
                    conn,
                    Company(
                        ticker=match.ticker,
                        company_name=match.matched_company_name,
                        country=candidate.country,
                        founder_tier="N/A",
                        listing_type="ADR",
                        ticker_verified=False,
                        ticker_verification_source=verification.source,
                        ticker_verification_date=verification.checked_date,
                        ticker_verification_reason=verification.reason,
                        ticker_match_confidence=match.confidence,
                        founder_name=candidate.founder_name,
                        delisted_or_acquired=True,
                    ),
                )
                processed.append(match.ticker)
                run_summary.delisted_or_acquired += 1
                continue

            if not verification.verified:
                logger.warning(
                    "Ticker verification failed for %s (%s): %s",
                    match.ticker,
                    candidate.company_name,
                    verification.reason,
                )
                run_summary.unverified_tickers += 1

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
                    ticker_verification_reason=verification.reason,
                    ticker_match_confidence=match.confidence,
                    founder_name=candidate.founder_name,
                )
                db.upsert_company(conn, company)
                processed.append(match.ticker)
                run_summary.filing_lookup_failures += 1
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
                        ticker_verification_reason=verification.reason,
                        ticker_match_confidence=match.confidence,
                        founder_name=candidate.founder_name,
                        founder_tier_source=f"{filing.form}:{filing.document_url}",
                        founder_tier_as_of_date=filing.filing_date,
                        exchange=filing.exchange,
                        sector=filing.sector,
                    ),
                )
                processed.append(match.ticker)
                run_summary.extraction_failures += 1
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
                ticker_verification_reason=verification.reason,
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

    return run_summary
