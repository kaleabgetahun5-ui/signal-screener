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
    assert "Warning" not in out
    assert "Added TEST to your watchlist." in out

    # Adding again reports it was already there, not a second insert.
    monkeypatch.setattr("sys.argv", ["signal-screener", "watchlist-add", "TEST"])
    cli.main()
    out = capsys.readouterr().out
    assert "already on your watchlist" in out

    monkeypatch.setattr("sys.argv", ["signal-screener", "watchlist-list"])
    cli.main()
    out = capsys.readouterr().out
    assert "TEST" in out

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


def test_watchlist_add_rejects_unscreened_entry_id(tmp_path, monkeypatch, capsys):
    """Unlike add-note, watchlist-add refuses an entry_id that hasn't been
    screened by the pipeline yet — an arbitrary outside ticker must never
    end up starred, since site.py/digest.py's watchlist section would
    otherwise just silently drop it with no indication anything failed."""
    cli = _reload_cli(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")

    monkeypatch.setattr("sys.argv", ["signal-screener", "watchlist-add", "NOTATICKER"])
    cli.main()

    out = capsys.readouterr().out
    assert "not adding it" in out
    assert "Added" not in out

    db.init_db()
    with db.connect() as conn:
        assert db.get_watchlist_entry_ids(conn) == set()
