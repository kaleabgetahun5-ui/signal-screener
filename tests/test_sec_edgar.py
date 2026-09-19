from signal_screener.filings.sec_edgar import extract_founder_mention_excerpts, extract_leadership_excerpt


def test_extract_leadership_excerpt_finds_role_and_ownership():
    text = (
        "Some unrelated filler text about segment reporting and revenue recognition. "
        "Jane Founder is our founder and has served as Chief Executive Officer and "
        "Chairman of the Board since our inception in 2010. "
        "More filler about accounting policies. "
        "BENEFICIAL OWNERSHIP OF OUR COMMON STOCK Name Percentage Jane Founder 12.5% "
        "Other Holder 3.1%"
    )
    excerpt = extract_leadership_excerpt(text, "Jane Founder")
    assert "Chief Executive Officer" in excerpt
    assert "12.5%" in excerpt


def test_extract_leadership_excerpt_falls_back_when_nothing_matches():
    text = "This document never mentions any names or ownership tables at all."
    excerpt = extract_leadership_excerpt(text, "Nobody Here", max_chars=50)
    assert excerpt == text[:50]


def test_extract_founder_mention_excerpts_returns_none_when_word_never_appears():
    """The discovery pipeline's cheap prefilter: a filing that never says
    "founder" at all must be skipped before any Claude call, not handed
    over as an empty/fabricated excerpt."""
    text = "This document is entirely about segment reporting and revenue recognition."
    assert extract_founder_mention_excerpts(text) is None


def test_extract_founder_mention_excerpts_finds_founder_and_cofounder():
    text = (
        "Filler text before. Jane Founder, our founder, has served as Chief "
        "Executive Officer since inception. "
        "More filler in between the two mentions to keep windows separate for this test. "
        "John Cofounder co-founded the company in 2005 and serves as our Chairman."
    )
    excerpt = extract_founder_mention_excerpts(text)
    assert excerpt is not None
    assert "Jane Founder" in excerpt
    assert "John Cofounder" in excerpt


def test_extract_founder_mention_excerpts_respects_max_chars():
    text = "founder " * 2000
    excerpt = extract_founder_mention_excerpts(text, max_chars=500)
    assert excerpt is not None
    assert len(excerpt) <= 500
