"""Steps 1-2 of the MVP roadmap: FDA Breakthrough Therapy + EMA PRIME.

Runs the subset of the project brief's pipeline (section 4) that applies
before the founder-led screener exists:
  1. Pull new designations from every registered source (FDA, EMA)
  2. Match drug/company name to a ticker (fuzzy)
  3. Verify every matched ticker against a second, independent source —
     mandatory for every entry, every run; never silently dropped or trusted
  5. Pull trial detail from ClinicalTrials.gov (if a trial_id is present)
  6. Generate a plain-English clinical summary via Claude
  7. Store everything, with source + as-of date on every record

Every source module exposes the same fetch_new_designations() -> list[RawDesignation]
interface (see sources/fda_breakthrough.py and sources/ema_prime.py), so steps
2 onward run identically regardless of which regulator issued the designation.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import date

from signal_screener import db, track_record
from signal_screener.matching.resolve import resolve_ticker
from signal_screener.matching.ticker_match import placeholder_ticker
from signal_screener.models import Company, Designation
from signal_screener.sources import ema_prime, fda_breakthrough
from signal_screener.summarize.claude_summary import summarize_designation
from signal_screener.trials.clinicaltrials import fetch_trial

logger = logging.getLogger(__name__)

SOURCES = [fda_breakthrough, ema_prime]


@dataclass
class RunSummary:
    """Item 6, failure visibility: every run reports what actually went
    wrong, in one line, instead of failures only being visible by reading
    logs. Surfaced by the CLI (cli.py) and folded into the weekly digest
    (digest.py) so a bad run doesn't go unnoticed until someone happens to
    read a designation's card and see it's unverified."""

    processed_ids: list[str]
    unverified_tickers: int = 0
    trial_lookup_failures: int = 0
    summarization_failures: int = 0
    # Not a failure — a confirmed real-world status change (brief section
    # 4). Tracked and reported, but deliberately excluded from
    # failure_count: counting it as one would misrepresent a correctly-
    # detected acquisition/delisting as something the pipeline got wrong.
    delisted_or_acquired: int = 0

    @property
    def failure_count(self) -> int:
        return self.unverified_tickers + self.trial_lookup_failures + self.summarization_failures

    def one_line(self) -> str:
        return (
            f"{len(self.processed_ids)} processed, {self.failure_count} failure(s): "
            f"{self.unverified_tickers} unverified ticker(s), "
            f"{self.trial_lookup_failures} trial lookup failure(s), "
            f"{self.summarization_failures} summarization failure(s) "
            f"| {self.delisted_or_acquired} delisted/acquired (not a failure)"
        )


def _designation_id(raw) -> str:
    key = f"{raw.source}|{raw.type}|{raw.drug_name}|{raw.company_name}|{raw.date_granted}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _resolve_company(raw) -> Company:
    """Steps 2 + 3: match then mandatorily verify. Always returns a Company
    row — an unmatched or failed-verification entry is still recorded, just
    flagged unverified, per the brief's "never silently dropped" rule."""
    match, verification = resolve_ticker(raw.company_name)

    if match is None:
        logger.warning("No ticker match for company_name=%r", raw.company_name)
        return Company(
            ticker=placeholder_ticker(raw.company_name),
            company_name=raw.company_name,
            ticker_verified=False,
            ticker_verification_source="none",
            ticker_verification_date=date.today().isoformat(),
            ticker_match_confidence=None,
        )

    if verification.delisted_or_acquired:
        logger.warning(
            "%s (%s) is delisted/acquired: %s", match.ticker, raw.company_name, verification.reason
        )
    elif not verification.verified:
        logger.warning(
            "Ticker verification failed for %s (%s): %s",
            match.ticker,
            raw.company_name,
            verification.reason,
        )

    return Company(
        ticker=match.ticker,
        company_name=match.matched_company_name,
        ticker_verified=verification.verified,
        ticker_verification_source=verification.source,
        ticker_verification_date=verification.checked_date,
        ticker_verification_reason=verification.reason,
        ticker_match_confidence=match.confidence,
        delisted_or_acquired=verification.delisted_or_acquired,
    )


def run(*, generate_summaries: bool = True) -> RunSummary:
    """Runs the pipeline once. Returns a RunSummary (processed designation_ids
    plus failure counts — see RunSummary.one_line())."""
    db.init_db()
    raw_designations = []
    for source in SOURCES:
        source_designations = source.fetch_new_designations()
        logger.info(
            "Fetched %d designation(s) from %s", len(source_designations), source.__name__
        )
        raw_designations.extend(source_designations)

    processed_ids = []
    run_summary = RunSummary(processed_ids=processed_ids)
    with db.connect() as conn:
        for raw in raw_designations:
            company = _resolve_company(raw)
            db.upsert_company(conn, company)
            if company.delisted_or_acquired:
                run_summary.delisted_or_acquired += 1
            elif not company.ticker_verified:
                run_summary.unverified_tickers += 1

            trial = None
            if raw.trial_id:
                try:
                    trial = fetch_trial(raw.trial_id)
                except Exception:
                    logger.exception("Trial lookup failed for %s", raw.trial_id)
                    run_summary.trial_lookup_failures += 1
                if trial:
                    db.upsert_trial(conn, trial)
                else:
                    logger.warning("No ClinicalTrials.gov record for %s", raw.trial_id)

            designation_id = _designation_id(raw)
            designation = Designation(
                designation_id=designation_id,
                ticker=company.ticker,
                source=raw.source,
                type=raw.type,
                date_granted=raw.date_granted,
                drug_name=raw.drug_name,
                indication=raw.indication,
                trial_id=raw.trial_id,
                data_source=raw.data_source,
                data_as_of_date=raw.data_as_of_date,
                raw_company_name=raw.company_name,
                date_granted_source=raw.date_granted_source,
            )

            if generate_summaries:
                try:
                    summary = summarize_designation(
                        drug_name=raw.drug_name,
                        company_name=company.company_name,
                        ticker=company.ticker,
                        designation_type=raw.type,
                        date_granted=raw.date_granted,
                        indication=raw.indication,
                        phase=trial.phase if trial else None,
                        status=trial.status if trial else None,
                    )
                    designation.summary_text = summary.full_text
                    designation.summary_confidence_flag = summary.confidence_flag
                    designation.summary_generated_at = summary.generated_at
                except Exception:
                    logger.exception(
                        "Summarization failed for designation_id=%s", designation_id
                    )
                    run_summary.summarization_failures += 1

            db.upsert_designation(conn, designation)
            processed_ids.append(designation_id)

            # Roadmap step 6: track record trigger. date_flagged is
            # deliberately today, not raw.date_granted — the tracking
            # clock starts when the pipeline first sees this flag, not
            # whenever the underlying regulatory designation happened
            # (which can be years in the past, e.g. Casgevy's 2020 PRIME
            # grant — starting the clock there would mean the 3/6/12-month
            # checkpoints are already overdue before tracking even begins).
            if designation.summary_confidence_flag in track_record.TRACKABLE_BIOTECH_FLAGS:
                track_record.flag_entry(
                    conn,
                    entry_id=designation_id,
                    entry_type="designation",
                    ticker=company.ticker,
                    flag_given=designation.summary_confidence_flag,
                )

    return run_summary
