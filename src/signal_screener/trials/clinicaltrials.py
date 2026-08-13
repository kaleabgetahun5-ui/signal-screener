"""Pull trial detail from the public ClinicalTrials.gov API (v2, no key
required). Field paths confirmed against a live query against
https://clinicaltrials.gov/api/v2/studies.
"""

from datetime import datetime, timezone

import requests

from signal_screener.config import CLINICALTRIALS_API_BASE
from signal_screener.models import Trial


def fetch_trial(nct_id: str) -> Trial | None:
    resp = requests.get(
        f"{CLINICALTRIALS_API_BASE}/studies/{nct_id}",
        timeout=15,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    study = resp.json()

    protocol = study.get("protocolSection", {})
    status_module = protocol.get("statusModule", {})
    design_module = protocol.get("designModule", {})
    conditions_module = protocol.get("conditionsModule", {})

    phases = design_module.get("phases") or []
    conditions = conditions_module.get("conditions") or []

    return Trial(
        trial_id=nct_id,
        registry="ClinicalTrials.gov",
        phase=", ".join(phases) or None,
        status=status_module.get("overallStatus"),
        start_date=(status_module.get("startDateStruct") or {}).get("date"),
        primary_completion_date=(
            status_module.get("primaryCompletionDateStruct") or {}
        ).get("date"),
        condition="; ".join(conditions) or None,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
