"""Tests for pipeline.py's summary caching: summarize_designation() should
only be called again when something material it actually sees (drug name,
resolved company name, ticker, designation type, date granted, indication,
trial phase/status) has changed since the stored summary was generated —
not unconditionally on every run, which a daily schedule would otherwise
turn into a 7x cost increase for identical output."""

import importlib
from unittest.mock import patch

import signal_screener.config as config


def test_summary_input_fingerprint_deterministic_and_sensitive_to_change():
    from signal_screener.pipeline import _summary_input_fingerprint

    kwargs = dict(
        drug_name="Tovorafenib",
        company_name="Day One Biopharmaceuticals",
        ticker="DAWN",
        designation_type="Breakthrough Therapy",
        date_granted="2022-08-15",
        indication="pediatric low-grade glioma",
        phase="Phase 2",
        status="Recruiting",
    )
    assert _summary_input_fingerprint(**kwargs) == _summary_input_fingerprint(**kwargs)

    changed = dict(kwargs, status="Completed")
    assert _summary_input_fingerprint(**kwargs) != _summary_input_fingerprint(**changed)


def _reload(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    importlib.reload(importlib.import_module("signal_screener.db"))
    return importlib.reload(importlib.import_module("signal_screener.pipeline"))


def _raw_designation(pipeline, *, phase="Phase 2", status="Recruiting"):
    from signal_screener.models import RawDesignation

    return RawDesignation(
        source="FDA",
        type="Breakthrough Therapy",
        date_granted="2022-08-15",
        drug_name="Tovorafenib",
        company_name="Day One Biopharmaceuticals",
        indication="pediatric low-grade glioma",
        trial_id="NCT12345678",
        data_source="unit_test",
        data_as_of_date="2026-08-29",
    ), phase, status


def _run_with_mocks(pipeline, phase, status, *, summary_call_count):
    from signal_screener.matching.ticker_match import TickerMatch
    from signal_screener.matching.ticker_verify import VerificationResult
    from signal_screener.summarize.claude_summary import BiotechSummary
    from signal_screener.trials.clinicaltrials import Trial

    raw, _, _ = _raw_designation(pipeline)
    fake_source = type("FakeSource", (), {"fetch_new_designations": staticmethod(lambda: [raw])})

    match = TickerMatch(ticker="DAWN", matched_company_name="Day One Biopharmaceuticals", confidence=100.0)
    verification = VerificationResult(
        verified=True,
        source="yahoo_finance_search",
        checked_date="2026-08-29",
        reason="symbol and company name confirmed (score=100)",
    )
    trial = Trial(
        trial_id="NCT12345678",
        registry="ClinicalTrials.gov",
        phase=phase,
        status=status,
        start_date="2021-01-01",
        primary_completion_date="2027-01-01",
        condition="pediatric low-grade glioma",
        fetched_at="2026-08-29T00:00:00+00:00",
    )

    def fake_summarize(**kwargs):
        summary_call_count["n"] += 1
        return BiotechSummary(
            explanation="A summary.",
            differentiation="Differentiated.",
            confidence_flag="Moderate signal",
            generated_at="2026-08-29T00:00:00+00:00",
        )

    with patch.object(pipeline, "SOURCES", [fake_source]), patch.object(
        pipeline, "resolve_ticker", return_value=(match, verification)
    ), patch.object(pipeline, "fetch_trial", return_value=trial), patch.object(
        pipeline, "summarize_designation", side_effect=fake_summarize
    ):
        return pipeline.run()


def test_run_reuses_summary_when_nothing_material_changed(tmp_path, monkeypatch):
    pipeline = _reload(tmp_path, monkeypatch)
    call_count = {"n": 0}

    result_1 = _run_with_mocks(pipeline, "Phase 2", "Recruiting", summary_call_count=call_count)
    assert call_count["n"] == 1
    assert result_1.summaries_reused == 0

    result_2 = _run_with_mocks(pipeline, "Phase 2", "Recruiting", summary_call_count=call_count)
    assert call_count["n"] == 1  # not called again
    assert result_2.summaries_reused == 1

    db = importlib.import_module("signal_screener.db")
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM designations").fetchone()
        assert row["summary_text"] == "A summary. Differentiated."
        assert row["summary_generated_at"] == "2026-08-29T00:00:00+00:00"


def test_run_regenerates_summary_when_trial_phase_changes(tmp_path, monkeypatch):
    pipeline = _reload(tmp_path, monkeypatch)
    call_count = {"n": 0}

    _run_with_mocks(pipeline, "Phase 2", "Recruiting", summary_call_count=call_count)
    assert call_count["n"] == 1

    result_2 = _run_with_mocks(pipeline, "Phase 3", "Recruiting", summary_call_count=call_count)
    assert call_count["n"] == 2  # regenerated — trial phase changed
    assert result_2.summaries_reused == 0
