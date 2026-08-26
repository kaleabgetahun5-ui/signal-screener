"""Tests for filings/hongkong.py (Tier 2, Hong Kong / Tencent). External
HTTP calls are mocked."""

from unittest.mock import patch

from signal_screener.filings import hongkong


class _FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise hongkong.requests.HTTPError(f"status {self.status_code}")


_BOARD_PAGE_HTML = """
<html><body>
<p>Some unrelated boilerplate about board composition and independence.</p>
<h3>MA Huateng (Pony Ma)</h3>
<p>Chairman. Ma Huateng is an executive director, Chairman of the Board and
Chief Executive Officer of the Company. Mr Ma is one of the core founders
and has been employed by the Group since 1999.</p>
<h3>Someone Else</h3>
<p>President. Not the founder.</p>
</body></html>
"""


def test_fetch_leadership_excerpt_finds_founder_and_notes_ownership_gap():
    with patch.object(hongkong.requests, "get", return_value=_FakeResponse(_BOARD_PAGE_HTML)):
        excerpt = hongkong.fetch_leadership_excerpt("Tencent Holdings", "Ma Huateng")

    assert "Chairman of the Board" in excerpt
    assert "Chief Executive Officer" in excerpt
    assert "core founders" in excerpt
    assert "No ownership percentage source is accessible" in excerpt
    assert "bot-detection" in excerpt


def test_fetch_leadership_excerpt_raises_on_fetch_failure():
    with patch.object(
        hongkong.requests, "get", side_effect=hongkong.requests.ConnectionError("boom")
    ):
        try:
            hongkong.fetch_leadership_excerpt("Tencent Holdings", "Ma Huateng")
            assert False, "expected an exception"
        except hongkong.requests.ConnectionError:
            pass
