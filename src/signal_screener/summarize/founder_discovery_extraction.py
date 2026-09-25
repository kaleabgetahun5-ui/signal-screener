"""Founder-*detection* via Claude — the S&P 500 discovery feature's
counterpart to summarize/founder_extraction.py.

The two prompts have different jobs and that's deliberate, not an
oversight: founder_extraction.py's prompt is handed a filing excerpt
already centered on a *known* founder's name (Tier 1/Tier 2's hand-curated
candidate lists supply that name) and classifies their tier + the
company's network effect. This module doesn't get a name up front —
finding out whether anyone in the filing is identified as a founder in an
active leadership role, and who, is the detection task itself. Everything
else about the guardrail is identical: never infer or guess, answer only
from what this specific excerpt states, say so explicitly when it doesn't.

No network-effect classification here — that's deliberately deferred to
promotion (founder_discovery_pipeline.py's promote_approved(), which reuses
founder_extraction.py's existing, tested prompt once a human has approved
the candidate). Running the more expensive full extraction against ~500
S&P 500 companies just to build a review list would mean paying for (and
asking Claude to answer) the network-effect question for hundreds of
companies nobody has decided are even founder-led candidates yet.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import anthropic

from signal_screener.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

PROMPT_TEMPLATE = """Given this excerpt from {company_name}'s SEC filing, determine whether a
named individual is identified in this excerpt BOTH as a founder (or
co-founder) of {company_name} SPECIFICALLY AND as currently holding an
active leadership role of Chief Executive Officer, Chairman, or Executive
Chairman AT {company_name}.

Rules — do not guess or infer beyond what this excerpt explicitly states:
- If no named individual is clearly identified as both a founder/co-founder
  of {company_name} itself AND currently CEO/Chairman/Executive Chairman OF
  {company_name} in this excerpt, respond founder_detected: false. A
  mention of "the founder" without a name, or a founder mentioned only in a
  past/historical sense ("founded the company in 1998" with no statement of
  their current role), does not qualify — return false rather than
  assuming they're still active.
