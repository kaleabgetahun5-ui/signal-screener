"""Orchestrates matching/ticker_match.py and matching/ticker_verify.py into
the single "give me the best ticker for this company name, checked against a
second source" call both pipeline.py and founder_pipeline.py need.

Kept separate from both modules so each stays independently testable (pure
matching, pure verification) while this is the one place that decides *when*
the OpenFIGI fallback in ticker_match.py is worth trying: SEC's primary
match is used as-is when it verifies, and the fallback is only attempted
when SEC found nothing or what it found didn't check out — never as a
second opinion on a match that's already confirmed.
"""

from signal_screener.matching.ticker_match import (
    TickerMatch,
    match_company_to_ticker,
    match_company_to_ticker_openfigi,
)
from signal_screener.matching.ticker_verify import (
    VerificationResult,
    check_delisted_or_acquired,
    verify_ticker,
)


def _apply_resolved_ticker(match: TickerMatch, verification: VerificationResult) -> TickerMatch:
    """Substitutes in Yahoo's exchange-suffixed symbol (verify_ticker's
    base-ticker fallback, Tier 2 international companies) so what's used
    downstream — site links, track_record.py price fetches — is a ticker
    those sources can actually resolve, not the bare guess OpenFIGI/
    ticker_match.py returned."""
    if verification.resolved_ticker and verification.resolved_ticker != match.ticker:
        return TickerMatch(
            ticker=verification.resolved_ticker,
            matched_company_name=match.matched_company_name,
            confidence=match.confidence,
        )
    return match


def resolve_ticker(company_name: str) -> tuple[TickerMatch | None, VerificationResult | None]:
    """Returns (match, verification). match is None only if no source
    offered any candidate at all. verification is None only alongside a
    None match. A non-None match with verification.verified == False is a
    deliberate "best guess, unconfirmed" result — never silently dropped —
    and verification.delisted_or_acquired == True on that result means it's
    specifically brief section 4's "listing status changed" case, not an
    unresolved match (see check_delisted_or_acquired)."""
    match = match_company_to_ticker(company_name)
    verification = verify_ticker(match.ticker, company_name) if match else None

    if match is not None and verification.verified:
        return _apply_resolved_ticker(match, verification), verification

    fallback_match = match_company_to_ticker_openfigi(company_name)
    fallback_verification = verify_ticker(fallback_match.ticker, company_name) if fallback_match else None

    if fallback_match is not None and fallback_verification.verified:
        return _apply_resolved_ticker(fallback_match, fallback_verification), fallback_verification

    # Neither source confirms an active, currently-tradable listing. Before
    # settling for a plain "unverified," check whether that's actually
    # because the company is a real SEC filer that's since delisted/been
    # acquired/gone private — a confirmed status change, not a bad match.
    delisted_result = check_delisted_or_acquired(company_name)
    if delisted_result is not None:
        return (fallback_match or match), delisted_result

    # Nothing verified and no delisted/acquired confirmation either. Prefer
    # the OpenFIGI guess when we have one — it's a name-search match against
    # the actual company rather than SEC's fuzzy score against arbitrary
    # titles, so it's typically the more relevant guess even unconfirmed —
    # falling back to the SEC guess, then to nothing (brief guardrail:
    # never silently drop an entry for lack of a match, but there has to be
    # a match to not drop).
    if fallback_match is not None:
        return fallback_match, fallback_verification
    if match is not None:
        return match, verification
    return None, None
