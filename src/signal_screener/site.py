"""Generates a static public HTML page from the current database, in the
same visual style as the earlier hand-built demos (signal-screener-v1.html,
nefl-screener-v1.html) — same fonts, colors, card layout, flag pills, and
verify-link rows, but driven by real pipeline data instead of hand-written
examples.

Two things the demos had that this page deliberately omits, because the
data doesn't exist yet:
  - The "$100 at IPO vs. S&P 500" backtest bars (nefl-screener-v1.html) —
    needs the `price_history` table, which isn't built (MVP roadmap step 6
    is the track-record checker; a backtest view isn't scheduled yet).
  - The "why this is worth a closer look" growth/analyst/bull-bear block
    (brief section 7) — needs real growth data, analyst targets, and news,
    none of which this pipeline pulls. Fabricating that content would
    violate the project's own guardrail against inventing facts not
    present in the input, so it's left out rather than faked.

What IS real and shown: for biotech entries, the company name as originally
submitted (not the resolved match, which can be wrong — see db.py's
raw_company_name note), the confidence flag, the Claude clinical summary,
and a verify link to the real ClinicalTrials.gov record. For founder-led
entries, the founder tier, the real ownership percentage and role sentence
pulled from the actual SEC filing, and a verify link straight to that
filing on sec.gov.

Delisted/acquired biotech entries (companies.delisted_or_acquired) render
in a dedicated "Archive" section rather than inline in "Biotech signals" —
same card markup either way, just moved out of the section meant to
answer "what's currently worth a look" once the underlying company is
confirmed no longer an active, tradable listing. The designation record
itself is real and kept, not dropped, since the clinical fact (the
Breakthrough Therapy/PRIME designation) doesn't stop being true just
because the company's listing status changed.
"""

import html
from datetime import date, datetime

from signal_screener import db

CONFIDENCE_CLASS = {
    "High signal": "high",
    "Moderate signal": "moderate",
    "Early stage": "early",
}
TIER_CLASS = {
    "Founder-CEO": "high",
    "Founder-Chair": "moderate",
    "Founder-departed": "early",
}
TIER_LABEL = {
    "Founder-CEO": "Founder-CEO tier",
    "Founder-Chair": "Founder-Chair tier",
    "Founder-departed": "Founder-departed",
}