- Proxy statements and annual reports routinely include OTHER people's
  unrelated career history — e.g. an independent director's own bio listing
  companies THEY founded elsewhere ("Career Highlights: XYZ Ventures —
  Founder and CEO (2015-present)"), or a board skills-matrix table where
  "Founder / CEO" is a column label summarizing a director's most senior
  role at some OTHER, unnamed company. These are NOT about {company_name}
  and must NOT be extracted, even though the words "founder" and the
  company's own name may appear nearby on the same page. Only a founder
  claim that is explicitly and unambiguously about {company_name} itself
  counts.
- founder_name must be the person's name exactly as it appears in the excerpt.
- current_title must be their title exactly as stated in the excerpt (e.g.
  "Chief Executive Officer", "Executive Chairman") — not a paraphrase.
- ownership_pct_numeric must be a plain number (e.g. 12.5) ONLY if an
  ownership percentage for this specific named person is explicitly stated
  in the excerpt. Otherwise null — never estimate.
- supporting_quote (only when founder_detected is true) must be a short
  verbatim quote (a contiguous span, copied exactly, no paraphrasing) from
  this excerpt that by itself ties this named person to being founder
  AND current CEO/Chairman/Executive Chairman OF {company_name}
  specifically — not just a quote mentioning "founder" in isolation.

Source text:
{report_excerpt}

Respond with ONLY a JSON object, no other text, in this exact shape:
{{"founder_detected": <true or false>, "founder_name": "<name as stated, or null>", "current_title": "<title as stated, or null>", "ownership_pct_numeric": <number or null>, "ownership_stake": "<ownership text as stated, or 'not disclosed in this excerpt'>", "supporting_quote": "<verbatim quote from the excerpt, or null>", "reasoning": "<one sentence citing what in the excerpt supports this answer>"}}
"""


@dataclass
class FounderDetection:
    founder_detected: bool
    founder_name: str | None
    current_title: str | None
    ownership_pct_numeric: float | None
    ownership_stake: str
    supporting_quote: str | None
    reasoning: str
    generated_at: str


def _normalize_for_quote_check(text: str) -> str:
    """Collapses whitespace so a quote check isn't defeated by the
    line-wrap/multi-space normalization already applied when the filing
    text was extracted (filings/sec_edgar.py's fetch_filing_text already
    collapses runs of whitespace to single spaces, but Claude's returned
    quote may still differ in incidental spacing around punctuation)."""
    return re.sub(r"\s+", " ", text).strip()


def detect_founder_leadership(*, company_name: str, report_excerpt: str) -> FounderDetection:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (see .env.example)")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = PROMPT_TEMPLATE.format(company_name=company_name, report_excerpt=report_excerpt)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        # Pinned to 0 for determinism: this call is a binary detection gate
        # (founder_detected true/false) that decides whether a company ever
        # becomes reviewable, not a generative task where variety matters.
        # Left unpinned (API default), the same excerpt was observed to
        # flip true/false across identical re-runs (confirmed live on
        # AppLovin/APP) -- that variance is invisible for a "false" result
        # specifically, since a not-detected company is silently skipped
        # with no stored evidence, unlike a verified match (see run()'s
        # no_founder_detected branch). Pinning temperature doesn't
        # eliminate model error, but it removes sampling noise as a
        # separate, undetectable source of missed candidates.
        #
        # Passed via extra_body, not the typed `temperature=` kwarg: this
        # environment's installed anthropic SDK build doesn't expose
        # `temperature` as a first-class parameter (confirmed live --
        # `messages.create()` raised TypeError for it), unlike the
        # standard public SDK this project's pyproject.toml declares
        # (anthropic>=0.40). extra_body merges straight into the raw JSON
        # request body regardless of what the SDK's typed wrapper exposes,
        # so this reaches the API the same way either form would.
        extra_body={"temperature": 0},
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = response.content[0].text.strip()
    raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip())

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude did not return valid JSON: {raw_text!r}") from exc

    detected = bool(parsed.get("founder_detected"))
    # Never-infer guardrail, enforced in code too, not just in the prompt:
    # a "detected" answer with no name or no title isn't usable by anything
    # downstream (the review list, promotion) and would otherwise slip
    # through as a candidate nobody can actually evaluate.
    if detected and not (parsed.get("founder_name") and parsed.get("current_title")):
        detected = False

    # Quote-grounding check: the model must point at real text in the
    # excerpt it was actually given, not text it composed itself. This is
    # the concrete fix for a real false-positive class found live against
    # the S&P 500 (AES Corp, Allegion): the model attributing a founder
    # claim it read in a director's unrelated outside-company bio, or a
    # board skills-matrix cell, to the company being asked about. Requiring
    # a verbatim quote that must actually exist in the source excerpt
    # doesn't fully solve that on its own (the quote could still be a real
    # sentence about the wrong company), but it does rule out the case
    # where the model can't even produce one — and combined with the
    # prompt's explicit negative examples above, forces the model to
    # ground its answer in an actual sentence rather than a same-page
    # association.
    supporting_quote = parsed.get("supporting_quote")
    if detected and (
        not supporting_quote
        or _normalize_for_quote_check(supporting_quote) not in _normalize_for_quote_check(report_excerpt)
    ):
        detected = False

    return FounderDetection(
        founder_detected=detected,
        founder_name=parsed.get("founder_name") if detected else None,
        current_title=parsed.get("current_title") if detected else None,
        ownership_pct_numeric=parsed.get("ownership_pct_numeric") if detected else None,
        ownership_stake=parsed.get("ownership_stake") or "not disclosed in this excerpt",
        supporting_quote=supporting_quote if detected else None,
        reasoning=parsed.get("reasoning", ""),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
