"""Tests for roadmap step 5: the "new since last visit" diff view and
personal notes rendering (site.py)."""

import importlib

import signal_screener.config as config


def test_is_new_helper():
    from signal_screener.site import _is_new

    assert _is_new({"first_seen_at": "2026-08-14T00:00:00+00:00"}, None) is False
    assert _is_new({"first_seen_at": None}, "2026-08-13T00:00:00+00:00") is False
    assert (
        _is_new({"first_seen_at": "2026-08-14T00:00:00+00:00"}, "2026-08-13T00:00:00+00:00")
        is True
    )
    assert (
        _is_new({"first_seen_at": "2026-08-12T00:00:00+00:00"}, "2026-08-13T00:00:00+00:00")
        is False
    )


def _reload(tmp_path, monkeypatch, name):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    importlib.reload(importlib.import_module("signal_screener.db"))
    return importlib.reload(importlib.import_module(f"signal_screener.{name}"))


def test_build_site_html_diff_view_across_three_generations(tmp_path, monkeypatch):
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company, Designation

    # 1. First-ever generation: nothing to diff against yet.
    html_1 = site.build_site_html()
    assert "first generated snapshot" in html_1
    assert "Test Drug" not in html_1

    # 2. A pipeline run adds a new designation between generations.
    with db.connect() as conn:
        db.upsert_company(conn, Company(ticker="TEST", company_name="Test Co", ticker_verified=True))
        db.upsert_designation(
            conn,
            Designation(
                designation_id="abc123",
                ticker="TEST",
                source="FDA",
                type="Breakthrough Therapy",
                date_granted="2026-01-01",
                drug_name="Test Drug",
                indication="Test indication",
                trial_id=None,
                data_source="unit_test",
                data_as_of_date="2026-01-01",
                raw_company_name="Test Co",
            ),
        )

    html_2 = site.build_site_html()
    assert "Nothing new since your last visit" not in html_2
    # Appears twice: once in "New since last visit", once in the main
    # "Biotech signals" section below it — same card markup both times.
    assert html_2.count("Test Drug") == 2

    # 3. Nothing added since generation #2 — the new-designation card must
    # now only appear in the main section, not "New since last visit."
    html_3 = site.build_site_html()
    assert "Nothing new since your last visit" in html_3
    assert html_3.count("Test Drug") == 1


def test_delisted_biotech_entries_render_in_archive_not_main_section(tmp_path, monkeypatch):
    """A delisted/acquired biotech designation moves to the "Archive"
    section instead of the main "Biotech signals" list — same card
    markup, just partitioned by companies.delisted_or_acquired. An active
    entry does the reverse: main section only, never the archive."""
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company, Designation

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(
            conn,
            Company(
                ticker="DEAD",
                company_name="Delisted Co",
                ticker_verified=False,
                delisted_or_acquired=True,
                ticker_verification_reason="confirmed delisted for testing",
            ),
        )
        db.upsert_designation(
            conn,
            Designation(
                designation_id="dead123",
                ticker="DEAD",
                source="FDA",
                type="Breakthrough Therapy",
                date_granted="2020-01-01",
                drug_name="Archived Drug",
                indication="Test indication",
                trial_id=None,
                data_source="unit_test",
                data_as_of_date="2020-01-01",
                raw_company_name="Delisted Co",
            ),
        )
        db.upsert_company(conn, Company(ticker="LIVE", company_name="Live Co", ticker_verified=True))
        db.upsert_designation(
            conn,
            Designation(
                designation_id="live123",
                ticker="LIVE",
                source="FDA",
                type="Breakthrough Therapy",
                date_granted="2026-01-01",
                drug_name="Active Drug",
                indication="Test indication",
                trial_id=None,
                data_source="unit_test",
                data_as_of_date="2026-01-01",
                raw_company_name="Live Co",
            ),
        )

    html_out = site.build_site_html()
    archive_section, _, rest = html_out.partition('Founder-led companies</h2>')
    biotech_section, _, archive_only = archive_section.partition("Archive — delisted")

    assert "Archived Drug" not in biotech_section
    assert "Archived Drug" in archive_only
    assert "Active Drug" in biotech_section
    assert "Active Drug" not in archive_only


