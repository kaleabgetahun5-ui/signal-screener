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
