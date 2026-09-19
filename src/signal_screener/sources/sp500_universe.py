"""S&P 500 constituent list for the discovery feature (brief section 3's
Tier 1/Tier 2 founder-led screener was hand-curated to 9 companies; this
scans the rest of the S&P 500 for additional founder-led candidates).

Source: Wikipedia's "List of S&P 500 companies" page. Named here
explicitly rather than left implicit, because it's a real limitation worth
being honest about, the same way sources/founder_led_tier2.py's docstring
corrects the brief's own stated sources: this is a community-maintained
page, not S&P Dow Jones Indices' own licensed constituent feed (that's a
paid product this project doesn't have access to). In practice the page is
actively maintained, cites its own changes against S&P's public press
releases, and is the same page commonly used for exactly this purpose —
but a stale or vandalized edit is a real (if unlikely) failure mode this
project's own "never silently trust a single unverified source" guardrail
would otherwise flag. The mitigation already exists elsewhere in the
pipeline, not here: every ticker this module returns still goes through
matching/ticker_verify.py's mandatory second-source check
(founder_discovery_pipeline.py) before it's treated as real, so a bad row
here fails closed (unverified, skipped) rather than silently propagating.

CIK is included because Wikipedia's table happens to carry it, but it's
NOT used to fetch filings — get_latest_annual_filing() (filings/
sec_edgar.py) re-resolves CIK from SEC's own company_tickers.json by
ticker, same as every other source in this pipeline, so a wrong/stale CIK
here can't cause a wrong filing to be fetched.
"""

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from signal_screener.config import SEC_USER_AGENT

SP500_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


@dataclass
class SP500Constituent:
    ticker: str
    company_name: str
    sector: str | None
    headquarters: str | None
    cik: str | None  # see module docstring — informational only, not used to fetch filings


def fetch_sp500_constituents() -> list[SP500Constituent]:
    """Live fetch + parse of the "constituents" table on the Wikipedia page
    above. Raises requests.RequestException on a network failure, or
    ValueError if the page's table structure has changed enough that this
    parser can no longer find what it expects — both deliberately
    propagate rather than returning a partial/guessed list, since a
    silently-truncated S&P 500 list would just look like "nothing else
    found" to the rest of the discovery pipeline."""
    resp = requests.get(
        SP500_WIKIPEDIA_URL,
        headers={"User-Agent": SEC_USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", {"id": "constituents"})
    if table is None:
        raise ValueError(
            "Wikipedia's S&P 500 page no longer has a table id='constituents' — "
            "page structure has changed, parser needs updating"
        )

    rows = table.find_all("tr")[1:]
    if len(rows) < 400:  # sanity floor — the real index has ~500 tickers
        raise ValueError(
            f"Only found {len(rows)} rows in the constituents table — "
            "expected ~500; page structure may have changed"
        )

    constituents = []
    for row in rows:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) < 7:
            continue
        ticker, company_name, sector = cells[0], cells[1], cells[2]
        headquarters, cik = cells[4], cells[6]
        # Wikipedia represents dual-class tickers as e.g. "BRK.B" — Yahoo/SEC
        # use "BRK-B". Normalized here, once, rather than at every downstream
        # call site.
        ticker = re.sub(r"\.", "-", ticker.strip())
        constituents.append(
            SP500Constituent(
                ticker=ticker,
                company_name=company_name,
                sector=sector or None,
                headquarters=headquarters or None,
                cik=cik or None,
            )
        )
    return constituents