CSS = """
  @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

  :root{
    --bg:#EDF1F0; --card:#FFFFFF; --ink:#16233D; --ink-soft:#4A5568; --line:#D8DEDC;
    --high:#1F7A5C; --high-bg:#E5F3EC;
    --moderate:#B8862B; --moderate-bg:#FBF1DE;
    --early:#5B6B7A; --early-bg:#E9EDF0;
    --verify:#9C6B1F;
    --delisted:#5B3A8E; --delisted-bg:#EEE7F7;
    --arbitrary:#1C5D8C; --arbitrary-bg:#E3EEF7;
  }
  *{box-sizing:border-box;}
  body{margin:0; background:var(--bg); color:var(--ink); font-family:'IBM Plex Sans', sans-serif; padding:40px 20px 80px;}
  .wrap{max-width:780px; margin:0 auto;}
  header{margin-bottom:36px;}
  .eyebrow{font-family:'IBM Plex Mono', monospace; font-size:12px; letter-spacing:0.08em; text-transform:uppercase; color:var(--ink-soft); margin-bottom:10px;}
  h1{font-family:'Source Serif 4', serif; font-weight:700; font-size:34px; margin:0 0 10px; letter-spacing:-0.01em;}
  h2.section-title{font-family:'Source Serif 4', serif; font-weight:600; font-size:22px; margin:44px 0 18px;}
  .sub{color:var(--ink-soft); font-size:15px; line-height:1.55; max-width:62ch;}

  .banner{background:var(--card); border:1px solid var(--line); border-left:4px solid var(--verify); border-radius:6px; padding:16px 18px; margin:24px 0 12px; font-size:14px; line-height:1.6; color:var(--ink-soft);}
  .banner b{color:var(--ink);}

  .card{background:var(--card); border:1px solid var(--line); border-radius:8px; margin-bottom:20px; overflow:hidden;}
  .card.with-tab{display:flex;}
  .tab{width:6px; flex-shrink:0;}
  .tab.high{background:var(--high);} .tab.moderate{background:var(--moderate);} .tab.early{background:var(--early);} .tab.delisted{background:var(--delisted);}
  .body{padding:20px 22px; flex:1; min-width:0;}
  .card-head{padding:20px 22px 0;}

  .top-row{display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap; margin-bottom:6px;}
  .drug-name, .company-name{font-family:'Source Serif 4', serif; font-weight:600; font-size:19px;}
  .ticker{font-family:'IBM Plex Mono', monospace; font-size:12px; background:var(--bg); border:1px solid var(--line); border-radius:4px; padding:3px 8px; color:var(--ink-soft); white-space:nowrap;}
  .ticker.unverified{border-style:dashed; color:var(--verify);}
  .ticker.delisted{border-style:solid; border-color:var(--delisted); color:var(--delisted); background:var(--delisted-bg);}

  .meta{font-size:13px; color:var(--ink-soft); margin-bottom:14px; line-height:1.6;}
  .meta strong{color:var(--ink); font-weight:500;}
  .meta.valuation{font-family:'IBM Plex Mono', monospace; font-size:12px;}
  .valuation-as-of{font-style:italic;}

  .flag{display:inline-block; font-family:'IBM Plex Mono', monospace; font-size:11px; letter-spacing:0.03em; text-transform:uppercase; padding:3px 9px; border-radius:20px; margin-bottom:12px;}
  .flag.high{background:var(--high-bg); color:var(--high);}
  .flag.moderate{background:var(--moderate-bg); color:var(--moderate);}
  .flag.early{background:var(--early-bg); color:var(--early);}
  .flag.delisted{background:var(--delisted-bg); color:var(--delisted);}
  .flag.arbitrary{background:var(--arbitrary-bg); color:var(--arbitrary);}

  .card.arbitrary{border-style:dashed; border-color:var(--arbitrary);}
  .card.arbitrary .ticker{border-color:var(--arbitrary); color:var(--arbitrary);}

  .read{font-size:14.5px; line-height:1.65; color:var(--ink); margin-bottom:16px;}

  .verify-row{border-top:1px dashed var(--line); padding-top:12px; margin:0 22px 20px; display:flex; flex-wrap:wrap; gap:8px; align-items:center;}
  .card.with-tab .verify-row{margin:0; padding:12px 22px; border-top:1px dashed var(--line);}
  .verify-label{font-family:'IBM Plex Mono', monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.05em; color:var(--ink-soft); margin-right:2px;}
  .verify-row a{font-size:12.5px; color:var(--verify); text-decoration:none; border-bottom:1px solid transparent; padding:2px 0;}
  .verify-row a:hover, .verify-row a:focus-visible{border-bottom-color:var(--verify); outline:none;}
  .verify-row a:focus-visible{outline:2px solid var(--verify); outline-offset:2px; border-radius:2px;}
  .verify-note{font-size:12.5px; color:var(--verify); font-style:italic;}
  .delisted-note{font-size:13px; color:var(--delisted); line-height:1.5; margin:0 22px 14px; padding:10px 12px; background:var(--delisted-bg); border-radius:6px;}
  .card.with-tab .delisted-note{margin:0 22px 14px;}

  .notes{border-top:1px dashed var(--line); padding-top:12px; margin:0 22px 14px; font-size:13.5px; color:var(--ink);}
  .card.with-tab .notes{margin:0 22px 14px;}
  .notes-label{font-family:'IBM Plex Mono', monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.05em; color:var(--ink-soft); display:block; margin-bottom:6px;}
  .notes ul{margin:0; padding-left:18px;}
  .notes li{margin-bottom:4px; line-height:1.5;}
  .note-date{font-family:'IBM Plex Mono', monospace; font-size:11.5px; color:var(--ink-soft);}

  .new-since{background:var(--card); border:1px solid var(--line); border-radius:8px; padding:4px 22px 8px; margin-bottom:36px;}
  .subsection-title{font-family:'Source Serif 4', serif; font-weight:600; font-size:16px; color:var(--ink-soft); margin:20px 0 12px;}
  .new-since .card, .new-since .card.with-tab{margin-left:-1px; margin-right:-1px;}

  footer{margin-top:40px; font-size:12.5px; color:var(--ink-soft); line-height:1.75; border-top:1px solid var(--line); padding-top:18px;}
"""


