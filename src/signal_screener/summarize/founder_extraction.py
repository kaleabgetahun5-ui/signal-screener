"""Founder-led/network-effect extraction via Claude — the exact prompt from
the project brief (section 5), with a JSON response format appended so the
tier classification can be validated programmatically, the same way
claude_summary.py handles the biotech prompt.

Guardrail (project brief, section 4): both the title and ownership-
percentage checks must come from actual filings, never be inferred or
guessed — that's why this module only classifies from a real filing
excerpt (filings/sec_edgar.py) and requires Claude to say so explicitly
when the excerpt doesn't state something, rather than fill the gap.

Item 4 of the prompt (network effect) is explicitly the exception to that:
the brief scopes it to general knowledge of the company's business model,
not the excerpt — a filing's leadership/ownership section never describes
that. (This was a real bug in an earlier build here: scoping item 4 to the
excerpt too made it silently return "None identified" for genuinely
network-effect businesses like Sea Limited and Grab. The brief was since
corrected to call this out explicitly, and the prompt below matches that
correction verbatim.)

One remaining gap between the brief's two sections: section 4's
classification rule gates "Founder-Chair" on the transition having
happened within the last 24 months, but section 5's extraction prompt
doesn't ask for that recency check at all — it only conditions the tier on
current title + ownership. Rather than editing the prompt's substance, this
module asks for a `transition_date` field in the structured response
(a direct structuring of what the prompt already asks Claude to address —
"say so explicitly" if the date isn't in the excerpt) and applies the
24-month rule as a separate check in founder_pipeline.py once a date is
available, downgrading a stale "Founder-Chair" to "Founder-departed" per
section 4. No date stated means no downgrade — the rule doesn't get
applied on a guess.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import anthropic

from signal_screener.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

ALLOWED_FOUNDER_TIERS = ("Founder-CEO", "Founder-Chair", "Founder-departed")

PROMPT_TEMPLATE = """Given this excerpt from {company_name}'s annual report or 20-F filing, extract:
1. Is the original founder still in an active leadership role (CEO, Chair, or
   equivalent)? State their current title.
2. Approximate founder ownership stake, if disclosed.
3. Based on #1 and #2, classify into exactly one tier: "Founder-CEO"
   (founder is current CEO), "Founder-Chair" (founder stepped back from
   CEO but holds Chairman/Executive Chairman AND >5% ownership), or
   "Founder-departed" (neither of the above applies). If the transition
   date isn't in this excerpt, say so explicitly rather than guessing
   how recent it was.
4. One sentence describing the company's core network effect, if one exists
   (e.g., more users → more value for each user), or "None identified" if
   the business model doesn't have one. Unlike items 1-3, this question is
   about the company's general business model, not something the leadership/
   ownership excerpt itself will describe — answer it from general knowledge
   of the company, not from the excerpt. (This distinction matters: an
   earlier build of this prompt scoped item 4 to excerpt-only too, and it
   silently returned "None identified" for genuinely network-effect
   businesses like Sea Limited and Grab, simply because leadership/ownership
   sections never discuss business model.)

Source text:
{report_excerpt}

Respond with ONLY a JSON object, no other text, in this exact shape:
{{"leadership_status": "<item 1, including current title or 'no active leadership role'>", "ownership_stake": "<item 2 as stated in the excerpt, or 'not disclosed in this excerpt'>", "ownership_pct_numeric": <item 2 as a plain number like 7.0, or null if not disclosed>, "founder_tier": "<item 3, exactly one of Founder-CEO / Founder-Chair / Founder-departed>", "transition_date": "<the date the founder stepped back from CEO, as YYYY-MM-DD if a specific date is stated in the excerpt, or null if not stated>", "network_effect": "<item 4>"}}
"""


@dataclass
class FounderExtraction:
    leadership_status: str
    ownership_stake: str
    ownership_pct_numeric: float | None
    founder_tier: str
    transition_date: str | None
    network_effect: str
    generated_at: str


def extract_founder_status(*, company_name: str, report_excerpt: str) -> FounderExtraction:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (see .env.example)")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = PROMPT_TEMPLATE.format(company_name=company_name, report_excerpt=report_excerpt)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = response.content[0].text.strip()
    raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip())

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude did not return valid JSON: {raw_text!r}") from exc

    tier = parsed.get("founder_tier")
    if tier not in ALLOWED_FOUNDER_TIERS:
        raise ValueError(
            f"Claude returned an invalid founder_tier {tier!r}; "
            f"must be exactly one of {ALLOWED_FOUNDER_TIERS}"
        )

    return FounderExtraction(
        leadership_status=parsed["leadership_status"],
        ownership_stake=parsed["ownership_stake"],
        ownership_pct_numeric=parsed.get("ownership_pct_numeric"),
        founder_tier=tier,
        transition_date=parsed.get("transition_date"),
        network_effect=parsed["network_effect"],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
