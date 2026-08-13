"""Step 4 of the MVP roadmap: weekly email digest, plain text, no dashboard.

Ships the full current snapshot of both screeners on every run — biotech
designations (FDA + EMA) and founder-led Tier 1 companies — pulled straight
from the same companies/designations/ownership tables both pipelines write
to. It is not yet scoped to "what changed since last time" (that's roadmap
step 5's diff view); every run currently emits everything in the database.

Every line item carries its source and as-of date (guardrail, brief section
6), and the biotech/founder-led sections stay clearly separate rather than
merged, mirroring how the two screeners' data stays separate in the schema.
"""

import smtplib
import textwrap
from dataclasses import dataclass
from datetime import date
from email.mime.text import MIMEText

from signal_screener import db
from signal_screener.config import (
    DIGEST_FROM_EMAIL,
    DIGEST_TO_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
)

WRAP_WIDTH = 88

DISCLAIMER = (
    "This digest is a research aid, not investment advice. Confidence flags "
    "and founder tiers describe clinical/ownership facts, not buy or sell "
    "recommendations. Ticker matches marked \"unverified\" have not been "
    "confirmed against an independent source and should not be trusted."
)


@dataclass
class Digest:
    subject: str
    body: str


def _wrap(text: str, indent: str = "    ") -> str:
    return "\n".join(
        textwrap.wrap(
            text, width=WRAP_WIDTH, initial_indent=indent, subsequent_indent=indent
        )
    )


def _ticker_label(ticker: str, verified: bool) -> str:
    if ticker.startswith("UNVERIFIED::") or not verified:
        return f"{ticker} [UNVERIFIED TICKER]"
    return ticker


def _build_biotech_section(conn) -> str:
    rows = conn.execute(
        """
        SELECT d.*, c.company_name AS resolved_company_name, c.ticker_verified
        FROM designations d
        JOIN companies c ON c.ticker = d.ticker
        ORDER BY d.date_granted DESC, d.drug_name
        """
    ).fetchall()

    if not rows:
        return "No biotech designations on file yet.\n"

    lines = []
    for row in rows:
        ticker_label = _ticker_label(row["ticker"], bool(row["ticker_verified"]))
        lines.append(
            f"[{row['source']}] {row['drug_name']} "
            f"— {row['resolved_company_name']} ({ticker_label})"
        )
        lines.append(f"    Designation: {row['type']}, granted {row['date_granted']}")
        flag = row["summary_confidence_flag"] or "not yet summarized"
        lines.append(f"    Confidence: {flag}")
        if row["summary_text"]:
            lines.append(_wrap(row["summary_text"]))
        lines.append(
            f"    Source: {row['data_source']} (as of {row['data_as_of_date']})"
        )
        lines.append("")
    return "\n".join(lines)


def _build_founder_section(conn) -> str:
    rows = conn.execute(
        """
        SELECT * FROM companies
        WHERE listing_type = 'ADR'
        ORDER BY
            CASE founder_tier
                WHEN 'Founder-CEO' THEN 0
                WHEN 'Founder-Chair' THEN 1
                WHEN 'Founder-departed' THEN 2
                ELSE 3
            END,
            company_name
        """
    ).fetchall()

    if not rows:
        return "No founder-led companies on file yet.\n"

    lines = []
    for row in rows:
        ticker_label = _ticker_label(row["ticker"], bool(row["ticker_verified"]))
        lines.append(f"{ticker_label} — {row['company_name']} [{row['founder_tier']}]")

        ownership = conn.execute(
            "SELECT * FROM ownership WHERE ticker = ? ORDER BY as_of_date DESC, "
            "ownership_id DESC LIMIT 1",
            (row["ticker"],),
        ).fetchone()
        if ownership:
            pct = (
                f"{ownership['ownership_pct']:.1f}%"
                if ownership["ownership_pct"] is not None
                else "not disclosed"
            )
            lines.append(f"    Founder: {row['founder_name']} — {ownership['role']} ({pct})")
        elif row["founder_name"]:
            lines.append(f"    Founder: {row['founder_name']}")

        if row["network_effect"]:
            lines.append(_wrap(f"Network effect: {row['network_effect']}"))

        if row["founder_tier_source"]:
            lines.append(
                f"    Source: {row['founder_tier_source']} "
                f"(as of {row['founder_tier_as_of_date']})"
            )
        lines.append("")
    return "\n".join(lines)


def build_digest() -> Digest:
    db.init_db()
    with db.connect() as conn:
        biotech_section = _build_biotech_section(conn)
        founder_section = _build_founder_section(conn)

    today = date.today().isoformat()
    body = f"""SIGNAL SCREENER — WEEKLY DIGEST
{today}

{DISCLAIMER}

================================================
BIOTECH SIGNALS (FDA Breakthrough Therapy / EMA PRIME)
================================================

{biotech_section}
================================================
FOUNDER-LED COMPANIES (Tier 1 / ADR)
================================================

{founder_section}"""

    return Digest(subject=f"Signal Screener Weekly Digest — {today}", body=body)


def send_digest(digest: Digest) -> None:
    missing = [
        name
        for name, value in [
            ("SMTP_USERNAME", SMTP_USERNAME),
            ("SMTP_PASSWORD", SMTP_PASSWORD),
            ("DIGEST_TO_EMAIL", DIGEST_TO_EMAIL),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing email config: {', '.join(missing)} (see .env.example)"
        )

    message = MIMEText(digest.body, "plain")
    message["Subject"] = digest.subject
    message["From"] = DIGEST_FROM_EMAIL
    message["To"] = DIGEST_TO_EMAIL

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(DIGEST_FROM_EMAIL, [DIGEST_TO_EMAIL], message.as_string())
