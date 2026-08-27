"""Tests for filings/netherlands.py (Tier 2, Netherlands / Adyen).
External HTTP calls are mocked."""

from unittest.mock import patch

from signal_screener.filings import netherlands


class _FakeResponse:
    def __init__(self, content, status_code=200):
        # content may be str (decoded as .text) or bytes (for .content)
        if isinstance(content, str):
            self.text = content
            self.content = content.encode("utf-8")
        else:
            self.content = content
            self.text = content.decode("utf-8", errors="replace")
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise netherlands.requests.HTTPError(f"status {self.status_code}")


_GOVERNANCE_HTML = """
<html><body>
<div id="app"></div>
<script id="__NUXT_DATA__" type="application/json">
["ShallowReactive",1],{"name":2,"role":3},"Pieter van der Does","Co-Founder and Co-CEO",
"Pieter van der Does is an executive director, Co-Founder and Co-Chief Executive Officer
of the Company, responsible for strategy and commercial operations since founding Adyen in 2006."
</script>
</body></html>
"""

_AFM_CSV_HEADER = (
    '"Datum meldingsplicht";"Uitgevende instelling";"Meldingsplichtige";"Kvk-nr";"Plaats";'
    '"Soort aandeel";"Kapitaalbelang";"Stemrecht";"Wijze van beschikken";"Aantal aandelen";'
    '"Aantal stemmen";"Aantal equivalente aandelen";"Soort aandeel ENG";"Toelichting";'
    '"Soort aandeel procentuele verdeling";"Totale deelneming";"Rechtstreeks re\xebel";'
    '"Rechtstreeks potentieel";"Middellijk re\xebel";"Middellijk potentieel";'
    '"Totaal kapitaalbelang";"Rechtstreeks";"Middellijk"\r\n'
)

_AFM_CSV_ROWS = (
    '"2023-03-01 00:00:00";"Adyen N.V.";"P.W. van der Does";"";"Amsterdam";"Gewoon aandeel";'
    '"Re\xebel";"Re\xebel";"Middellijk<BR>(Spreng BV)";"922539.00000";"922539.00000";"";'
    '"Ordinary share";"";"Kapitaalbelang";"2,98 %";"0,00 %";"0,00 %";"2,98 %";"0,00 %";"";"";""\r\n'
    '"2023-03-01 00:00:00";"Adyen N.V.";"P.W. van der Does";"";"Amsterdam";"Gewoon aandeel";'
    '"Re\xebel";"Re\xebel";"Middellijk<BR>(Spreng BV)";"922539.00000";"922539.00000";"";'
    '"Ordinary share";"";"Stemrecht";"2,98 %";"0,00 %";"0,00 %";"2,98 %";"0,00 %";"";"";""\r\n'
    '"2018-06-13 00:00:00";"Adyen N.V.";"P.W. van der Does";"";"Amsterdam";"Gewoon aandeel";'
    '"Re\xebel";"Re\xebel";"Middellijk<BR>(Spreng BV)";"1415278.00000";"1415278.00000";"";'
    '"Ordinary share";"";"Kapitaalbelang";"4,81 %";"0,00 %";"0,00 %";"4,81 %";"0,00 %";"";"";""\r\n'
)

_AFM_CSV = (_AFM_CSV_HEADER + _AFM_CSV_ROWS).encode("cp1252")


def _fake_get(url, *args, **kwargs):
    if "afm.nl" in url:
        return _FakeResponse(_AFM_CSV)
    return _FakeResponse(_GOVERNANCE_HTML)


def test_fetch_leadership_excerpt_finds_founder_and_afm_notification():
    with patch.object(netherlands.requests, "get", side_effect=_fake_get):
        excerpt = netherlands.fetch_leadership_excerpt("Adyen", "Pieter van der Does")

    assert "Co-Chief Executive Officer" in excerpt
    assert "founding Adyen in 2006" in excerpt
    assert "2,98 %" in excerpt
    assert "2023-03-01" in excerpt
    # Picks the most recent (2023) notification, not the older 2018 one.
    assert "4,81 %" not in excerpt


def test_fetch_leadership_excerpt_reports_no_afm_notification_when_none_match():
    with patch.object(netherlands.requests, "get", side_effect=_fake_get):
        excerpt = netherlands.fetch_leadership_excerpt("Adyen", "Nobody Matching")

    assert "No AFM substantial-holdings notification on file" in excerpt


def test_fetch_leadership_excerpt_raises_on_governance_page_failure():
    with patch.object(
        netherlands.requests, "get", side_effect=netherlands.requests.ConnectionError("boom")
    ):
        try:
            netherlands.fetch_leadership_excerpt("Adyen", "Pieter van der Does")
            assert False, "expected an exception"
        except netherlands.requests.ConnectionError:
            pass


def test_afm_notifications_degrades_gracefully_on_request_failure():
    def _flaky_get(url, *args, **kwargs):
        if "afm.nl" in url:
            raise netherlands.requests.ConnectionError("boom")
        return _FakeResponse(_GOVERNANCE_HTML)

    with patch.object(netherlands.requests, "get", side_effect=_flaky_get):
        excerpt = netherlands.fetch_leadership_excerpt("Adyen", "Pieter van der Does")

    assert "No AFM substantial-holdings notification on file" in excerpt
