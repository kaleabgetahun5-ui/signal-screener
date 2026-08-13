import importlib

import signal_screener.config as config


def test_build_digest_runs_against_empty_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "empty.db")
    importlib.reload(importlib.import_module("signal_screener.db"))
    digest = importlib.reload(importlib.import_module("signal_screener.digest"))

    result = digest.build_digest()
    assert "Weekly Digest" in result.subject
    assert "No biotech designations on file yet." in result.body
    assert "No founder-led companies on file yet." in result.body
    assert "not investment advice" in result.body


def test_send_digest_raises_without_config(monkeypatch):
    import signal_screener.digest as digest

    monkeypatch.setattr(digest, "SMTP_USERNAME", None)
    monkeypatch.setattr(digest, "SMTP_PASSWORD", None)
    monkeypatch.setattr(digest, "DIGEST_TO_EMAIL", None)

    try:
        digest.send_digest(digest.Digest(subject="x", body="y"))
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "SMTP_USERNAME" in str(e)
