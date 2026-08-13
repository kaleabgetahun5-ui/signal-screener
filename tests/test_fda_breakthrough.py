from signal_screener.sources.fda_breakthrough import fetch_new_designations


def test_fetch_new_designations_reads_seed_csv():
    designations = fetch_new_designations()
    assert len(designations) >= 3
    first = designations[0]
    assert first.source == "FDA"
    assert first.type == "Breakthrough Therapy"
    assert first.drug_name
    assert first.company_name
    assert first.trial_id.startswith("NCT")
