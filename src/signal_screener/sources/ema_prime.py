"""EMA PRIME designation source.

Unlike FDA, EMA does publish a real structured, monthly-updated file of
PRIME-designated medicines: list-medicines-currently-prime-scheme_en.xlsx
(confirmed live at https://www.ema.europa.eu/en/documents/other/
list-medicines-currently-prime-scheme_en.xlsx, columns: Name*, Substance
type, Therapeutic area, Therapeutic indication, Type of data supporting
request, Type of applicant, Date of granting PRIME eligibility).

But that file does not include the sponsoring company name — "Type of
applicant" is a size category (SME / Other / Large / Academic/non-profit),
not a company. Drug names at PRIME-designation stage are also often
pre-brand-name development codes. So company_name still can't be read off
the official source; it has to come from cross-referencing each drug name
against company press releases, same as FDA's designation dates.

Given that, this module follows the same pattern as fda_breakthrough.py:
new designations are curated manually into data/ema_prime_seed.csv (one row
per designation, company_name filled in by hand) and read by
fetch_new_designations() below, with the same swappable interface.
"""

import csv

from signal_screener.config import SEED_DATA_DIR
from signal_screener.models import RawDesignation

SEED_FILE = SEED_DATA_DIR / "ema_prime_seed.csv"

REQUIRED_COLUMNS = {
    "drug_name",
    "company_name",
    "date_granted",
    "date_granted_source",
    "indication",
    "trial_id",
    "data_as_of_date",
}


def fetch_new_designations() -> list[RawDesignation]:
    """Return all PRIME designations currently in the seed file.

    "New" filtering (skipping ones already stored) happens in the pipeline,
    not here, so this function stays a simple, swappable read of "everything
    the source currently has." Mirrors sources/fda_breakthrough.py.
    """
    if not SEED_FILE.exists():
        raise FileNotFoundError(
            f"No seed file at {SEED_FILE}. Add designations there "
            "(see data/ema_prime_seed.csv.example for the format)."
        )

    designations = []
    with SEED_FILE.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Seed file missing required columns: {missing}")

        for i, row in enumerate(reader, start=2):  # start=2: header is row 1
            date_granted_source = (row.get("date_granted_source") or "").strip()
            if not date_granted_source:
                raise ValueError(
                    f"{SEED_FILE.name} row {i} ({row.get('drug_name', '?')!r}): "
                    "date_granted_source is required — cite where date_granted "
                    "came from (a PRIME-grant press release or EMA document "
                    "URL), not left blank or guessed."
                )

            designations.append(
                RawDesignation(
                    source="EMA",
                    type="PRIME",
                    date_granted=row["date_granted"].strip(),
                    drug_name=row["drug_name"].strip(),
                    company_name=row["company_name"].strip(),
                    indication=row["indication"].strip(),
                    trial_id=(row.get("trial_id") or "").strip() or None,
                    data_source=f"manual_seed:{SEED_FILE.name}",
                    data_as_of_date=row["data_as_of_date"].strip(),
                    date_granted_source=date_granted_source,
                )
            )
    return designations
