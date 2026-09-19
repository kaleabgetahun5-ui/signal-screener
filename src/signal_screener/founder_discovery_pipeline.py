"""S&P 500 discovery feature: scans the S&P 500 for founder-led companies
beyond the hand-curated Tier 1/Tier 2 lists (sources/founder_led_tier1.py,
sources/founder_led_tier2.py — the existing 9). Reuses this project's
existing verification rigor end to end (mandatory second-source ticker
verification, real SEC filings only, never-infer extraction) but publishes
nothing straight to the live site: every company this finds lands in the
founder_candidates table as 'pending' and needs an explicit human approval
(the candidates-approve CLI command) before promote_approved() below will
ever add it to the real `companies` table those other pipelines populate.

Two-phase, mirroring the approval gate itself:
  run()              — discovery only. Never touches `companies`, never
                        overwrites an existing candidate's status.
  promote_approved() — for candidates a human has approved, runs them
                        through the same match/verify/classify/store shape
                        as founder_pipeline.py's Tier 1 loop (reusing its
                        _fetch_valuation_for/_fetch_backtest_for helpers
                        directly rather than reimplementing them), and
                        writes a real `companies` row. Only ever acts on
                        rows already marked status='approved' by a human;
                        never invoked automatically by run() or by any
                        scheduled job.

Deliberately its own module rather than added to founder_pipeline.py: the
existing Tier 1/Tier 2 pipeline, its candidate lists, and its daily
schedule are out of scope for this feature and shouldn't be touched to
build it.
"""

import logging
from dataclasses import dataclass, field
from datetime import date

from signal_screener import backtest, db, track_record, valuation
from signal_screener.filings.sec_edgar import (
    extract_founder_mention_excerpts,
    extract_leadership_excerpt,
    fetch_filing_text,
    get_latest_annual_filing,
)
from signal_screener.founder_pipeline import _fetch_backtest_for, _fetch_valuation_for
from signal_screener.matching.ticker_verify import verify_ticker
from signal_screener.models import Company, FounderCandidate, Ownership
from signal_screener.sources.sp500_universe import fetch_sp500_constituents
from signal_screener.summarize.founder_discovery_extraction import detect_founder_leadership
from signal_screener.summarize.founder_extraction import extract_founder_status

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryRunSummary:
    scanned: int = 0
    already_known: int = 0
    ticker_unverified: int = 0
    no_filing: int = 0
    no_founder_mention: int = 0
    no_founder_detected: int = 0
    detection_failures: int = 0
    newly_discovered: list[str] = field(default_factory=list)

    def one_line(self) -> str:
        return (
            f"{self.scanned} scanned, {len(self.newly_discovered)} new candidate(s) found: "
            f"{self.already_known} already known/skipped, {self.ticker_unverified} unverified ticker(s), "
            f"{self.no_filing} no filing found, {self.no_founder_mention} filing never mentions 'founder', "
            f"{self.no_founder_detected} mentioned 'founder' but nothing qualified, "
            f"{self.detection_failures} detection failure(s)"
        )


def run(limit: int | None = None) -> DiscoveryRunSummary:
    """Scans up to `limit` S&P 500 tickers not already known (see
    db.get_known_discovery_tickers — anything already a real company or
    already an existing candidate in any status) for a filing that
    explicitly names an active founder-CEO/Chair. limit=None scans the
    full ~500-ticker list, which makes a live ticker-verification call per
    ticker plus (for filings that mention "founder" at all) a Claude call
    — expect a full run to take a while and make real API calls. Pass a
    limit for a bounded/manual first pass."""
    db.init_db()
    summary = DiscoveryRunSummary()

    constituents = fetch_sp500_constituents()
    with db.connect() as conn:
        known_tickers = db.get_known_discovery_tickers(conn)

        for constituent in constituents:
            if constituent.ticker in known_tickers:
                summary.already_known += 1
                continue
            if limit is not None and summary.scanned >= limit:
                continue

            summary.scanned += 1

            verification = verify_ticker(constituent.ticker, constituent.company_name)
            if not verification.verified:
                logger.info(
                    "Skipping %s (%s): ticker didn't verify — %s",
                    constituent.ticker,
                    constituent.company_name,
                    verification.reason,
                )
                summary.ticker_unverified += 1
                continue

            filing = get_latest_annual_filing(constituent.ticker)
            if filing is None:
                summary.no_filing += 1
                continue

            try:
                text = fetch_filing_text(filing.document_url)
            except Exception:
                logger.exception("Filing fetch failed for %s", constituent.ticker)
                summary.no_filing += 1
                continue

            excerpt = extract_founder_mention_excerpts(text)
            if excerpt is None:
                summary.no_founder_mention += 1
                continue

            try:
                detection = detect_founder_leadership(
                    company_name=constituent.company_name, report_excerpt=excerpt
                )
            except Exception:
                logger.exception("Founder detection failed for %s", constituent.ticker)
                summary.detection_failures += 1
                continue

            if not detection.founder_detected:
                summary.no_founder_detected += 1
                continue

            candidate = FounderCandidate(
                ticker=constituent.ticker,
                company_name=filing.company_name or constituent.company_name,
                founder_name=detection.founder_name,
                current_title=detection.current_title,
                ownership_pct=detection.ownership_pct_numeric,
                ownership_stake_text=detection.ownership_stake,
                source_citation=f"{filing.form}:{filing.document_url}",
                source_excerpt=excerpt,
                discovered_at=date.today().isoformat(),
                country=constituent.headquarters,
                exchange=filing.exchange,
                sector=filing.sector or constituent.sector,
            )
            inserted = db.insert_founder_candidate(conn, candidate)
            if inserted:
                summary.newly_discovered.append(constituent.ticker)

    return summary


