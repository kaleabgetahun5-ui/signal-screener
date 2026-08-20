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
