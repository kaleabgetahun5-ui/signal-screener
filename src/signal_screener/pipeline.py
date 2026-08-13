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
from datetime import date

from signal_screener import db
from signal_screener.matching.ticker_match import match_company_to_ticker, placeholder_ticker
from signal_screener.matching.ticker_verify import verify_ticker
from signal_screener.models import Company, Designation
from signal_screener.sources import ema_prime, fda_breakthrough
from signal_screener.summarize.claude_summary import summarize_designation
from signal_screener.trials.clinicaltrials import fetch_trial

logger = logging.getLogger(__name__)

SOURCES = [fda_breakthrough, ema_prime]


def _designation_id(raw) -> str:
    key = f"{raw.source}|{raw.type}|{raw.drug_name}|{raw.company_name}|{raw.date_granted}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _resolve_company(raw) -> Company:
    """Steps 2 + 3: match then mandatorily verify. Always returns a Company
    row — an unmatched or failed-verification entry is still recorded, just
    flagged unverified, per the brief's "never silently dropped" rule."""
    match = match_company_to_ticker(raw.company_name)

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

    verification = verify_ticker(match.ticker, raw.company_name)
    if not verification.verified:
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
        ticker_match_confidence=match.confidence,
    )


def run(*, generate_summaries: bool = True) -> list[str]:
    """Runs the pipeline once. Returns the list of designation_ids processed."""
    db.init_db()
    raw_designations = []
    for source in SOURCES:
        source_designations = source.fetch_new_designations()
        logger.info(
            "Fetched %d designation(s) from %s", len(source_designations), source.__name__
        )
        raw_designations.extend(source_designations)

    processed_ids = []
    with db.connect() as conn:
        for raw in raw_designations:
            company = _resolve_company(raw)
            db.upsert_company(conn, company)

            trial = None
            if raw.trial_id:
                try:
                    trial = fetch_trial(raw.trial_id)
                except Exception:
                    logger.exception("Trial lookup failed for %s", raw.trial_id)
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

            db.upsert_designation(conn, designation)
            processed_ids.append(designation_id)

    return processed_ids
