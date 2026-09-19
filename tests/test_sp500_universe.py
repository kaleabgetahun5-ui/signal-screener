"""Tests for sources/sp500_universe.py's Wikipedia table parser — mocked
HTTP, no live network call, but the fake table shape mirrors the real
page's structure (see live-checked column order in the module docstring)."""

from unittest.mock import MagicMock, patch

import pytest

from signal_screener.sources import sp500_universe


def _fake_table_html(rows: list[list[str]]) -> str:
    header = (
        "<tr><th>Symbol</th><th>Security</th><th>GICSSector</th>"
        "<th>GICS Sub-Industry</th><th>Headquarters Location</th>"
        "<th>Date added</th><th>CIK</th><th>Founded</th></tr>"
    )
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f'<table id="constituents">{header}{body}</table>'


def _padded_rows(real_rows: list[list[str]], total: int = 450) -> list[list[str]]:
    """Pads out to clear fetch_sp500_constituents' ~500-row sanity floor
    without needing 500 lines of real-looking fixture data."""
    filler_rows = [
        [f"F{i}", f"Filler Co {i}", "Industrials", "Sub", "Nowhere", "2000-01-01", "0000000000", "2000"]
        for i in range(max(0, total - len(real_rows)))
    ]
    return real_rows + filler_rows


def test_parses_real_rows_and_normalizes_dual_class_tickers():
    rows = _padded_rows(
        [
            ["MMM", "3M", "Industrials", "Industrial Conglomerates", "Saint Paul, Minnesota", "1957-03-04", "0000066740", "1902"],
            ["BRK.B", "Berkshire Hathaway", "Financials", "Multi-Sector Holdings", "Omaha, Nebraska", "2010-02-16", "0001067983", "1839"],
        ]
    )
    html = _fake_table_html(rows)
    with patch.object(sp500_universe, "requests") as mock_requests:
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_requests.get.return_value = mock_resp

        constituents = sp500_universe.fetch_sp500_constituents()

    by_ticker = {c.ticker: c for c in constituents}
    assert by_ticker["MMM"].company_name == "3M"
    assert by_ticker["MMM"].sector == "Industrials"
    assert by_ticker["MMM"].cik == "0000066740"
    # "BRK.B" -> "BRK-B" (Yahoo/SEC's dual-class ticker convention).
    assert "BRK-B" in by_ticker
    assert "BRK.B" not in by_ticker


def test_raises_if_table_missing():
    html = "<html><body>no table here</body></html>"
    with patch.object(sp500_universe, "requests") as mock_requests:
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_requests.get.return_value = mock_resp

        with pytest.raises(ValueError):
            sp500_universe.fetch_sp500_constituents()


def test_raises_if_row_count_looks_wrong():
    """A parser silently returning a truncated list would look identical
    to "nothing else found" to the discovery pipeline — this must fail
    loud instead."""
    rows = [["MMM", "3M", "Industrials", "Industrial Conglomerates", "Saint Paul, Minnesota", "1957-03-04", "0000066740", "1902"]]
    html = _fake_table_html(rows)
    with patch.object(sp500_universe, "requests") as mock_requests:
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_requests.get.return_value = mock_resp

        with pytest.raises(ValueError):
            sp500_universe.fetch_sp500_constituents()
