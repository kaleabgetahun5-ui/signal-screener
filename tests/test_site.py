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
