"""Step 3 of the MVP roadmap: founder-led/network-effect Tier 1 (ADR)
companies, using the same SEC EDGAR connection already built for the
biotech screener's ticker matching.

Runs the founder-led subset of the project brief's pipeline (section 4):
  2. Match company name to a ticker (fuzzy) — same matching/ticker_match.py
  3. Verify every matched ticker against a second, independent source —
     same matching/ticker_verify.py, mandatory, never silently trusted
  4. Classify founder status into exactly one tier (Founder-CEO /
     Founder-Chair / Founder-departed), pulled from a real SEC filing,
     never inferred or guessed. The filing/excerpt is re-fetched and
     re-checked every pipeline run, since both the title and the
     ownership stake can change over time — but the Claude extraction
     call itself (step 6) is only re-run when that excerpt has actually
     changed since the last run (see _founder_extraction_fingerprint),
     not unconditionally, so a daily schedule doesn't mean re-billing an
     identical call for a filing that hasn't changed. The recency rule
     (Founder-Chair aging into Founder-departed) still re-evaluates every
     run regardless, since that's a function of elapsed time, not of
     whether the excerpt changed.
  5. Pull ownership detail from the filing (Form 20-F / DEF 14A)
  6. Generate the founder-led/network-effect extraction via Claude
     (section 5's prompt)
  7. Store everything, with source + as-of date on every record
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime

from signal_screener import backtest, db, track_record, valuation
from signal_screener.filings import germany, hongkong, korea, netherlands
from signal_screener.filings.sec_edgar import (
    extract_leadership_excerpt,
    fetch_filing_text,
    get_latest_annual_filing,
)
from signal_screener.matching.resolve import resolve_ticker
from signal_screener.matching.ticker_match import TickerMatch, placeholder_ticker
from signal_screener.matching.ticker_verify import VerificationResult, verify_ticker
from signal_screener.models import Company, Ownership
from signal_screener.sources.founder_led_tier1 import TIER1_CANDIDATES
from signal_screener.sources.founder_led_tier2 import TIER2_CANDIDATES, Tier2Candidate
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
    # Cache hits (_founder_extraction_fingerprint unchanged since the last
    # run with a real classification) — see pipeline.RunSummary.
    # summaries_reused for the biotech-side twin of this.
    extractions_reused: int = 0
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
            f"{self.extraction_failures} founder extraction failure(s), "
            f"{self.extractions_reused} extraction(s) reused unchanged "
            f"| {self.delisted_or_acquired} delisted/acquired (not a failure)"
        )


def _founder_extraction_fingerprint(company_name: str, excerpt: str) -> str:
    """Hash of everything extract_founder_status() actually sees. Compared
    against the previous run's stored fingerprint (companies.
    founder_extraction_fingerprint) before calling Claude again — see that
    column's schema comment for why this exists (daily schedule, same
    filing/board-page excerpt most days)."""
    return hashlib.sha1(f"{company_name}|{excerpt}".encode("utf-8")).hexdigest()


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


def _fetch_tier2_excerpt(candidate: Tier2Candidate) -> str:
    """Dispatches to the country-specific filings/ module (see sources/
    founder_led_tier2.py)."""
    if candidate.source_country_code == "DE":
        return germany.fetch_leadership_excerpt(candidate.company_name, candidate.founder_name)
    if candidate.source_country_code == "KR":
        return korea.fetch_leadership_excerpt(candidate.company_name, candidate.founder_name_local)
    if candidate.source_country_code == "HK":
        return hongkong.fetch_leadership_excerpt(candidate.company_name, candidate.founder_name)
    if candidate.source_country_code == "NL":
        return netherlands.fetch_leadership_excerpt(candidate.company_name, candidate.founder_name)
    raise NotImplementedError(f"No Tier 2 source wired up for country code {candidate.source_country_code!r}")


def _tier2_source_citation(candidate: Tier2Candidate) -> str:
    if candidate.source_country_code == "DE":
        return f"DE:{germany.MANAGEMENT_BOARD_URLS[candidate.company_name]}"
    if candidate.source_country_code == "KR":
        return f"KR:DART exctvSttus corp_code={korea.CORP_CODES[candidate.company_name]}"
    if candidate.source_country_code == "HK":
        return f"HK:{hongkong.BOARD_MEMBERS_URLS[candidate.company_name]}"
    if candidate.source_country_code == "NL":
        return f"NL:{netherlands.GOVERNANCE_URLS[candidate.company_name]}"
    raise NotImplementedError(f"No Tier 2 source wired up for country code {candidate.source_country_code!r}")


def _resolve_tier2_ticker(candidate: Tier2Candidate) -> tuple[TickerMatch | None, VerificationResult | None]:
    """Tries candidate.known_ticker first, if set — still run through the
    same mandatory verify_ticker() check as everything else, never trusted
    just because it's hardcoded. Falls through to the general fuzzy-match
    dance (resolve_ticker) if there's no hint, or the hint doesn't verify
    (e.g. the company changed its primary listing since this was written).

    Exists because resolve_ticker()'s OpenFIGI tie-break has no concept of
    "which listing is this Tier 2 candidate's actual home market" — found
    live against Tencent: OpenFIGI ranks a thinly-traded US OTC ticker
    (TCTZF) above the real, liquid HKEX listing (0700.HK) because both
    verify and nothing in that tie-break favors one home exchange over
    another. That's a real accuracy problem, not a cosmetic one —
    track_record.py prices off of whatever ticker ends up here, and OTC
    pink-sheet pricing can be stale/illiquid next to the actual home-
    exchange price."""
    if candidate.known_ticker:
        hint_verification = verify_ticker(candidate.known_ticker, candidate.company_name)
        if hint_verification.verified:
            return (
                TickerMatch(
                    ticker=candidate.known_ticker,
                    matched_company_name=candidate.company_name,
                    confidence=100.0,
                ),
                hint_verification,
            )
    return resolve_ticker(candidate.company_name)


def _effective_transition_date(candidate: Tier2Candidate, extraction_transition_date: str | None) -> str | None:
    """Feeds _apply_recency_rule() the older (more conservative) of
    Claude's own extracted transition_date and a real, filing-confirmed
    anchor from a direct historical lookup — currently only Korea has one
    (see filings/korea.py's check_role_predates_recency_window). A single
    current-period excerpt has no "stepped back on X" sentence to find
    for a transition that happened many years before the source's data
    even starts (confirmed live: Naver's Lee Hae-jin already held his
    current, non-CEO role as of DART's earliest available year), so
    leaving this to Claude's excerpt-only inference would silently miss
    it — same "verify with real data, don't infer" principle
    check_delisted_or_acquired() (matching/ticker_verify.py) already
    applies elsewhere in this pipeline."""
    if candidate.source_country_code != "KR":
        return extraction_transition_date

    anchor = korea.check_role_predates_recency_window(candidate.company_name, candidate.founder_name_local)
    if anchor is None:
        return extraction_transition_date
    if extraction_transition_date is None:
        return anchor
    return min(anchor, extraction_transition_date)


def _fetch_valuation_for(session_and_crumb, ticker: str) -> dict:
    """Returns Company(**kwargs)-ready valuation fields — {} (the
    dataclass's own None defaults apply) if session_and_crumb is None
    (valuation.get_session_and_crumb() failed for the whole run) or the
    per-ticker fetch itself failed. Only called on each loop's success
    path, not every early-exit branch — a company that never reached
    ticker verification or founder classification has nothing to enrich
    (see the docstring on where this is called from)."""
    if session_and_crumb is None:
        return {}
    session, crumb = session_and_crumb
    metrics = valuation.fetch_valuation_metrics(session, crumb, ticker)
    if metrics is None:
        return {}
    return {
        "market_cap": metrics.market_cap,
        "currency": metrics.currency,
        "trailing_pe": metrics.trailing_pe,
        "forward_pe": metrics.forward_pe,
        "fifty_two_week_low": metrics.fifty_two_week_low,
        "fifty_two_week_high": metrics.fifty_two_week_high,
        "beta": metrics.beta,
        "dividend_yield_pct": metrics.dividend_yield_pct,
        "valuation_as_of_date": metrics.as_of_date,
        "valuation_source": metrics.source,
    }


def _fetch_backtest_for(sp500_current_price: float | None, ticker: str) -> dict:
    """Returns Company(**kwargs)-ready IPO-backtest fields — {} (the
    dataclass's own None defaults apply) if sp500_current_price is None
    (the once-per-run S&P 500 fetch failed) or the per-ticker backtest
    itself couldn't be computed (see backtest.compute_backtest's
    all-or-nothing contract). Only called on each loop's success path,
    same reasoning as _fetch_valuation_for above."""
    result = backtest.compute_backtest(ticker, sp500_current_price)
    if result is None:
        return {}
    return {
        "ipo_date": result.ipo_date,
        "ipo_price": result.company_ipo_price,
        "backtest_current_price": result.company_current_price,
        "sp500_price_at_ipo": result.sp500_price_at_ipo,
        "sp500_current_price": result.sp500_current_price,
        "backtest_as_of_date": result.as_of_date,
        "backtest_source": result.source,
    }


def _run_tier2(
    conn, run_summary: RunSummary, processed: list[str], session_and_crumb, sp500_current_price
) -> None:
    """Tier 2 (brief section 3): same match/verify/classify/store shape as
    the Tier 1 loop in run() below, kept as a separate function rather
    than unified with it — filing metadata (form/filing_date/exchange/
    sector, all pulled straight from SEC EDGAR) doesn't have an equivalent
    shape across arbitrary countries, and forcing one now would mean
    guessing at a generalization ahead of having more than one real
    country to generalize from. listing_type is "primary" here, not
    "ADR" — see sources/founder_led_tier2.py."""
    for candidate in TIER2_CANDIDATES:
        match, verification = _resolve_tier2_ticker(candidate)
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
                    listing_type="primary",
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
                    listing_type="primary",
                    ticker_verified=False,
                    ticker_verification_source=verification.source,
                    ticker_verification_date=verification.checked_date,
                    ticker_verification_reason=verification.reason,
                    ticker_match_confidence=match.confidence,
                    founder_name=candidate.founder_name,
                    exchange=candidate.exchange,
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

        try:
            excerpt = _fetch_tier2_excerpt(candidate)
        except Exception:
            logger.exception("Leadership-page fetch failed for %s", match.ticker)
            db.upsert_company(
                conn,
                Company(
                    ticker=match.ticker,
                    company_name=match.matched_company_name,
                    country=candidate.country,
                    founder_tier="N/A",
                    listing_type="primary",
                    ticker_verified=verification.verified,
                    ticker_verification_source=verification.source,
                    ticker_verification_date=verification.checked_date,
                    ticker_verification_reason=verification.reason,
                    ticker_match_confidence=match.confidence,
                    founder_name=candidate.founder_name,
                    exchange=candidate.exchange,
                ),
            )
            processed.append(match.ticker)
            run_summary.filing_lookup_failures += 1
            continue

        source_citation = _tier2_source_citation(candidate)
        fingerprint = _founder_extraction_fingerprint(candidate.company_name, excerpt)
        existing = db.get_company(conn, match.ticker)
        cache_hit = bool(
            existing
            and existing["founder_tier"] not in (None, "N/A")
            and existing["founder_extraction_fingerprint"] == fingerprint
        )

        if cache_hit:
            # Nothing Claude would see (company name + excerpt) has
            # changed since the last real classification — reuse it
            # rather than re-billing an identical call. The recency rule
            # still re-runs fresh below regardless: a Founder-Chair can
            # age into Founder-departed purely from elapsed time, on a
            # day the excerpt (and so this fingerprint) hasn't changed at
            # all — see companies.founder_transition_date's schema comment.
            #
            # founder_tier_source/as_of still use today's freshly-fetched
            # excerpt/source_citation, not the stale stored ones — the
            # source *was* actively re-checked today (that's how the
            # fingerprint match was established), only the Claude call
            # itself was skipped, so "as of today" is accurate here too.
            transition_date = existing["founder_transition_date"]
            network_effect = existing["network_effect"]
            network_effect_strength = existing["network_effect_strength"]
            founder_tier_source = source_citation
            as_of = date.today().isoformat()
            final_tier, override_reason = _apply_recency_rule(
                existing["founder_tier"], transition_date
            )
            run_summary.extractions_reused += 1
        else:
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
                        listing_type="primary",
                        ticker_verified=verification.verified,
                        ticker_verification_source=verification.source,
                        ticker_verification_date=verification.checked_date,
                        ticker_verification_reason=verification.reason,
                        ticker_match_confidence=match.confidence,
                        founder_name=candidate.founder_name,
                        founder_tier_source=source_citation,
                        founder_tier_as_of_date=date.today().isoformat(),
                        exchange=candidate.exchange,
                    ),
                )
                processed.append(match.ticker)
                run_summary.extraction_failures += 1
                continue

            transition_date = _effective_transition_date(candidate, extraction.transition_date)
            final_tier, override_reason = _apply_recency_rule(extraction.founder_tier, transition_date)
            network_effect = extraction.network_effect
            network_effect_strength = extraction.network_effect_strength
            founder_tier_source = source_citation
            as_of = date.today().isoformat()

        if override_reason:
            logger.info("%s: %s", match.ticker, override_reason)

        company = Company(
            ticker=match.ticker,
            company_name=match.matched_company_name,
            country=candidate.country,
            founder_tier=final_tier,
            listing_type="primary",
            ticker_verified=verification.verified,
            ticker_verification_source=verification.source,
            ticker_verification_date=verification.checked_date,
            ticker_verification_reason=verification.reason,
            ticker_match_confidence=match.confidence,
            founder_name=candidate.founder_name,
            network_effect=network_effect,
            network_effect_strength=network_effect_strength,
            founder_tier_source=founder_tier_source,
            founder_tier_as_of_date=as_of,
            exchange=candidate.exchange,
            founder_extraction_fingerprint=fingerprint,
            founder_transition_date=transition_date,
            **_fetch_valuation_for(session_and_crumb, match.ticker),
            **_fetch_backtest_for(sp500_current_price, match.ticker),
        )
        db.upsert_company(conn, company)

        if not cache_hit:
            # Append-only history (ownership table's own schema comment)
            # — only worth a new row when the extraction actually ran and
            # could have produced a different value; an unchanged cache
            # hit would just duplicate the last row with a later as_of_date
            # and no new information.
            db.insert_ownership(
                conn,
                Ownership(
                    ticker=match.ticker,
                    founder_name=candidate.founder_name,
                    role=extraction.leadership_status,
                    ownership_pct=extraction.ownership_pct_numeric,
                    source=source_citation,
                    as_of_date=as_of,
                ),
            )

        founder_flag = track_record.derive_founder_flag(final_tier, network_effect_strength)
        if founder_flag:
            track_record.flag_entry(
                conn,
                entry_id=match.ticker,
                entry_type="founder_stock",
                ticker=match.ticker,
                flag_given=founder_flag,
            )

        processed.append(match.ticker)


def run() -> RunSummary:
    """Runs the founder-led pipeline once (Tier 1 ADRs, then Tier 2
    home-market-listed international companies). Returns a RunSummary
    (processed tickers plus failure counts — see RunSummary.one_line())."""
    db.init_db()
    processed = []
    run_summary = RunSummary(processed_tickers=processed)
    # Fetched once for the whole run, not once per candidate — see
    # valuation.get_session_and_crumb()'s docstring. None here (crumb
    # setup failed) degrades every candidate's valuation fields to their
    # dataclass defaults (None) rather than failing the run.
    session_and_crumb = valuation.get_session_and_crumb()
    # Same "fetch once, reuse for every candidate" reasoning — it's the
    # same S&P 500 quote regardless of which company is being backtested.
    # None here degrades every candidate's backtest fields to their
    # dataclass defaults rather than failing the run.
    sp500_current_price = backtest.get_current_price(backtest.SP500_TICKER)

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

            source_citation = f"{filing.form}:{filing.document_url}"
            fingerprint = _founder_extraction_fingerprint(candidate.company_name, excerpt)
            existing = db.get_company(conn, match.ticker)
            cache_hit = bool(
                existing
                and existing["founder_tier"] not in (None, "N/A")
                and existing["founder_extraction_fingerprint"] == fingerprint
            )

            if cache_hit:
                # Same reasoning as _run_tier2's cache-hit branch: nothing
                # Claude would see has changed (same filing, same excerpt
                # text), so reuse the last real classification rather than
                # re-billing an identical call. The recency rule still
                # re-runs fresh below — see companies.founder_transition_date's
                # schema comment. source/as_of use today's freshly-fetched
                # filing metadata either way, so no special-casing needed
                # for those here (a genuinely new filing would change the
                # excerpt text too, which would already show up as a cache
                # miss above).
                transition_date = existing["founder_transition_date"]
                network_effect = existing["network_effect"]
                network_effect_strength = existing["network_effect_strength"]
                final_tier, override_reason = _apply_recency_rule(
                    existing["founder_tier"], transition_date
                )
                run_summary.extractions_reused += 1
            else:
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
                            founder_tier_source=source_citation,
                            founder_tier_as_of_date=filing.filing_date,
                            exchange=filing.exchange,
                            sector=filing.sector,
                        ),
                    )
                    processed.append(match.ticker)
                    run_summary.extraction_failures += 1
                    continue

                transition_date = extraction.transition_date
                final_tier, override_reason = _apply_recency_rule(extraction.founder_tier, transition_date)
                network_effect = extraction.network_effect
                network_effect_strength = extraction.network_effect_strength

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
                network_effect=network_effect,
                network_effect_strength=network_effect_strength,
                founder_tier_source=source_citation,
                founder_tier_as_of_date=filing.filing_date,
                exchange=filing.exchange,
                sector=filing.sector,
                founder_extraction_fingerprint=fingerprint,
                founder_transition_date=transition_date,
                **_fetch_valuation_for(session_and_crumb, match.ticker),
                **_fetch_backtest_for(sp500_current_price, match.ticker),
            )
            db.upsert_company(conn, company)

            if not cache_hit:
                # Append-only history — only worth a new row when the
                # extraction actually ran (see _run_tier2's matching
                # comment for the full reasoning).
                db.insert_ownership(
                    conn,
                    Ownership(
                        ticker=match.ticker,
                        founder_name=candidate.founder_name,
                        role=extraction.leadership_status,
                        ownership_pct=extraction.ownership_pct_numeric,
                        source=source_citation,
                        as_of_date=filing.filing_date,
                    ),
                )

            # Roadmap step 6: track record trigger (see track_record.py's
            # derive_founder_flag for the rule). entry_id is the ticker —
            # same convention user_notes already uses for founder-led
            # entries, since a founder-led company doesn't have a separate
            # designation_id-style identifier.
            founder_flag = track_record.derive_founder_flag(final_tier, network_effect_strength)
            if founder_flag:
                track_record.flag_entry(
                    conn,
                    entry_id=match.ticker,
                    entry_type="founder_stock",
                    ticker=match.ticker,
                    flag_given=founder_flag,
                )

            processed.append(match.ticker)

        _run_tier2(conn, run_summary, processed, session_and_crumb, sp500_current_price)

    return run_summary