def _flag_pill(label: str, css_class: str) -> str:
    return f'<div class="flag {css_class}">{html.escape(label)}</div>'


def _verify_note() -> str:
    return '<span class="verify-note">ticker not independently verified</span>'


def _delisted_note(reason: str | None) -> str:
    text = reason or "This company appears to no longer be an active, tradable listing."
    return f'<div class="delisted-note"><strong>Delisted/acquired:</strong> {html.escape(text)}</div>'


def _notes_html(notes) -> str:
    """Roadmap step 5 / brief section 8: personal notes per entry, written
    via `signal-screener add-note` — this tool stays CLI-only for writing
    (brief section 9: no accounts, no backend), the site is read-only."""
    if not notes:
        return ""
    items = "".join(
        f'<li><span class="note-date">{html.escape(n["date_written"])}</span> — {html.escape(n["note_text"])}</li>'
        for n in notes
    )
    return f'<div class="notes"><span class="notes-label">Your notes:</span><ul>{items}</ul></div>'


def _format_ts(iso_ts: str) -> str:
    """"2026-08-13T14:22:01.123456+00:00" -> "2026-08-13 14:22 UTC" — used
    only for the human-readable "since your last visit" timestamp; the raw
    ISO string is what's actually compared against first_seen_at."""
    try:
        return datetime.fromisoformat(iso_ts).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return iso_ts


def _render_biotech_card(row, notes=()) -> str:
    verified = bool(row["ticker_verified"])
    delisted = bool(row["delisted_or_acquired"])
    ticker_class = "ticker delisted" if delisted else ("ticker" if verified else "ticker unverified")
    confidence = row["summary_confidence_flag"] or "Early stage"
    # Delisted/acquired status is about the company's listing, not the
    # drug's clinical designation — the confidence flag/tab color stays
    # what it was; delisted status gets its own distinct pill + note below,
    # not a repurposed one.
    tab_class = CONFIDENCE_CLASS.get(confidence, "early")

    company = html.escape(row["raw_company_name"])
    drug = html.escape(row["drug_name"])
    ticker = html.escape(row["ticker"])
    designation_type = html.escape(row["type"])
    source = html.escape(row["source"])
    indication = html.escape(row["indication"] or "")
    read_text = html.escape(row["summary_text"] or "Summary not yet generated.")

    verify_links = []
    if row["trial_id"]:
        nct = html.escape(row["trial_id"])
        verify_links.append(
            f'<a href="https://clinicaltrials.gov/study/{nct}" target="_blank" '
            f'rel="noopener">ClinicalTrials.gov ({nct})</a>'
        )
    date_granted_source = row["date_granted_source"]
    if date_granted_source and date_granted_source.startswith("http"):
        verify_links.append(
            f'<a href="{html.escape(date_granted_source)}" target="_blank" '
            f'rel="noopener">Designation date source</a>'
        )
    if verified:
        verify_links.append(
            f'<a href="https://finance.yahoo.com/quote/{ticker}" target="_blank" '
            f'rel="noopener">Current price</a>'
        )
    verify_html = "".join(verify_links) if verify_links else ""
    if delisted:
        verify_html += '<span class="verify-note">no current-price link — see delisted/acquired note above</span>'
    elif not verified:
        verify_html += _verify_note()

    delisted_html = _delisted_note(row["ticker_verification_reason"]) if delisted else ""
    notes_html = _notes_html(notes)

    return f"""
  <div class="card with-tab">
    <div class="tab {tab_class}"></div>
    <div class="body">
      <div class="top-row">
        <div class="drug-name">{drug} ({company})</div>
        <div class="{ticker_class}">{ticker}</div>
      </div>
      <div class="meta"><strong>{source} {designation_type}</strong> · granted {row['date_granted']} · {indication}</div>
      {_flag_pill(confidence, tab_class)}
      {_flag_pill("Delisted/Acquired", "delisted") if delisted else ""}
      <div class="read">{read_text}</div>
      {delisted_html}
      {notes_html}
      <div class="verify-row">
        <span class="verify-label">Verify:</span>
        {verify_html}
      </div>
    </div>
  </div>"""