@dataclass
class PromoteRunSummary:
    promoted: list[str] = field(default_factory=list)
    lookup_failures: int = 0
    extraction_failures: int = 0

    def one_line(self) -> str:
        promoted_list = ", ".join(self.promoted) if self.promoted else "none"
        return (
            f"{len(self.promoted)} promoted ({promoted_list}), "
            f"{self.lookup_failures} lookup failure(s), "
            f"{self.extraction_failures} extraction failure(s)"
        )


def promote_approved() -> PromoteRunSummary:
    """For every founder_candidates row with status='approved', runs the
    same match/verify/classify/store shape founder_pipeline.py's Tier 1
    loop uses — re-verifies the ticker fresh, re-fetches the filing fresh,
    calls the full founder_extraction.py prompt (including the network-
    effect classification discovery deliberately skips — see
    summarize/founder_discovery_extraction.py's docstring), and reuses
    founder_pipeline._fetch_valuation_for/_fetch_backtest_for directly
    rather than reimplementing them — and writes a real `companies` row.
    listing_type is "primary": every S&P 500 constituent trades on its
    home exchange as its actual primary listing, never as an ADR.

    Only ever touches rows already marked 'approved' by a human via the
    candidates-approve CLI command; never invoked automatically by run()
    above or by any scheduled job."""
    db.init_db()
    summary = PromoteRunSummary()
    session_and_crumb = valuation.get_session_and_crumb()
    sp500_current_price = backtest.get_current_price(backtest.SP500_TICKER)

    with db.connect() as conn:
        for row in db.list_founder_candidates(conn, status="approved"):
            ticker = row["ticker"]

            verification = verify_ticker(ticker, row["company_name"])
            if not verification.verified:
                logger.warning(
                    "Re-verification failed for approved candidate %s: %s",
                    ticker,
                    verification.reason,
                )
                summary.lookup_failures += 1
                continue

            filing = get_latest_annual_filing(ticker)
            if filing is None:
                logger.warning("No annual filing found for approved candidate %s", ticker)
                summary.lookup_failures += 1
                continue

            try:
                text = fetch_filing_text(filing.document_url)
                excerpt = extract_leadership_excerpt(text, row["founder_name"])
                extraction = extract_founder_status(
                    company_name=row["company_name"], report_excerpt=excerpt
                )
            except Exception:
                logger.exception("Founder extraction failed while promoting %s", ticker)
                summary.extraction_failures += 1
                continue

            source_citation = f"{filing.form}:{filing.document_url}"
            company = Company(
                ticker=ticker,
                company_name=filing.company_name or row["company_name"],
                country=row["country"],
                founder_tier=extraction.founder_tier,
                listing_type="primary",
                ticker_verified=verification.verified,
                ticker_verification_source=verification.source,
                ticker_verification_date=verification.checked_date,
                ticker_verification_reason=verification.reason,
                ticker_match_confidence=100.0,  # exact ticker from the S&P 500 list, not a fuzzy guess
                founder_name=row["founder_name"],
                network_effect=extraction.network_effect,
                network_effect_strength=extraction.network_effect_strength,
                founder_tier_source=source_citation,
                founder_tier_as_of_date=filing.filing_date,
                exchange=filing.exchange,
                sector=filing.sector,
                **_fetch_valuation_for(session_and_crumb, ticker),
                **_fetch_backtest_for(sp500_current_price, ticker),
            )
            db.upsert_company(conn, company)
            db.insert_ownership(
                conn,
                Ownership(
                    ticker=ticker,
                    founder_name=row["founder_name"],
                    role=extraction.leadership_status,
                    ownership_pct=extraction.ownership_pct_numeric,
                    source=source_citation,
                    as_of_date=filing.filing_date,
                ),
            )

            founder_flag = track_record.derive_founder_flag(
                extraction.founder_tier, extraction.network_effect_strength
            )
            if founder_flag:
                track_record.flag_entry(
                    conn,
                    entry_id=ticker,
                    entry_type="founder_stock",
                    ticker=ticker,
                    flag_given=founder_flag,
                )

            db.set_founder_candidate_status(conn, ticker, "promoted", db.now_iso())
            summary.promoted.append(ticker)

    return summary
