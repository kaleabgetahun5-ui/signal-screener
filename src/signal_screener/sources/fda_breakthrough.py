"""FDA Breakthrough Therapy designation source.

FDA does not publish a structured API or downloadable feed of Breakthrough
Therapy designations as they're granted (openFDA's Drugs@FDA endpoint only
carries submission_type/status, not designation type; the designation lists
FDA does publish on fda.gov are periodically-updated HTML pages, not a data
feed). In practice these designations are tracked by watching company press
releases and FDA's own periodic approval summaries.

For this MVP step, new designations are curated manually into
data/fda_breakthrough_seed.csv (one row per designation) and read by
fetch_new_designations() below. The function signature is the integration
point: swapping in a scraper/API later means changing this file only, not
the rest of the pipeline.
"""

import csv

from signal_screener.config import SEED_DATA_DIR
from signal_screener.models import RawDesignation

SEED_FILE = SEED_DATA_DIR / "fda_breakthrough_seed.csv"

REQUIRED_COLUMNS = {
    "drug_name",
    "company_name",
    "date_granted",
    "indication",
    "trial_id",
    "data_as_of_date",
}


def fetch_new_designations() -> list[RawDesignation]:
    """Return all Breakthrough Therapy designations currently in the seed file.

    "New" filtering (skipping ones already stored) happens in the pipeline,
    not here, so this function stays a simple, swappable read of "everything
    the source currently has."
    """
    if not SEED_FILE.exists():
        raise FileNotFoundError(
            f"No seed file at {SEED_FILE}. Add designations there "
            "(see data/fda_breakthrough_seed.csv.example for the format)."
        )

    designations = []
    with SEED_FILE.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Seed file missing required columns: {missing}")

        for row in reader:
            designations.append(
                RawDesignation(
                    source="FDA",
                    type="Breakthrough Therapy",
                    date_granted=row["date_granted"].strip(),
                    drug_name=row["drug_name"].strip(),
                    company_name=row["company_name"].strip(),
                    indication=row["indication"].strip(),
                    trial_id=(row.get("trial_id") or "").strip() or None,
                    data_source=f"manual_seed:{SEED_FILE.name}",
                    data_as_of_date=row["data_as_of_date"].strip(),
                )
            )
    return designations