def _format_market_cap(value: float | None, currency: str | None) -> str | None:
    if value is None:
        return None
    abs_value = abs(value)
    if abs_value >= 1e12:
        magnitude = f"{value / 1e12:.1f}T"
    elif abs_value >= 1e9:
        magnitude = f"{value / 1e9:.1f}B"
    elif abs_value >= 1e6:
        magnitude = f"{value / 1e6:.1f}M"
    else:
        magnitude = f"{value:,.0f}"
    return f"{magnitude} {currency}".strip() if currency else magnitude


def _valuation_html(row) -> str:
    """Roadmap extra: market cap/P/E/52-week range/beta/dividend yield,
    pulled from valuation.py (Yahoo's quoteSummary endpoint — a different
    source from the chart/search endpoints the rest of this project
    already used, since neither of those carries these fields at all).
    Never fabricated: any field valuation.fetch_valuation_metrics()
    couldn't get comes through as None here and is either shown as "not
    available" (market cap, P/E — always meaningful for an active
    listing) or omitted entirely (beta, dividend yield — not every
    company has one, and Yahoo itself distinguishes "zero" from "none" by
    returning nothing at all for the latter, see valuation.py's _raw()).
    Returns "" (no block at all) if every field is missing — e.g. a
    company whose valuation fetch failed outright, or a delisted/acquired
    one that never had this fetched in the first place."""
    market_cap = _format_market_cap(row["market_cap"], row["currency"])
    trailing_pe = row["trailing_pe"]
    forward_pe = row["forward_pe"]
    beta = row["beta"]
    dividend_yield = row["dividend_yield_pct"]
    low = row["fifty_two_week_low"]
    high = row["fifty_two_week_high"]

    if all(v is None for v in (market_cap, trailing_pe, forward_pe, beta, dividend_yield, low, high)):
        return ""

    parts = [f"<strong>Market cap:</strong> {html.escape(market_cap) if market_cap else 'not available'}"]

    pe_text = f"{trailing_pe:.1f}" if trailing_pe is not None else "not available"
    if forward_pe is not None:
        pe_text += f" (fwd {forward_pe:.1f})"
    parts.append(f"<strong>P/E:</strong> {html.escape(pe_text)}")

    if low is not None and high is not None:
        currency = html.escape(row["currency"] or "")
        parts.append(f"<strong>52-wk range:</strong> {low:,.2f}–{high:,.2f} {currency}".strip())
    if beta is not None:
        parts.append(f"<strong>Beta:</strong> {beta:.2f}")
    if dividend_yield is not None:
        parts.append(f"<strong>Dividend yield:</strong> {dividend_yield:.2f}%")

    as_of = row["valuation_as_of_date"]
    as_of_html = (
        f' <span class="valuation-as-of">(as of {html.escape(as_of)})</span>' if as_of else ""
    )
    return f'<div class="meta valuation">{" · ".join(parts)}{as_of_html}</div>'