def test_founder_departed_renders_in_no_longer_founder_led_subsection(tmp_path, monkeypatch):
    """A Founder-departed company renders in a secondary "No longer
    founder-led" group within the main "Founder-led companies" section —
    not blended into the primary Founder-CEO/Founder-Chair list (the two
    tiers track_record.py actually triggers on), and not moved to the
    delisted/acquired Archive, since that section means "no longer
    tradable," which isn't true for a Founder-departed company."""
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(
            conn,
            Company(
                ticker="CEO1",
                company_name="Still Founder Led Co",
                ticker_verified=True,
                listing_type="ADR",
                founder_tier="Founder-CEO",
            ),
        )
        db.upsert_company(
            conn,
            Company(
                ticker="DEP1",
                company_name="Founder Departed Co",
                ticker_verified=True,
                listing_type="ADR",
                founder_tier="Founder-departed",
            ),
        )

    html_out = site.build_site_html()

    archive_and_earlier, _, founder_section = html_out.partition("Founder-led companies</h2>")
    primary_group, has_subsection, departed_group = founder_section.partition(
        "No longer founder-led"
    )

    assert has_subsection  # the labeled subsection heading is present at all
    assert "Still Founder Led Co" in primary_group
    assert "Founder Departed Co" not in primary_group
    assert "Founder Departed Co" in departed_group
    assert "Still Founder Led Co" not in departed_group
    # Not diverted into the delisted/acquired Archive, which renders
    # entirely before "Founder-led companies</h2>".
    assert "Founder Departed Co" not in archive_and_earlier


def test_notes_render_on_biotech_card(tmp_path, monkeypatch):
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company, Designation

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(conn, Company(ticker="TEST", company_name="Test Co", ticker_verified=True))
        db.upsert_designation(
            conn,
            Designation(
                designation_id="abc123",
                ticker="TEST",
                source="FDA",
                type="Breakthrough Therapy",
                date_granted="2026-01-01",
                drug_name="Test Drug",
                indication="Test indication",
                trial_id=None,
                data_source="unit_test",
                data_as_of_date="2026-01-01",
                raw_company_name="Test Co",
            ),
        )
        db.insert_user_note(conn, "abc123", "Worth watching the Phase 2 readout.", "2026-08-14")

    html_out = site.build_site_html()
    assert "Your notes" in html_out
    assert "Worth watching the Phase 2 readout." in html_out


def test_format_market_cap():
    from signal_screener.site import _format_market_cap

    assert _format_market_cap(99317571584, "USD") == "99.3B USD"
    assert _format_market_cap(4098172125184, "HKD") == "4.1T HKD"
    assert _format_market_cap(500_000_000, "EUR") == "500.0M EUR"
    assert _format_market_cap(12345, None) == "12,345"
    assert _format_market_cap(None, "USD") is None


def test_founder_card_shows_valuation_metrics_when_present(tmp_path, monkeypatch):
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(
            conn,
            Company(
                ticker="TEST",
                company_name="Test Co",
                ticker_verified=True,
                listing_type="ADR",
                founder_tier="Founder-CEO",
                market_cap=99317571584,
                currency="USD",
                trailing_pe=53.41,
                forward_pe=34.47,
                fifty_two_week_low=1495.0,
                fifty_two_week_high=2548.5,
                beta=1.312,
                dividend_yield_pct=None,
                valuation_as_of_date="2026-08-28",
                valuation_source="yahoo_finance_quotesummary",
            ),
        )

    html_out = site.build_site_html()
    assert "99.3B USD" in html_out
    assert "53.4" in html_out  # trailing P/E
    assert "(fwd 34.5)" in html_out
    assert "1,495.00" in html_out and "2,548.50" in html_out
    assert "Beta:</strong> 1.31" in html_out
    assert "(as of 2026-08-28)" in html_out
    # No dividend yield on file for this one — must not render a
    # fabricated 0.00%.
    assert "Dividend yield" not in html_out


def test_founder_card_omits_valuation_block_when_no_data(tmp_path, monkeypatch):
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(
            conn,
            Company(
                ticker="TEST",
                company_name="Test Co",
                ticker_verified=True,
                listing_type="ADR",
                founder_tier="Founder-CEO",
            ),
        )

    html_out = site.build_site_html()
    assert "Test Co" in html_out
    assert "Market cap" not in html_out
    assert '<div class="meta valuation">' not in html_out


def test_founder_card_shows_backtest_bars_when_present(tmp_path, monkeypatch):
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(
            conn,
            Company(
                ticker="TEST",
                company_name="Test Co",
                ticker_verified=True,
                listing_type="ADR",
                founder_tier="Founder-CEO",
                currency="USD",
                ipo_date="2007-08-10",
                ipo_price=28.5,
                backtest_current_price=1966.25,
                sp500_price_at_ipo=1453.64,
                sp500_current_price=7711.76,
                backtest_as_of_date="2026-08-28",
                backtest_source="yahoo_finance_chart",
            ),
        )

    html_out = site.build_site_html()
    assert '<div class="backtest">' in html_out
    assert "$100 invested at IPO (2007-08-10) vs. S&amp;P 500" in html_out
    assert "TEST" in html_out
    # 1966.25/28.5 * 100 ≈ 6899 (the larger of the two -> full-width bar)
    assert "~$6,899" in html_out
    # 7711.76/1453.64 * 100 ≈ 531 (the smaller -> proportionally narrower)
    assert "~$531" in html_out
    assert 'style="width:100.0%"' in html_out
    assert "dividends not included" in html_out
    # Same currency (USD) on both sides — no FX caveat needed.
    assert "not adjusted for exchange-rate" not in html_out


