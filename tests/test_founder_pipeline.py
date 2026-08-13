from signal_screener.founder_pipeline import _apply_recency_rule


def test_recent_transition_keeps_founder_chair():
    tier, reason = _apply_recency_rule("Founder-Chair", "2026-01-01")
    assert tier == "Founder-Chair"
    assert reason is None


def test_stale_transition_downgrades_to_departed():
    tier, reason = _apply_recency_rule("Founder-Chair", "2020-01-01")
    assert tier == "Founder-departed"
    assert reason is not None


def test_missing_transition_date_leaves_tier_unchanged():
    tier, reason = _apply_recency_rule("Founder-Chair", None)
    assert tier == "Founder-Chair"
    assert reason is None


def test_non_chair_tier_is_never_touched():
    tier, reason = _apply_recency_rule("Founder-CEO", "2015-01-01")
    assert tier == "Founder-CEO"
    assert reason is None