def _render_founder_card(row, ownership, notes=()) -> str:
    verified = bool(row["ticker_verified"])
    delisted = bool(row["delisted_or_acquired"])
    ticker_class = "ticker delisted" if delisted else ("ticker" if verified else "ticker unverified")
    tier = row["founder_tier"]
    tier_class = "delisted" if delisted else TIER_CLASS.get(tier, "early")
    tier_label = "Delisted/Acquired" if delisted else TIER_LABEL.get(tier, tier)

    name = html.escape(row["company_name"])
    ticker = html.escape(row["ticker"])
    exchange = html.escape(row["exchange"] or "")
    country = html.escape(row["country"] or "unknown")
    network_effect_strength = row["network_effect_strength"]
    network_effect = html.escape(row["network_effect"] or "not identified in the source excerpt")
    if network_effect_strength:
        network_effect = f"[{html.escape(network_effect_strength)}] {network_effect}"

    if delisted:
        # founder_pipeline.py deliberately skips the filing/ownership fetch
        # for a confirmed delisted/acquired company (nothing left to
        # classify) — the delisted note below carries the real information
        # here instead of a "no ownership on file" line that would read as
        # a data gap rather than a known status.
        read_text = "This company is no longer an active, tradable listing — see note below."
    elif ownership:
        pct = (
            f"{ownership['ownership_pct']:.1f}%"
            if ownership["ownership_pct"] is not None
            else "not disclosed"
        )
        read_text = html.escape(ownership["role"])
        read_text += f" Ownership stake: {pct} (as of {ownership['as_of_date']})."
    else:
        read_text = "No ownership detail on file yet."

    verify_links = []
    if row["founder_tier_source"]:
        form, _, url = row["founder_tier_source"].partition(":")
        url = url or row["founder_tier_source"]
        if url.startswith("http"):
            verify_links.append(
                f'<a href="{html.escape(url)}" target="_blank" rel="noopener">'
                f"SEC {html.escape(form)} filing</a>"
            )
    if verified:
        verify_links.append(
            f'<a href="https://finance.yahoo.com/quote/{ticker}" target="_blank" '
            f'rel="noopener">Current price</a>'
        )
    verify_html = "".join(verify_links) if verify_links else ""
    if delisted:
        verify_html += '<span class="verify-note">no current-price link — see delisted/acquired note above</span>'
    elif not verified:
        verify_html += _verify_note()

    delisted_html = _delisted_note(row["ticker_verification_reason"]) if delisted else ""
    notes_html = _notes_html(notes)
    valuation_html = _valuation_html(row)

    ticker_display = f"{exchange}: {ticker}" if exchange else ticker

    return f"""
  <div class="card">
    <div class="card-head">
      <div class="top-row">
        <div class="company-name">{name}</div>
        <div class="{ticker_class}">{ticker_display}</div>
      </div>
      {_flag_pill(tier_label, tier_class)}
      <div class="meta"><strong>HQ:</strong> {country} · <strong>Founder:</strong> {html.escape(row['founder_name'] or 'unknown')} · <strong>Network effect:</strong> {network_effect}</div>
      {valuation_html}
      <div class="read">{read_text}</div>
      {delisted_html}
      {notes_html}
    </div>
    <div class="verify-row">
      <span class="verify-label">Verify:</span>
      {verify_html}
    </div>
  </div>"""


def _render_arbitrary_watchlist_card(row) -> str:
    """A self-added ticker (db.watchlist, entry_kind='arbitrary') has no
    row in companies — it was never run through the founder-led/biotech
    screening pipeline at all, only independently verified to exist as a
    real, currently listed security (matching/ticker_verify.py's
    resolve_arbitrary_ticker) at the moment it was added. Deliberately
    styled and worded to look different from a screened card (dashed
    blue border, "Self-added" flag instead of a tier/confidence pill, no
    founder/network-effect claims) — this project's guardrail against
    ever presenting unscreened data as if it were screened."""
    ticker = html.escape(row["entry_id"])
    name = html.escape(row["company_name"] or ticker)
    source = html.escape(row["verification_source"] or "unknown source")
    verified_date = html.escape(row["verification_date"] or "unknown date")
    reason = html.escape(row["verification_reason"] or "")

    return f"""
  <div class="card arbitrary">
    <div class="card-head">
      <div class="top-row">
        <div class="company-name">{name}</div>
        <div class="ticker">{ticker}</div>
      </div>
      {_flag_pill("Self-added — not screened", "arbitrary")}
      <div class="meta"><strong>Added by you:</strong> {html.escape(row['added_at'])} · <strong>Existence verified via:</strong> {source} ({verified_date})</div>
      <div class="read">{reason}</div>
    </div>
    <div class="verify-row">
      <span class="verify-label">Verify:</span>
      <a href="https://finance.yahoo.com/quote/{ticker}" target="_blank" rel="noopener">Current price</a>
    </div>
  </div>"""


def _is_new(row, previous_generated_at: str | None) -> bool:
    """Roadmap step 5's diff mechanism: a row is "new since last visit" iff
    it was first seen after the previous generate-site run. first_seen_at
    is NULL for rows that predate that column (see db.py) and
    previous_generated_at is None on the very first-ever run — both cases
    correctly fall out of this as "not new" rather than needing a
    special-cased comparison against NULL/None."""
    return bool(row["first_seen_at"]) and previous_generated_at is not None and row["first_seen_at"] > previous_generated_at


