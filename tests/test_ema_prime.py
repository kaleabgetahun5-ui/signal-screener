import csv
from unittest.mock import patch

import pytest

from signal_screener.sources import ema_prime
from signal_screener.sources.ema_prime import fetch_new_designations


def test_fetch_new_designations_reads_seed_csv():
    designations = fetch_new_designations()
    assert len(designations) >= 2
    first = designations[0]
    assert first.source == "EMA"
    assert first.type == "PRIME"
    assert first.drug_name
    assert first.company_name
    assert first.trial_id.startswith("NCT")
    assert first.date_granted_source
    assert first.date_granted_source.startswith("http")


def test_fetch_new_designations_rejects_row_missing_date_granted_source(tmp_path):
    seed = tmp_path / "ema_prime_seed.csv"
    with seed.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["drug_name", "company_name", "date_granted", "date_granted_source", "indication", "trial_id", "data_as_of_date"]
        )
        writer.writerow(["Some Drug", "Some Company", "2026-01-01", "", "Some indication", "NCT00000000", "2026-08-12"])

    with patch.object(ema_prime, "SEED_FILE", seed):
        with pytest.raises(ValueError, match="date_granted_source"):
            fetch_new_designations()
