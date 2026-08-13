from signal_screener.filings.sec_edgar import extract_leadership_excerpt


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