def build_site_html() -> str:
    db.init_db()
    with db.connect() as conn:
        # Read before this run's generation overwrites it — this is the
        # baseline the "New since last visit" section diffs against.
        previous_generated_at = db.get_last_generated_at(conn)
        watchlist_ids = db.get_watchlist_entry_ids(conn)
        arbitrary_watchlist_rows = db.get_arbitrary_watchlist_rows(conn)

        biotech_rows = conn.execute(
            """
            SELECT d.*, c.ticker_verified, c.delisted_or_acquired, c.ticker_verification_reason
            FROM designations d
            JOIN companies c ON c.ticker = d.ticker
            ORDER BY d.date_granted DESC, d.drug_name
            """
        ).fetchall()

        founder_rows = conn.execute(
            """
            SELECT * FROM companies
            WHERE listing_type IN ('ADR', 'primary')
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

        # Render each row's card exactly once — the "New since last visit"
        # section and the main section below it show the same card markup
        # for a given row (same style, same verify links, same notes),
        # never a simplified duplicate.
        biotech_cards = []
        for row in biotech_rows:
            notes = db.get_notes_for_entry(conn, row["designation_id"])
            biotech_cards.append((row, _render_biotech_card(row, notes)))

        founder_cards = []
        for row in founder_rows:
            ownership = conn.execute(
                "SELECT * FROM ownership WHERE ticker = ? "
                "ORDER BY as_of_date DESC, ownership_id DESC LIMIT 1",
                (row["ticker"],),
            ).fetchone()
            notes = db.get_notes_for_entry(conn, row["ticker"])
            founder_cards.append((row, _render_founder_card(row, ownership, notes)))

        generated_at = db.now_iso()
        db.set_last_generated_at(conn, generated_at)

    # Delisted/acquired biotech entries move to their own "Archive"
    # section below rather than rendering inline — the main section is
    # meant to answer "what's currently worth a look," and a delisted/
    # acquired listing (see _delisted_note) isn't that anymore even
    # though the underlying designation record is still real and worth
    # keeping. Same card markup either way (_render_biotech_card), just
    # partitioned by companies.delisted_or_acquired — never a simplified
    # or re-derived version of the card for the archive.
    active_biotech_cards = [
        (row, card_html) for row, card_html in biotech_cards if not row["delisted_or_acquired"]
    ]
    archived_biotech_cards = [
        (row, card_html) for row, card_html in biotech_cards if row["delisted_or_acquired"]
    ]

    biotech_html = (
        "".join(card_html for _, card_html in active_biotech_cards)
        if active_biotech_cards
        else '<p class="sub">No active biotech designations on file yet.</p>'
    )
    archive_html = (
        "".join(card_html for _, card_html in archived_biotech_cards)
        if archived_biotech_cards
        else '<p class="sub">Nothing archived yet — this fills in as designations '
        "get confirmed delisted/acquired.</p>"
    )
    founder_html = (
        "".join(card_html for _, card_html in founder_cards)
        if founder_cards
        else '<p class="sub">No founder-led companies on file yet.</p>'
    )

    new_biotech_html = "".join(
        card_html for row, card_html in biotech_cards if _is_new(row, previous_generated_at)
    )
    new_founder_html = "".join(
        card_html for row, card_html in founder_cards if _is_new(row, previous_generated_at)
    )

    watchlist_biotech_html = "".join(
        card_html for row, card_html in biotech_cards if row["designation_id"] in watchlist_ids
    )
    watchlist_founder_html = "".join(
        card_html for row, card_html in founder_cards if row["ticker"] in watchlist_ids
    )
    watchlist_arbitrary_html = "".join(
        _render_arbitrary_watchlist_card(row) for row in arbitrary_watchlist_rows
    )

    if previous_generated_at is None:
        new_since_body = (
            '<p class="sub">This is the first generated snapshot — nothing to compare '
            "against yet. The next run will show what's new since this one.</p>"
        )
    elif not new_biotech_html and not new_founder_html:
        new_since_body = (
            f'<p class="sub">Nothing new since your last visit '
            f"({html.escape(_format_ts(previous_generated_at))}).</p>"
        )
    else:
        # Pulled out of the f-string below rather than inlined with escaped
        # quotes: a backslash inside an f-string's {} expression part is a
        # SyntaxError before Python 3.12 (PEP 701 lifted that restriction),
        # and this project targets 3.11 (pyproject.toml, CI).
        nothing_new_here = '<p class="sub">Nothing new here.</p>'
        new_since_body = (
            f'<p class="sub">Since your last visit ({html.escape(_format_ts(previous_generated_at))}):</p>'
            f'<h3 class="subsection-title">New biotech signals</h3>'
            f'{new_biotech_html or nothing_new_here}'
            f'<h3 class="subsection-title">New founder-led companies</h3>'
            f'{new_founder_html or nothing_new_here}'
        )

    has_any_watchlist_content = (
        watchlist_biotech_html or watchlist_founder_html or watchlist_arbitrary_html
    )
    if not watchlist_ids and not arbitrary_watchlist_rows:
        watchlist_body = (
            '<p class="sub">Your watchlist is empty. Star an already-screened entry '
            "or add an outside ticker with <code>signal-screener watchlist-add "
            "&lt;entry_id&gt;</code> — a designation_id, a founder-led/biotech ticker, "
            "or any other ticker (verified against Yahoo/SEC before being accepted) "
            "— to see it here.</p>"
        )
    elif not has_any_watchlist_content:
        watchlist_body = (
            '<p class="sub">Nothing on your watchlist is currently in the pipeline '
            "(it may have since been removed).</p>"
        )
    else:
        watchlist_nothing_here = '<p class="sub">Nothing here.</p>'
        watchlist_body = (
            '<h3 class="subsection-title">Biotech signals</h3>'
            f"{watchlist_biotech_html or watchlist_nothing_here}"
            '<h3 class="subsection-title">Founder-led companies</h3>'
            f"{watchlist_founder_html or watchlist_nothing_here}"
        )
        if watchlist_arbitrary_html:
            watchlist_body += (
                '<h3 class="subsection-title">Self-added tickers — not screened by '
                "this pipeline</h3>"
                '<p class="sub">These were added directly by ticker, without going '
                "through the founder-led/biotech screening pipeline — only their "
                "existence as a real, listed security was verified, nothing else.</p>"
                f"{watchlist_arbitrary_html}"
            )

    generated = date.today().isoformat()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Signal Screener</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div class="eyebrow">Signal Screener · Live pipeline snapshot · {generated}</div>
    <h1>Biotech signals &amp; founder-led companies</h1>
    <div class="sub">FDA Breakthrough Therapy and EMA PRIME designations, plus a founder-led/network-effect stock screener, both pulled from real sources (SEC EDGAR, ClinicalTrials.gov, FDA/EMA) and summarized by Claude. Every card links to where the fact came from.</div>
  </header>

  <div class="banner">
    <b>How to validate this:</b> click "Verify" on each card — it goes straight to the source filing or trial record, not a paraphrase of one. Cards marked with a dashed, amber ticker failed independent verification (a second source didn't confirm the match) and are shown as-is rather than silently dropped or silently trusted. A solid purple ticker means something different: the match is very likely correct, but the company is confirmed no longer an active, tradable listing (acquired, delisted, gone private) — a real-world status change, not a matching failure. Nothing on this page is investment advice — confidence flags describe clinical/ownership facts, not buy or sell recommendations.
  </div>

  <h2 class="section-title">New since last visit</h2>
  <div class="new-since">
    {new_since_body}
  </div>

  <h2 class="section-title">★ Your watchlist</h2>
  <div class="new-since">
    {watchlist_body}
  </div>

  <h2 class="section-title">Biotech signals</h2>
  {biotech_html}

  <h2 class="section-title">Archive — delisted / acquired</h2>
  <div class="sub" style="margin-bottom:18px;">Biotech designations whose company is confirmed no longer an active, tradable listing (see the banner above) — moved out of the main section above so it stays focused on what's currently live, without dropping the underlying designation record.</div>
  {archive_html}

  <h2 class="section-title">Founder-led companies</h2>
  {founder_html}

  <footer>
    <b>Generated {generated}</b> from a live pipeline (not a live feed on this page — it's a static snapshot, rebuilt on demand). Ticker matching, verification, and classification methodology: <a href="https://github.com/kaleabgetahun5-ui/signal-screener" target="_blank" rel="noopener" style="color:var(--verify);">source on GitHub</a>. This omits the "why this is worth a closer look" growth/analyst/bull-bear section from earlier mockups — that needs a real growth-data and analyst-target source this pipeline doesn't pull yet, and this project doesn't fabricate that kind of content.
  </footer>

</div>
</body>
</html>
"""
