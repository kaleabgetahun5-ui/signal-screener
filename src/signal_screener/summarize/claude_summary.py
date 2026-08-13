"""Biotech signal summarization via Claude — the exact prompt from the
project brief (section 5), with a JSON response format appended so the
confidence flag can be validated programmatically.

Guardrail (project brief, section 6): the confidence flag must be exactly
one of ALLOWED_CONFIDENCE_FLAGS. This is enforced here, not left to trust —
a response with any other value raises rather than silently passing through
a value the rest of the app can't filter/sort on.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import anthropic

from signal_screener.config import ALLOWED_CONFIDENCE_FLAGS, ANTHROPIC_API_KEY, CLAUDE_MODEL

PROMPT_TEMPLATE = """You are helping a physician-run investment research tool summarize
clinical significance for a general audience.

Given this data:
- Drug: {drug_name}
- Company: {company_name} ({ticker})
- Designation: {designation_type} granted {date_granted}
- Indication: {indication}
- Trial phase: {phase}, Status: {status}
- Mechanism (if known): {mechanism}

Write:
1. A 2-sentence plain-English explanation of what this drug does
   and why the designation matters clinically (not just "it's promising")
2. One sentence on how differentiated this is vs. existing treatments
   for the same condition, if known
3. A confidence flag: "High signal" / "Moderate signal" / "Early stage"
   based on trial phase and designation strength alone —
   NOT a buy/sell recommendation

Do not speculate about stock price movement. Stick to clinical facts.

Respond with ONLY a JSON object, no other text, in this exact shape:
{{"explanation": "<item 1>", "differentiation": "<item 2>", "confidence_flag": "<item 3, exactly one of High signal / Moderate signal / Early stage>"}}
"""


@dataclass
class BiotechSummary:
    explanation: str
    differentiation: str
    confidence_flag: str
    generated_at: str

    @property
    def full_text(self) -> str:
        return f"{self.explanation} {self.differentiation}"


def summarize_designation(
    *,
    drug_name: str,
    company_name: str,
    ticker: str,
    designation_type: str,
    date_granted: str,
    indication: str,
    phase: str | None,
    status: str | None,
    mechanism: str | None = None,
) -> BiotechSummary:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (see .env.example)")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = PROMPT_TEMPLATE.format(
        drug_name=drug_name,
        company_name=company_name,
        ticker=ticker,
        designation_type=designation_type,
        date_granted=date_granted,
        indication=indication,
        phase=phase or "unknown",
        status=status or "unknown",
        mechanism=mechanism or "unknown",
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = response.content[0].text.strip()
    raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip())

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude did not return valid JSON: {raw_text!r}") from exc

    flag = parsed.get("confidence_flag")
    if flag not in ALLOWED_CONFIDENCE_FLAGS:
        raise ValueError(
            f"Claude returned an invalid confidence flag {flag!r}; "
            f"must be exactly one of {ALLOWED_CONFIDENCE_FLAGS}"
        )

    return BiotechSummary(
        explanation=parsed["explanation"],
        differentiation=parsed["differentiation"],
        confidence_flag=flag,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
