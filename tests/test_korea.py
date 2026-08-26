"""Tests for filings/korea.py (Tier 2, South Korea / DART). All external
HTTP calls are mocked — these check the request/response handling and
excerpt formatting, not a live check of DART, which would make the suite
flaky and require a real API key in CI.
"""

from unittest.mock import patch

import pytest

from signal_screener.filings import korea


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise korea.requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._json_data


def _exctv_response(items):
    return _FakeResponse({"status": "000", "message": "정상", "list": items})


def _empty_exctv_response():
    return _FakeResponse({"status": "013", "message": "no data", "list": []})


@pytest.fixture(autouse=True)
def _require_key(monkeypatch):
    monkeypatch.setattr(korea, "OPENDART_API_KEY", "test-key")


def test_fetch_leadership_excerpt_marks_the_founder_row():
    executives = [
        {
            "nm": "이해진",
            "ofcps": "사내이사",
            "rgist_exctv_at": "사내이사",
            "fte_at": "상근",
            "chrg_job": "이사회 의장",
            "mxmm_shrholdr_relate": "-",
        },
        {
            "nm": "최수연",
            "ofcps": "대표이사",
            "rgist_exctv_at": "사내이사",
            "fte_at": "상근",
            "chrg_job": "대표이사",
            "mxmm_shrholdr_relate": "-",
        },
    ]
    with patch.object(korea.requests, "get") as mock_get:
        mock_get.side_effect = [_exctv_response(executives), _empty_exctv_response()]
        excerpt = korea.fetch_leadership_excerpt("Naver", "이해진")

    assert "<- SUBJECT" in excerpt
    assert "이해진" in excerpt
    assert "이사회 의장" in excerpt
    assert "No DART substantial-holding disclosure" in excerpt


def test_fetch_leadership_excerpt_includes_major_holding_when_present():
    executives = [
        {"nm": "이해진", "ofcps": "사내이사", "rgist_exctv_at": "사내이사", "fte_at": "상근", "chrg_job": "이사회 의장", "mxmm_shrholdr_relate": "-"}
    ]
    holdings = [{"rcept_dt": "2026-01-01", "repror": "이해진", "stkrt": "6.5", "report_resn": "단순취득"}]

    def get(url, params=None, timeout=None):
        if url == korea.EXCTV_STTUS_URL:
            return _exctv_response(executives)
        assert url == korea.MAJOR_STOCK_URL
        return _FakeResponse({"status": "000", "message": "정상", "list": holdings})

    with patch.object(korea.requests, "get", side_effect=get):
        excerpt = korea.fetch_leadership_excerpt("Naver", "이해진")

    assert "6.5%" in excerpt
    assert "2026-01-01" in excerpt


def test_fetch_leadership_excerpt_raises_without_api_key(monkeypatch):
    monkeypatch.setattr(korea, "OPENDART_API_KEY", None)
    with pytest.raises(RuntimeError, match="OPENDART_API_KEY"):
        korea.fetch_leadership_excerpt("Naver", "이해진")


def test_fetch_leadership_excerpt_raises_when_no_period_has_data():
    with patch.object(korea.requests, "get", return_value=_empty_exctv_response()):
        with pytest.raises(RuntimeError, match="No executive status report"):
            korea.fetch_leadership_excerpt("Naver", "이해진")


def test_fetch_current_executives_tries_periods_until_one_has_data():
    """Regression case found live: the most-recent quarter isn't always
    filed yet — must fall through to older periods, not just return
    empty."""
    calls = {"n": 0}

    def get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            return _empty_exctv_response()
        return _exctv_response([{"nm": "이해진", "ofcps": "사내이사"}])

    with patch.object(korea.requests, "get", side_effect=get):
        result = korea.fetch_current_executives("Naver")

    assert len(result) == 1
    assert calls["n"] == 3


def test_check_role_predates_recency_window_finds_founder_in_earliest_report():
    old_executives = [{"nm": "이해진", "ofcps": "사내이사", "chrg_job": "이사회의장"}]
    with patch.object(korea.requests, "get", return_value=_exctv_response(old_executives)) as mock_get:
        anchor = korea.check_role_predates_recency_window("Naver", "이해진")

    assert anchor == "2015-12-31"
    # Queried the earliest available year specifically, not a recent one.
    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["bsns_year"] == korea.EARLIEST_AVAILABLE_YEAR
    assert called_params["reprt_code"] == korea.EARLIEST_REPRT_CODE


def test_check_role_predates_recency_window_returns_none_when_founder_absent():
    old_executives = [{"nm": "최수연", "ofcps": "대표이사"}]
    with patch.object(korea.requests, "get", return_value=_exctv_response(old_executives)):
        anchor = korea.check_role_predates_recency_window("Naver", "이해진")
    assert anchor is None


def test_check_role_predates_recency_window_returns_none_on_request_failure():
    with patch.object(
        korea.requests, "get", side_effect=korea.requests.ConnectionError("boom")
    ):
        anchor = korea.check_role_predates_recency_window("Naver", "이해진")
    assert anchor is None


def test_fetch_major_shareholding_returns_most_recent_when_multiple():
    holdings = [
        {"rcept_dt": "2020-01-01", "repror": "이해진", "stkrt": "8.0", "report_resn": "old"},
        {"rcept_dt": "2026-01-01", "repror": "이해진", "stkrt": "6.5", "report_resn": "new"},
    ]
    with patch.object(korea.requests, "get", return_value=_FakeResponse({"status": "000", "message": "", "list": holdings})):
        result = korea.fetch_major_shareholding("Naver", "이해진")
    assert result["rcept_dt"] == "2026-01-01"


def test_fetch_major_shareholding_returns_none_when_founder_not_a_major_holder():
    holdings = [{"rcept_dt": "2026-01-01", "repror": "BlackRock", "stkrt": "7.0", "report_resn": "-"}]
    with patch.object(korea.requests, "get", return_value=_FakeResponse({"status": "000", "message": "", "list": holdings})):
        result = korea.fetch_major_shareholding("Naver", "이해진")
    assert result is None
