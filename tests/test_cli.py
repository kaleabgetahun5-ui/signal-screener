import importlib

import signal_screener.config as config


def _reload_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    importlib.reload(importlib.import_module("signal_screener.db"))
    return importlib.reload(importlib.import_module("signal_screener.cli"))


def test_add_note_writes_note_and_warns_on_unknown_entry_id(tmp_path, monkeypatch, capsys):
    cli = _reload_cli(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")

    monkeypatch.setattr("sys.argv", ["signal-screener", "add-note", "NOTATICKER", "A test note."])
    cli.main()

    out = capsys.readouterr().out
    assert "Warning" in out
    assert "Note added to NOTATICKER" in out

    with db.connect() as conn:
        notes = db.get_notes_for_entry(conn, "NOTATICKER")
    assert len(notes) == 1
    assert notes[0]["note_text"] == "A test note."


def test_add_note_no_warning_for_known_ticker(tmp_path, monkeypatch, capsys):
    cli = _reload_cli(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(conn, Company(ticker="TEST", company_name="Test Co"))

    monkeypatch.setattr("sys.argv", ["signal-screener", "add-note", "TEST", "Watching this one."])
    cli.main()

    out = capsys.readouterr().out
    assert "Warning" not in out
    assert "Note added to TEST" in out


def test_watchlist_add_remove_list_roundtrip(tmp_path, monkeypatch, capsys):
    cli = _reload_cli(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(conn, Company(ticker="TEST", company_name="Test Co"))

    monkeypatch.setattr("sys.argv", ["signal-screener", "watchlist-add", "TEST"])
    cli.main()
    out = capsys.readouterr().out
    assert "screened pipeline entry" in out
    assert "Added TEST to your watchlist" in out

    # Adding again reports it was already there, not a second insert.
    monkeypatch.setattr("sys.argv", ["signal-screener", "watchlist-add", "TEST"])
    cli.main()
    out = capsys.readouterr().out
    assert "already on your watchlist" in out

    monkeypatch.setattr("sys.argv", ["signal-screener", "watchlist-list"])
    cli.main()
    out = capsys.readouterr().out
    assert "TEST" in out
    assert "[screened pipeline entry]" in out

    monkeypatch.setattr("sys.argv", ["signal-screener", "watchlist-remove", "TEST"])
    cli.main()
    out = capsys.readouterr().out
    assert "Removed TEST from your watchlist." in out

    monkeypatch.setattr("sys.argv", ["signal-screener", "watchlist-remove", "TEST"])
    cli.main()
    out = capsys.readouterr().out
    assert "wasn't on your watchlist" in out

    monkeypatch.setattr("sys.argv", ["signal-screener", "watchlist-list"])
    cli.main()
    out = capsys.readouterr().out
    assert "Your watchlist is empty." in out


def test_watchlist_add_rejects_invalid_arbitrary_ticker(tmp_path, monkeypatch, capsys):
    """A string that matches no pipeline entry AND doesn't resolve to a
    real security (a typo like "MADEUPTICKER123") must be rejected
    outright — never silently added as an unverified dangling entry."""
    cli = _reload_cli(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")
    from signal_screener.matching.ticker_verify import VerificationResult

    failed = VerificationResult(
        verified=False,
        source="yahoo_finance_search",
        checked_date="2026-08-27",
        reason="no listing found for symbol 'NOTATICKER'",
    )
    monkeypatch.setattr(cli, "resolve_arbitrary_ticker", lambda ticker: (failed, None, None))

    monkeypatch.setattr("sys.argv", ["signal-screener", "watchlist-add", "NOTATICKER"])
    cli.main()

    out = capsys.readouterr().out
    assert "not adding it" in out
    assert "Added" not in out

    db.init_db()
    with db.connect() as conn:
        assert db.get_watchlist_entry_ids(conn) == set()
        assert db.list_watchlist(conn) == []


def test_watchlist_add_accepts_verified_arbitrary_ticker(tmp_path, monkeypatch, capsys):
    """A ticker with no pipeline entry but a real, verified listing (e.g.
    an outside stock the user is independently curious about) is accepted
    and stored as entry_kind='arbitrary', using the resolved canonical
    symbol/name — not the user's raw input — so downstream links always
    resolve."""
    cli = _reload_cli(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")
    from signal_screener.matching.ticker_verify import VerificationResult

    verified = VerificationResult(
        verified=True,
        source="yahoo_finance_search",
        checked_date="2026-08-27",
        reason="resolved 'aapl' to 'AAPL' ('Apple Inc.')",
    )
    monkeypatch.setattr(
        cli, "resolve_arbitrary_ticker", lambda ticker: (verified, "AAPL", "Apple Inc.")
    )

    monkeypatch.setattr("sys.argv", ["signal-screener", "watchlist-add", "aapl"])
    cli.main()

    out = capsys.readouterr().out
    assert "Added AAPL (Apple Inc.) to your watchlist" in out
    assert "not screened by this pipeline" in out

    db.init_db()
    with db.connect() as conn:
        rows = db.list_watchlist(conn)
        assert len(rows) == 1
        assert rows[0]["entry_id"] == "AAPL"
        assert rows[0]["entry_kind"] == "arbitrary"
        assert rows[0]["company_name"] == "Apple Inc."
        assert db.get_watchlist_entry_ids(conn) == set()  # pipeline-only set


def _insert_fake_candidate(db, conn, ticker="DISC", status="pending"):
    from signal_screener.models import FounderCandidate

    db.insert_founder_candidate(
        conn,
        FounderCandidate(
            ticker=ticker,
            company_name="Discovered Co",
            founder_name="Jane Founder",
            current_title="Chief Executive Officer",
            ownership_pct=12.5,
            ownership_stake_text="12.5%",
            source_citation="DEF 14A:https://www.sec.gov/fake.htm",
            source_excerpt="Jane Founder is our founder and CEO, owning 12.5%.",
            discovered_at="2026-09-15",
            country="Nowhere, USA",
            exchange="NASDAQ",
            sector="Technology",
            status=status,
        ),
    )


def test_candidates_list_shows_pending_by_default(tmp_path, monkeypatch, capsys):
    cli = _reload_cli(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")

    db.init_db()
    with db.connect() as conn:
        _insert_fake_candidate(db, conn, ticker="DISC")

    monkeypatch.setattr("sys.argv", ["signal-screener", "candidates-list"])
    cli.main()
    out = capsys.readouterr().out
    assert "DISC" in out
    assert "Discovered Co" in out
    assert "Jane Founder" in out
    assert "Chief Executive Officer" in out
    assert "12.5%" in out
    assert "DEF 14A:https://www.sec.gov/fake.htm" in out


def test_candidates_list_empty_state(tmp_path, monkeypatch, capsys):
    cli = _reload_cli(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")
    db.init_db()

    monkeypatch.setattr("sys.argv", ["signal-screener", "candidates-list"])
    cli.main()
    out = capsys.readouterr().out
    assert "No candidates" in out


def test_candidates_approve_and_reject_roundtrip(tmp_path, monkeypatch, capsys):
    cli = _reload_cli(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")

    db.init_db()
    with db.connect() as conn:
        _insert_fake_candidate(db, conn, ticker="APPR")
        _insert_fake_candidate(db, conn, ticker="REJ")

    monkeypatch.setattr("sys.argv", ["signal-screener", "candidates-approve", "APPR"])
    cli.main()
    out = capsys.readouterr().out
    assert "Approved APPR" in out

    monkeypatch.setattr("sys.argv", ["signal-screener", "candidates-reject", "REJ"])
    cli.main()
    out = capsys.readouterr().out
    assert "Rejected REJ" in out

    with db.connect() as conn:
        assert db.get_founder_candidate(conn, "APPR")["status"] == "approved"
        assert db.get_founder_candidate(conn, "REJ")["status"] == "rejected"


def test_candidates_approve_unknown_ticker_reports_not_found(tmp_path, monkeypatch, capsys):
    cli = _reload_cli(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")
    db.init_db()

    monkeypatch.setattr("sys.argv", ["signal-screener", "candidates-approve", "NOPE"])
    cli.main()
    out = capsys.readouterr().out
    assert "isn't a known discovery candidate" in out


def test_discover_sp500_command_invokes_pipeline_and_prints_summary(tmp_path, monkeypatch, capsys):
    from unittest.mock import patch

    cli = _reload_cli(tmp_path, monkeypatch)

    class _FakeSummary:
        newly_discovered = ["NEWCO"]

        def one_line(self):
            return "3 scanned, 1 new candidate(s) found"

    with patch.object(cli.founder_discovery_pipeline, "run", return_value=_FakeSummary()) as mock_run:
        monkeypatch.setattr("sys.argv", ["signal-screener", "discover-sp500", "--limit", "5"])
        cli.main()

    mock_run.assert_called_once_with(limit=5)
    out = capsys.readouterr().out
    assert "3 scanned, 1 new candidate(s) found" in out
    assert "NEWCO" in out


def test_candidates_promote_command_invokes_pipeline_and_prints_summary(tmp_path, monkeypatch, capsys):
    from unittest.mock import patch

    cli = _reload_cli(tmp_path, monkeypatch)

    class _FakeSummary:
        def one_line(self):
            return "1 promoted (APPR), 0 lookup failure(s), 0 extraction failure(s)"

    with patch.object(
        cli.founder_discovery_pipeline, "promote_approved", return_value=_FakeSummary()
    ) as mock_promote:
        monkeypatch.setattr("sys.argv", ["signal-screener", "candidates-promote"])
        cli.main()

    mock_promote.assert_called_once_with()
    out = capsys.readouterr().out
    assert "1 promoted (APPR)" in out