def test_founder_card_backtest_notes_fx_caveat_for_non_usd_company(tmp_path, monkeypatch):
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(
            conn,
            Company(
                ticker="0700.HK",
                company_name="Tencent Holdings",
                ticker_verified=True,
                listing_type="primary",
                founder_tier="Founder-CEO",
                currency="HKD",
                ipo_date="2004-06-16",
                ipo_price=0.765,
                backtest_current_price=455.2,
                sp500_price_at_ipo=1133.56,
                sp500_current_price=7711.76,
                backtest_as_of_date="2026-08-28",
                backtest_source="yahoo_finance_chart",
            ),
        )

    html_out = site.build_site_html()
    assert "not adjusted for exchange-rate movement" in html_out
    # The company's own bar value is labeled in HKD, not implied USD.
    assert "HKD" in html_out
    assert "~$" in html_out  # S&P 500's bar is still USD-labeled


def test_founder_card_omits_backtest_block_when_no_data(tmp_path, monkeypatch):
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(
            conn,
            Company(
                ticker="TEST",
                company_name="Test Co",
                ticker_verified=True,
                listing_type="ADR",
                founder_tier="Founder-CEO",
            ),
        )

    html_out = site.build_site_html()
    assert '<div class="backtest">' not in html_out


def test_watchlist_section_empty_state(tmp_path, monkeypatch):
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    db.init_db()

    html_out = site.build_site_html()
    assert "Your watchlist is empty" in html_out
    assert "watchlist-add" in html_out


def test_watchlist_section_shows_starred_entry_and_not_unstarred(tmp_path, monkeypatch):
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company, Designation

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(conn, Company(ticker="TEST", company_name="Test Co", ticker_verified=True))
        db.upsert_designation(
            conn,
            Designation(
                designation_id="abc123",
                ticker="TEST",
                source="FDA",
                type="Breakthrough Therapy",
                date_granted="2026-01-01",
                drug_name="Starred Drug",
                indication="Test indication",
                trial_id=None,
                data_source="unit_test",
                data_as_of_date="2026-01-01",
                raw_company_name="Test Co",
            ),
        )
        db.upsert_company(
            conn,
            Company(
                ticker="OTHR",
                company_name="Other Co",
                ticker_verified=True,
                listing_type="ADR",
                founder_tier="Founder-CEO",
            ),
        )
        db.add_to_watchlist(conn, "abc123", "2026-08-27")

    html_out = site.build_site_html()
    assert "★ Your watchlist" in html_out
    # Starred biotech entry appears twice: once in the watchlist section,
    # once in the main "Biotech signals" section — same card markup.
    assert html_out.count("Starred Drug") == 2
    # Unstarred founder-led entry appears only in its own main section.
    assert html_out.count("Other Co") == 1


def test_arbitrary_watchlist_ticker_renders_distinctly_from_screened_entries(
    tmp_path, monkeypatch
):
    """A self-added ticker (no companies/designations row at all) must be
    visually and textually distinguished from a starred, already-screened
    pipeline entry — a different card class/color, an explicit "Self-
    added — not screened" flag instead of a tier/confidence pill, and its
    own labeled subsection, never mixed in as if it had passed the
    founder-led/biotech screen."""
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(
            conn,
            Company(
                ticker="OTHR",
                company_name="Screened Co",
                ticker_verified=True,
                listing_type="ADR",
                founder_tier="Founder-CEO",
            ),
        )
        db.add_to_watchlist(conn, "OTHR", "2026-08-27")
        db.add_to_watchlist(
            conn,
            "AAPL",
            "2026-08-27",
            entry_kind="arbitrary",
            company_name="Apple Inc.",
            verification_source="yahoo_finance_search",
            verification_date="2026-08-27",
            verification_reason="resolved 'aapl' to 'AAPL' ('Apple Inc.')",
        )

    html_out = site.build_site_html()
    assert "Self-added — not screened" in html_out
    assert "not screened by this pipeline" in html_out
    assert '<div class="card arbitrary">' in html_out
    assert "Apple Inc." in html_out
    # The self-added ticker never appears in the main "Founder-led
    # companies"/"Biotech signals" sections — it was never screened, so
    # it has no row there to render from in the first place.
    watchlist_section, _, rest = html_out.partition("Biotech signals</h2>")
    assert "Apple Inc." in watchlist_section
    assert "Apple Inc." not in rest


def test_no_notes_section_when_entry_has_no_notes(tmp_path, monkeypatch):
    site = _reload(tmp_path, monkeypatch, "site")
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(
            conn,
            Company(
                ticker="TEST",
                company_name="Test Co",
                ticker_verified=True,
                listing_type="ADR",
                founder_tier="Founder-CEO",
            ),
        )

    html_out = site.build_site_html()
    assert "Test Co" in html_out
    assert "Your notes" not in html_out
